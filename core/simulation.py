from __future__ import annotations

from calendar import monthrange
from datetime import date
from pathlib import Path
from typing import Any

from core.asset import get_current_balances
from core.investment import calculate_monthly_contributions, get_investment_plans
from data.database import DB_PATH, get_connection

USER_ID = 1
SCENARIO_CODES = ("BEAR", "BASE", "BULL")


def calculate_monthly_rate(annual_rate: float) -> float:
    """Convert an effective annual return into an effective monthly return."""
    if annual_rate <= -1:
        raise ValueError("annual_rate must be greater than -100%")
    return (1.0 + float(annual_rate)) ** (1.0 / 12.0) - 1.0


def _add_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + offset
    return index // 12, index % 12 + 1


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def get_simulation_inputs(
    user_id: int = USER_ID,
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Load the DB inputs required by the simulation engine."""
    assets = get_current_balances(user_id=user_id, db_path=db_path)
    plans = get_investment_plans(user_id=user_id, active_only=True, db_path=db_path)

    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                s.id AS scenario_id,
                s.scenario_code,
                s.scenario_name,
                s.display_order,
                ara.asset_id,
                ara.annual_return_rate
            FROM simulation_scenarios s
            JOIN asset_return_assumptions ara ON ara.scenario_id = s.id
            JOIN assets a ON a.id = ara.asset_id
            WHERE s.is_active = 1
              AND a.user_id = ?
              AND a.is_active = 1
            ORDER BY s.display_order, a.display_order
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    scenarios: dict[str, dict[str, Any]] = {}
    return_assumptions: dict[str, dict[int, float]] = {}
    for row in rows:
        code = str(row["scenario_code"])
        scenarios[code] = {
            "id": int(row["scenario_id"]),
            "code": code,
            "name": row["scenario_name"],
            "display_order": int(row["display_order"]),
        }
        return_assumptions.setdefault(code, {})[int(row["asset_id"])] = float(
            row["annual_return_rate"]
        )

    return {
        "assets": assets,
        "plans": plans,
        "scenarios": scenarios,
        "return_assumptions": return_assumptions,
    }


def simulate_asset(
    *,
    asset_id: int,
    initial_balance: int | float,
    annual_rate: float,
    contributions: dict[tuple[int, int], int | float],
    start_date: date,
    months: int,
    current_age: int | None = None,
    scenario: str = "BASE",
) -> list[dict[str, Any]]:
    """Simulate one asset month by month using the month-end contribution model."""
    if months < 0:
        raise ValueError("months must be >= 0")
    if initial_balance < 0:
        raise ValueError("initial_balance must be >= 0")
    if annual_rate <= -1:
        raise ValueError("annual_rate must be greater than -100%")

    monthly_rate = calculate_monthly_rate(annual_rate)
    balance = float(initial_balance)
    cumulative_contribution = 0.0
    cumulative_gain = 0.0
    results: list[dict[str, Any]] = []

    for offset in range(1, months + 1):
        year, month = _add_month(start_date.year, start_date.month, offset)
        record_date = _month_end(year, month)
        contribution = float(contributions.get((year, month), 0))
        beginning_balance = balance
        investment_gain = beginning_balance * monthly_rate
        ending_balance = beginning_balance + investment_gain + contribution

        cumulative_contribution += contribution
        cumulative_gain += investment_gain
        balance = ending_balance

        results.append(
            {
                "date": record_date.isoformat(),
                "age": None if current_age is None else current_age + offset // 12,
                "scenario": scenario,
                "asset_id": asset_id,
                "beginning_balance": beginning_balance,
                "contribution": contribution,
                "investment_gain": investment_gain,
                "ending_balance": ending_balance,
                "cumulative_contribution": cumulative_contribution,
                "cumulative_gain": cumulative_gain,
            }
        )

    return results


def simulate_portfolio(
    *,
    user_id: int = USER_ID,
    current_age: int,
    years: int | None = None,
    target_age: int | None = None,
    start_date: date | None = None,
    scenario: str | None = None,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    """Run monthly simulation for all active assets and requested scenarios.

    The current balance is treated as the starting point. Simulation begins in
    the calendar month following ``start_date`` and contributions are applied at
    month end. Results are returned in memory and are not persisted to the DB.
    """
    if current_age < 0 or current_age > 150:
        raise ValueError("current_age must be between 0 and 150")
    if years is None and target_age is None:
        raise ValueError("either years or target_age is required")
    if years is not None and years <= 0:
        raise ValueError("years must be > 0")
    if target_age is not None and target_age <= current_age:
        raise ValueError("target_age must be greater than current_age")

    if target_age is not None:
        months = (target_age - current_age) * 12
    else:
        months = int(years) * 12

    effective_start = start_date or date.today()
    inputs = get_simulation_inputs(user_id=user_id, db_path=db_path)
    scenario_codes = [scenario] if scenario else [
        code for code, _ in sorted(
            inputs["scenarios"].items(), key=lambda item: item[1]["display_order"]
        )
    ]

    unknown = [code for code in scenario_codes if code not in inputs["scenarios"]]
    if unknown:
        raise ValueError(f"unknown scenario: {unknown[0]}")

    balances = {
        int(row["asset_id"]): float(row["balance"] or 0)
        for row in inputs["assets"]
    }
    asset_ids = [int(row["asset_id"]) for row in inputs["assets"]]
    plans = inputs["plans"]

    # Generate one multi-year contribution calendar so recurring plans continue
    # automatically throughout the simulation horizon.
    first_year, first_month = _add_month(effective_start.year, effective_start.month, 1)
    contribution_calendar: dict[tuple[int, int], dict[int, int]] = {}
    for offset in range(months):
        year, month = _add_month(first_year, first_month, offset)
        contribution_calendar[(year, month)] = {
            asset_id: amount
            for asset_id, amount in calculate_monthly_contributions(
                plans, year=year
            )[month].items()
        }

    all_results: list[dict[str, Any]] = []
    for scenario_code in scenario_codes:
        assumptions = inputs["return_assumptions"].get(scenario_code, {})
        for asset_id in asset_ids:
            if asset_id not in assumptions:
                raise ValueError(
                    f"missing return assumption for scenario={scenario_code}, asset_id={asset_id}"
                )

            asset_contributions = {
                key: values.get(asset_id, 0)
                for key, values in contribution_calendar.items()
            }
            all_results.extend(
                simulate_asset(
                    asset_id=asset_id,
                    initial_balance=balances.get(asset_id, 0),
                    annual_rate=assumptions[asset_id],
                    contributions=asset_contributions,
                    start_date=effective_start,
                    months=months,
                    current_age=current_age,
                    scenario=scenario_code,
                )
            )

    return all_results



def simulate_portfolio_with_plans(
    *,
    plans: list[dict[str, Any]],
    current_age: int,
    target_age: int,
    scenario: str,
    user_id: int = USER_ID,
    start_date: date | None = None,
    db_path: Path | str = DB_PATH,
) -> float:
    """Return the target-age portfolio value using an in-memory plan override.

    This is used by What-if and goal reverse calculations. The supplied plans
    are never written to the database.
    """
    if target_age <= current_age:
        raise ValueError("target_age must be greater than current_age")
    inputs = get_simulation_inputs(user_id=user_id, db_path=db_path)
    if scenario not in inputs["scenarios"]:
        raise ValueError(f"unknown scenario: {scenario}")

    effective_start = start_date or date.today()
    months = (target_age - current_age) * 12
    first_year, first_month = _add_month(effective_start.year, effective_start.month, 1)
    contribution_calendar: dict[tuple[int, int], dict[int, int]] = {}
    for offset in range(months):
        year, month = _add_month(first_year, first_month, offset)
        contribution_calendar[(year, month)] = calculate_monthly_contributions(
            plans, year=year
        )[month]

    balances = {
        int(row["asset_id"]): float(row["balance"] or 0)
        for row in inputs["assets"]
    }
    assumptions = inputs["return_assumptions"][scenario]
    total = 0.0
    for asset_id in balances:
        if asset_id not in assumptions:
            raise ValueError(
                f"missing return assumption for scenario={scenario}, asset_id={asset_id}"
            )
        asset_contributions = {
            key: values.get(asset_id, 0)
            for key, values in contribution_calendar.items()
        }
        rows = simulate_asset(
            asset_id=asset_id,
            initial_balance=balances[asset_id],
            annual_rate=assumptions[asset_id],
            contributions=asset_contributions,
            start_date=effective_start,
            months=months,
            current_age=current_age,
            scenario=scenario,
        )
        total += rows[-1]["ending_balance"] if rows else balances[asset_id]
    return total


def run_what_if(
    *,
    current_age: int,
    target_age: int,
    scenario: str,
    monthly_asset_id: int,
    what_if_monthly_amount: int,
    user_id: int = USER_ID,
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Compare the current plan with a temporary monthly-investment change."""
    if what_if_monthly_amount < 0:
        raise ValueError("what_if_monthly_amount must be >= 0")
    plans = get_investment_plans(user_id=user_id, active_only=True, db_path=db_path)
    monthly_plans = [
        p for p in plans
        if int(p["asset_id"]) == monthly_asset_id and p["frequency"] == "monthly"
    ]
    if not monthly_plans:
        raise ValueError("selected asset has no active monthly investment plan")

    current_results = simulate_portfolio(
        user_id=user_id,
        current_age=current_age,
        target_age=target_age,
        scenario=scenario,
        db_path=db_path,
    )
    current_portfolio = aggregate_portfolio_results(current_results)
    current_rows = [r for r in current_portfolio if r["scenario"] == scenario]
    if not current_rows:
        raise ValueError("current simulation returned no results")

    override_plans = []
    for plan in plans:
        item = dict(plan)
        if int(item["asset_id"]) == monthly_asset_id and item["frequency"] == "monthly":
            item["amount"] = what_if_monthly_amount
        override_plans.append(item)

    what_if = simulate_portfolio_with_plans(
        plans=override_plans,
        current_age=current_age,
        target_age=target_age,
        scenario=scenario,
        user_id=user_id,
        db_path=db_path,
    )
    current_monthly = sum(int(p["amount"]) for p in monthly_plans)
    current_final = current_rows[-1]["ending_balance"]
    return {
        "scenario": scenario,
        "target_age": target_age,
        "asset_id": monthly_asset_id,
        "current_monthly": current_monthly,
        "what_if_monthly": what_if_monthly_amount,
        "monthly_difference": what_if_monthly_amount - current_monthly,
        "current_forecast": current_final,
        "what_if_forecast": what_if,
        "forecast_difference": what_if - current_final,
    }

def aggregate_portfolio_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate asset-level results into one row per date/scenario."""
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in results:
        key = (str(row["scenario"]), str(row["date"]))
        item = grouped.setdefault(
            key,
            {
                "date": row["date"],
                "age": row["age"],
                "scenario": row["scenario"],
                "beginning_balance": 0.0,
                "contribution": 0.0,
                "investment_gain": 0.0,
                "ending_balance": 0.0,
                "cumulative_contribution": 0.0,
                "cumulative_gain": 0.0,
            },
        )
        item["beginning_balance"] += row["beginning_balance"]
        item["contribution"] += row["contribution"]
        item["investment_gain"] += row["investment_gain"]
        item["ending_balance"] += row["ending_balance"]
        item["cumulative_contribution"] += row["cumulative_contribution"]
        item["cumulative_gain"] += row["cumulative_gain"]

    return sorted(grouped.values(), key=lambda row: (row["scenario"], row["date"]))

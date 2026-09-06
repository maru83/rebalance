from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from core.asset import get_current_balances, get_portfolio_history
from core.goal import evaluate_goal, get_current_age, get_goals
from core.investment import calculate_annual_investment, calculate_monthly_total, get_investment_plans
from core.simulation import aggregate_portfolio_results, simulate_portfolio
from data.database import DB_PATH

USER_ID = 1


def get_total_assets(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> int:
    return int(round(sum(float(row["balance"] or 0) for row in get_current_balances(user_id, db_path))))


def get_assets_by_purpose(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> dict[str, int]:
    totals = {"asset_formation": 0, "retirement": 0, "emergency_fund": 0}
    for row in get_current_balances(user_id, db_path):
        purpose = row["purpose"]
        if purpose in totals:
            totals[purpose] += int(row["balance"] or 0)
    return totals


def get_annual_investment(
    user_id: int = USER_ID,
    year: int | None = None,
    db_path: Path | str = DB_PATH,
) -> int:
    target_year = year or date.today().year
    plans = get_investment_plans(user_id=user_id, active_only=True, db_path=db_path)
    return calculate_annual_investment(plans, year=target_year)


def get_monthly_investment(
    user_id: int = USER_ID,
    year: int | None = None,
    month: int | None = None,
    db_path: Path | str = DB_PATH,
) -> int:
    today = date.today()
    target_year = year or today.year
    target_month = month or today.month
    plans = get_investment_plans(user_id=user_id, active_only=True, db_path=db_path)
    return int(calculate_monthly_total(plans, year=target_year).get(target_month, 0))


def get_investment_breakdown(
    user_id: int = USER_ID,
    year: int | None = None,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    target_year = year or date.today().year
    plans = get_investment_plans(user_id=user_id, active_only=True, db_path=db_path)
    by_asset: dict[int, int] = {}
    from core.investment import calculate_monthly_contributions
    calendar = calculate_monthly_contributions(plans, year=target_year)
    for month_values in calendar.values():
        for asset_id, amount in month_values.items():
            by_asset[asset_id] = by_asset.get(asset_id, 0) + int(amount)

    names = {int(row["asset_id"]): row["asset_name"] for row in get_current_balances(user_id, db_path)}
    return [
        {"asset_id": asset_id, "asset_name": names.get(asset_id, str(asset_id)), "annual_investment": amount}
        for asset_id, amount in sorted(by_asset.items(), key=lambda item: (-item[1], item[0]))
    ]


def get_asset_history(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    return get_portfolio_history(user_id=user_id, db_path=db_path)


def get_latest_update_date(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> str | None:
    rows = get_current_balances(user_id=user_id, db_path=db_path)
    dates = [str(row["as_of_date"]) for row in rows if row["as_of_date"]]
    return max(dates) if dates else None


def get_goal_status(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    current_age = get_current_age(db_path=db_path, user_id=user_id)
    goals = get_goals(user_id=user_id, active_only=True, db_path=db_path)
    if current_age is None or not goals:
        return None
    goal = goals[0]
    if int(goal["target_age"]) <= current_age:
        return None
    return evaluate_goal(goal=goal, current_age=current_age, scenario="BASE", db_path=db_path)


def get_simulation_summary(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    current_age = get_current_age(db_path=db_path, user_id=user_id)
    if current_age is None:
        return None

    goals = get_goals(user_id=user_id, active_only=True, db_path=db_path)
    future_target_age = None
    if goals:
        valid_goals = [g for g in goals if int(g["target_age"]) > current_age]
        if valid_goals:
            future_target_age = int(valid_goals[0]["target_age"])

    if future_target_age is not None:
        results = simulate_portfolio(
            user_id=user_id,
            current_age=current_age,
            target_age=future_target_age,
            scenario="BASE",
            db_path=db_path,
        )
        horizon_label = f"{future_target_age}歳時点"
    else:
        results = simulate_portfolio(
            user_id=user_id,
            current_age=current_age,
            years=30,
            scenario="BASE",
            db_path=db_path,
        )
        horizon_label = "30年後"

    portfolio = aggregate_portfolio_results(results)
    rows = [row for row in portfolio if row["scenario"] == "BASE"]
    if not rows:
        return None
    final = rows[-1]
    return {
        "horizon_label": horizon_label,
        "target_age": future_target_age,
        "forecast_amount": final["ending_balance"],
        "cumulative_contribution": final["cumulative_contribution"],
        "cumulative_gain": final["cumulative_gain"],
        "current_balance": get_total_assets(user_id, db_path),
        "rows": rows,
    }

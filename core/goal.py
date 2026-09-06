from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.investment import get_investment_plans
from core.simulation import aggregate_portfolio_results, simulate_portfolio, simulate_portfolio_with_plans
from data.database import DB_PATH, get_connection, transaction

MAX_AMOUNT = 9_000_000_000_000_000_000

USER_ID = 1


def get_goals(user_id: int = USER_ID, active_only: bool = False, db_path: Path | str = DB_PATH) -> list[dict[str, Any]]:
    sql = """
        SELECT id, user_id, goal_name, target_age, target_amount, purpose,
               is_active, created_at, updated_at
        FROM goals
        WHERE user_id = ?
    """
    params: list[Any] = [user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY target_age, id"

    conn = get_connection(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def save_goal(
    *,
    goal_id: int | None,
    user_id: int,
    goal_name: str,
    target_age: int,
    target_amount: int,
    purpose: str | None = None,
    db_path: Path | str = DB_PATH,
) -> int:
    if not goal_name.strip():
        raise ValueError("goal_name is required")
    if target_age <= 0 or target_age > 150:
        raise ValueError("target_age must be between 1 and 150")
    if not isinstance(target_amount, int) or target_amount < 0:
        raise ValueError("target_amount must be a non-negative integer")
    if target_amount > MAX_AMOUNT:
        raise ValueError("target_amount is too large for the database")

    now = datetime.now().isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        if goal_id is None:
            cur = conn.execute(
                """
                INSERT INTO goals
                    (user_id, goal_name, target_age, target_amount, purpose,
                     is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (user_id, goal_name.strip(), target_age, target_amount, purpose, now, now),
            )
            return int(cur.lastrowid)

        conn.execute(
            """
            UPDATE goals
            SET goal_name = ?, target_age = ?, target_amount = ?, purpose = ?,
                is_active = 1, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (goal_name.strip(), target_age, target_amount, purpose, now, goal_id, user_id),
        )
        return goal_id


def deactivate_goal(goal_id: int, user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            """
            UPDATE goals SET is_active = 0, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (datetime.now().isoformat(timespec="seconds"), goal_id, user_id),
        )


def get_current_age(db_path: Path | str = DB_PATH, user_id: int = USER_ID) -> int | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT current_age FROM app_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else int(row["current_age"])


def evaluate_goal(
    *,
    goal: dict[str, Any],
    current_age: int,
    scenario: str = "BASE",
    db_path: Path | str = DB_PATH,
) -> dict[str, Any]:
    """Compare the target with the portfolio projection at target age."""
    results = simulate_portfolio(
        current_age=current_age,
        target_age=int(goal["target_age"]),
        scenario=scenario,
        db_path=db_path,
    )
    portfolio = aggregate_portfolio_results(results)
    rows = [r for r in portfolio if r["scenario"] == scenario]
    if not rows:
        raise ValueError("simulation returned no results")
    final = rows[-1]
    target = int(goal["target_amount"])
    forecast = float(final["ending_balance"])
    achievement_rate = 0.0 if target == 0 else forecast / target
    gap = forecast - target
    return {
        "goal_id": int(goal["id"]),
        "goal_name": goal["goal_name"],
        "target_age": int(goal["target_age"]),
        "target_amount": target,
        "scenario": scenario,
        "forecast_amount": forecast,
        "achievement_rate": achievement_rate,
        "gap": gap,
        "status": "達成見込み" if forecast >= target else "未達見込み",
    }


def _replace_monthly_plan_amounts(
    plans: list[dict[str, Any]],
    *,
    asset_id: int,
    monthly_amount: int,
) -> list[dict[str, Any]]:
    """Return a copy of plans with monthly plans for one asset replaced."""
    copied: list[dict[str, Any]] = []
    for plan in plans:
        item = dict(plan)
        if int(item["asset_id"]) == asset_id and item["frequency"] == "monthly":
            item["amount"] = monthly_amount
        copied.append(item)
    return copied


def calculate_required_monthly_investment(
    *,
    goal: dict[str, Any],
    current_age: int,
    scenario: str = "BASE",
    monthly_asset_id: int,
    db_path: Path | str = DB_PATH,
    upper_bound: int = 10_000_000,
) -> dict[str, Any]:
    """Find the minimum monthly amount that reaches the goal via binary search.

    Existing bonus/yearly plans are kept unchanged; only monthly plans for the
    selected asset are replaced. The returned amount is rounded up to ¥10,000.
    """
    if int(goal["target_age"]) <= current_age:
        raise ValueError("target_age must be greater than current_age")
    if upper_bound <= 0:
        raise ValueError("upper_bound must be positive")

    plans = get_investment_plans(user_id=USER_ID, active_only=True, db_path=db_path)
    monthly_plans = [p for p in plans if int(p["asset_id"]) == monthly_asset_id and p["frequency"] == "monthly"]
    if not monthly_plans:
        raise ValueError("selected asset has no active monthly investment plan")

    target = int(goal["target_amount"])

    def reaches(amount: int) -> bool:
        forecast = simulate_portfolio_with_plans(
            current_age=current_age,
            target_age=int(goal["target_age"]),
            scenario=scenario,
            plans=_replace_monthly_plan_amounts(
                plans, asset_id=monthly_asset_id, monthly_amount=amount
            ),
            db_path=db_path,
        )
        return forecast >= target

    if reaches(0):
        required = 0
    elif not reaches(upper_bound):
        return {
            "calculable": False,
            "reason": "upper_bound_exceeded",
            "required_monthly": None,
            "current_monthly": sum(int(p["amount"]) for p in monthly_plans),
            "difference": None,
        }
    else:
        lo, hi = 0, upper_bound
        while lo < hi:
            mid = (lo + hi) // 2
            if reaches(mid):
                hi = mid
            else:
                lo = mid + 1
        required = lo

    rounded_required = ((required + 9_999) // 10_000) * 10_000
    current_monthly = sum(int(p["amount"]) for p in monthly_plans)
    return {
        "calculable": True,
        "reason": None,
        "required_monthly": rounded_required,
        "unrounded_required_monthly": required,
        "current_monthly": current_monthly,
        "difference": rounded_required - current_monthly,
    }

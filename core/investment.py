from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from data.database import DB_PATH, get_connection, transaction

MAX_AMOUNT = 9_000_000_000_000_000_000  # below SQLite signed 64-bit integer max

USER_ID = 1


def get_investment_plans(
    user_id: int = USER_ID,
    active_only: bool = True,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            ip.id,
            ip.user_id,
            ip.asset_id,
            a.asset_name,
            a.institution_name,
            ip.plan_name,
            ip.frequency,
            ip.amount,
            ip.month,
            ip.day,
            ip.start_date,
            ip.end_date,
            ip.is_active
        FROM investment_plans ip
        JOIN assets a ON a.id = ip.asset_id
        WHERE ip.user_id = ?
          AND a.is_active = 1
    """
    params: list[Any] = [user_id]

    if active_only:
        sql += " AND ip.is_active = 1"

    sql += " ORDER BY a.display_order, ip.frequency, ip.month, ip.id"

    conn = get_connection(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def save_investment_plan(
    *,
    plan_id: int | None,
    user_id: int,
    asset_id: int,
    plan_name: str,
    frequency: str,
    amount: int,
    month: int | None = None,
    day: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db_path: Path | str = DB_PATH,
) -> int:
    if not plan_name.strip():
        raise ValueError("plan_name is required")
    if frequency not in {"monthly", "yearly", "one_time"}:
        raise ValueError("invalid frequency")
    if frequency in {"yearly", "one_time"} and month is None:
        raise ValueError("month is required for yearly/one_time plans")
    if frequency == "one_time" and start_date is None:
        raise ValueError("start_date is required for one_time plans")
    if not isinstance(amount, int) or amount < 0:
        raise ValueError("amount must be a non-negative integer")
    if amount > MAX_AMOUNT:
        raise ValueError("amount is too large for the database")
    if month is not None and not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if day is not None and not 1 <= day <= 31:
        raise ValueError("day must be between 1 and 31")
    if start_date and end_date and end_date < start_date:
        raise ValueError("end_date must not precede start_date")

    now = datetime.now().isoformat(timespec="seconds")

    with transaction(db_path) as conn:
        if plan_id is None:
            cur = conn.execute(
                """
                INSERT INTO investment_plans
                    (user_id, asset_id, plan_name, frequency, amount,
                     month, day, start_date, end_date, is_active,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id, asset_id, plan_name.strip(), frequency, amount,
                    month, day,
                    start_date.isoformat() if start_date else None,
                    end_date.isoformat() if end_date else None,
                    now, now,
                ),
            )
            return int(cur.lastrowid)

        conn.execute(
            """
            UPDATE investment_plans
            SET asset_id = ?,
                plan_name = ?,
                frequency = ?,
                amount = ?,
                month = ?,
                day = ?,
                start_date = ?,
                end_date = ?,
                is_active = 1,
                updated_at = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                asset_id, plan_name.strip(), frequency, amount,
                month, day,
                start_date.isoformat() if start_date else None,
                end_date.isoformat() if end_date else None,
                now, plan_id, user_id,
            ),
        )
        return plan_id


def deactivate_investment_plan(
    plan_id: int,
    user_id: int = USER_ID,
    db_path: Path | str = DB_PATH,
) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            """
            UPDATE investment_plans
            SET is_active = 0,
                updated_at = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (datetime.now().isoformat(timespec="seconds"), plan_id, user_id),
        )


def calculate_monthly_contributions(
    plans: list[dict[str, Any]],
    *,
    year: int,
) -> dict[int, dict[int, int]]:
    """Return {month: {asset_id: contribution}} for the requested year."""
    result = {month: {} for month in range(1, 13)}

    for plan in plans:
        amount = int(plan["amount"])
        frequency = plan["frequency"]

        start = date.fromisoformat(plan["start_date"]) if plan["start_date"] else None
        end = date.fromisoformat(plan["end_date"]) if plan["end_date"] else None

        for month in range(1, 13):
            period = date(year, month, 1)

            if start and period < date(start.year, start.month, 1):
                continue
            if end and period > date(end.year, end.month, 1):
                continue

            contribution = 0
            if frequency == "monthly":
                contribution = amount
            elif frequency == "yearly" and plan["month"] == month:
                contribution = amount
            elif frequency == "one_time":
                if plan["month"] == month and start and start.year == year:
                    contribution = amount

            if contribution:
                asset_id = int(plan["asset_id"])
                result[month][asset_id] = (
                    result[month].get(asset_id, 0) + contribution
                )

    return result


def calculate_annual_investment(
    plans: list[dict[str, Any]],
    *,
    year: int,
) -> int:
    monthly = calculate_monthly_contributions(plans, year=year)
    return sum(sum(by_asset.values()) for by_asset in monthly.values())


def calculate_monthly_total(
    plans: list[dict[str, Any]],
    *,
    year: int,
) -> dict[int, int]:
    monthly = calculate_monthly_contributions(plans, year=year)
    return {
        month: sum(by_asset.values())
        for month, by_asset in monthly.items()
    }

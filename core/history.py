from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from data.database import DB_PATH, get_connection


def get_asset_history_detail(
    user_id: int = 1,
    asset_ids: list[int] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    """Return active-asset history rows with asset metadata and optional filters."""
    sql = """
        SELECT
            h.asset_id,
            a.asset_name,
            a.institution_name,
            a.purpose,
            h.record_date,
            h.balance
        FROM asset_balance_history h
        JOIN assets a ON a.id = h.asset_id
        WHERE a.user_id = ?
          AND a.is_active = 1
    """
    params: list[Any] = [user_id]

    if asset_ids:
        placeholders = ",".join("?" for _ in asset_ids)
        sql += f" AND h.asset_id IN ({placeholders})"
        params.extend(asset_ids)
    if start_date is not None:
        sql += " AND h.record_date >= ?"
        params.append(start_date.isoformat())
    if end_date is not None:
        sql += " AND h.record_date <= ?"
        params.append(end_date.isoformat())

    sql += " ORDER BY h.record_date, a.display_order, a.id"

    conn = get_connection(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_history_date_range(
    user_id: int = 1,
    db_path: Path | str = DB_PATH,
) -> tuple[date | None, date | None]:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT MIN(h.record_date) AS min_date,
                   MAX(h.record_date) AS max_date
            FROM asset_balance_history h
            JOIN assets a ON a.id = h.asset_id
            WHERE a.user_id = ? AND a.is_active = 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if not row or row["min_date"] is None:
        return None, None
    return date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"])


def resolve_history_start_date(
    end_date: date,
    period: str,
    earliest_date: date | None,
) -> date | None:
    """Resolve a UI period label into a start date."""
    if earliest_date is None:
        return None
    if period == "全期間":
        return earliest_date
    days = {"3か月": 90, "6か月": 180, "1年": 365}.get(period)
    if days is None:
        raise ValueError(f"unsupported period: {period}")
    return max(earliest_date, end_date - timedelta(days=days))

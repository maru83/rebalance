from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from data.database import DB_PATH, transaction, get_connection

MAX_AMOUNT = 9_000_000_000_000_000_000


def get_assets(
    user_id: int = 1,
    active_only: bool = True,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, user_id, asset_name, institution_name, asset_type,
               purpose, is_investment, display_order, is_active
        FROM assets
        WHERE user_id = ?
    """
    params: list[Any] = [user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY display_order, id"

    conn = get_connection(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def get_current_balances(
    user_id: int = 1,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            a.id AS asset_id,
            a.asset_name,
            a.institution_name,
            a.asset_type,
            a.purpose,
            a.display_order,
            ab.balance,
            ab.as_of_date
        FROM assets a
        LEFT JOIN asset_balances ab ON ab.asset_id = a.id
        WHERE a.user_id = ?
          AND a.is_active = 1
        ORDER BY a.display_order, a.id
    """
    conn = get_connection(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, (user_id,)).fetchall()]
    finally:
        conn.close()


def get_latest_history_date(
    asset_id: int,
    db_path: Path | str = DB_PATH,
) -> str | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT MAX(record_date) AS latest_date
            FROM asset_balance_history
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()
        return row["latest_date"] if row else None
    finally:
        conn.close()


def get_balance_history(
    asset_id: int,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT asset_id, balance, record_date, created_at
            FROM asset_balance_history
            WHERE asset_id = ?
            ORDER BY record_date
            """,
            (asset_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_balance(
    asset_id: int,
    balance: int,
    record_date: date,
    db_path: Path | str = DB_PATH,
) -> None:
    if not isinstance(balance, int):
        raise ValueError("balance must be an integer")
    if balance < 0:
        raise ValueError("balance must be >= 0")
    if balance > MAX_AMOUNT:
        raise ValueError("balance is too large for the database")

    today = date.today()
    if record_date > today:
        raise ValueError("future dates are not allowed")

    with transaction(db_path) as conn:
        current = conn.execute(
            "SELECT as_of_date FROM asset_balances WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()

        if current is not None and record_date.isoformat() < current["as_of_date"]:
            raise ValueError("past-dated current balance updates are not allowed")

        now = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            """
            INSERT INTO asset_balances
                (asset_id, balance, as_of_date, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id)
            DO UPDATE SET
                balance = excluded.balance,
                as_of_date = excluded.as_of_date,
                updated_at = excluded.updated_at
            """,
            (asset_id, balance, record_date.isoformat(), now, now),
        )

        conn.execute(
            """
            INSERT INTO asset_balance_history
                (asset_id, balance, record_date, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(asset_id, record_date)
            DO UPDATE SET
                balance = excluded.balance
            """,
            (asset_id, balance, record_date.isoformat(), now),
        )


def get_portfolio_history(
    user_id: int = 1,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    """Return total active-asset balance by record date.

    Dates are derived from asset_balance_history, so the historical view
    remains based on the history table (the source of truth).
    """
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                h.record_date,
                SUM(h.balance) AS total_balance
            FROM asset_balance_history h
            JOIN assets a ON a.id = h.asset_id
            WHERE a.user_id = ?
              AND a.is_active = 1
            GROUP BY h.record_date
            ORDER BY h.record_date
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

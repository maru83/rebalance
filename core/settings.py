from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from data.database import DB_PATH, get_connection, transaction

USER_ID = 1


def get_settings(user_id: int = USER_ID, db_path: Path | str = DB_PATH) -> dict[str, Any] | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, user_id, current_age, simulation_years, currency, display_unit,
                   created_at, updated_at
            FROM app_settings
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else dict(row)


def validate_settings(*, current_age: int, simulation_years: int, currency: str, display_unit: str) -> None:
    if not isinstance(current_age, int) or not 0 <= current_age <= 150:
        raise ValueError("current_age must be between 0 and 150")
    if not isinstance(simulation_years, int) or not 1 <= simulation_years <= 100:
        raise ValueError("simulation_years must be between 1 and 100")
    if currency not in {"JPY"}:
        raise ValueError("unsupported currency")
    if display_unit not in {"yen", "man", "million"}:
        raise ValueError("unsupported display_unit")


def save_settings(
    *,
    user_id: int = USER_ID,
    current_age: int,
    simulation_years: int,
    currency: str = "JPY",
    display_unit: str = "yen",
    db_path: Path | str = DB_PATH,
) -> None:
    validate_settings(
        current_age=current_age,
        simulation_years=simulation_years,
        currency=currency,
        display_unit=display_unit,
    )
    now = datetime.now().isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        conn.execute(
            """
            INSERT INTO app_settings
                (user_id, current_age, simulation_years, currency, display_unit,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_age = excluded.current_age,
                simulation_years = excluded.simulation_years,
                currency = excluded.currency,
                display_unit = excluded.display_unit,
                updated_at = excluded.updated_at
            """,
            (user_id, current_age, simulation_years, currency, display_unit, now, now),
        )


def get_return_assumptions(
    user_id: int = USER_ID,
    db_path: Path | str = DB_PATH,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT ara.id, ara.asset_id, a.asset_name,
                   s.scenario_code, s.scenario_name,
                   ara.annual_return_rate
            FROM asset_return_assumptions ara
            JOIN assets a ON a.id = ara.asset_id
            JOIN simulation_scenarios s ON s.id = ara.scenario_id
            WHERE a.user_id = ? AND a.is_active = 1 AND s.is_active = 1
            ORDER BY a.display_order, s.display_order
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def save_return_assumptions(
    assumptions: list[dict[str, Any]],
    *,
    user_id: int = USER_ID,
    db_path: Path | str = DB_PATH,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with transaction(db_path) as conn:
        for item in assumptions:
            asset_id = int(item["asset_id"])
            scenario_code = str(item["scenario_code"])
            rate = float(item["annual_return_rate"])
            if not -1.0 <= rate <= 1.0:
                raise ValueError("annual_return_rate must be between -100% and 100%")
            row = conn.execute(
                """
                SELECT ara.id
                FROM asset_return_assumptions ara
                JOIN simulation_scenarios s ON s.id = ara.scenario_id
                JOIN assets a ON a.id = ara.asset_id
                WHERE ara.asset_id = ? AND s.scenario_code = ? AND a.user_id = ?
                """,
                (asset_id, scenario_code, user_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"return assumption not found: asset_id={asset_id}, scenario={scenario_code}")
            conn.execute(
                "UPDATE asset_return_assumptions SET annual_return_rate = ?, updated_at = ? WHERE id = ?",
                (rate, now, int(row["id"])),
            )

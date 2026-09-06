from pathlib import Path

from data.database import initialize_database


def test_initialize_database(tmp_path: Path):
    db_path = tmp_path / "test.db"
    initialize_database(db_path)

    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()

    expected = {
        "users",
        "app_settings",
        "assets",
        "asset_balances",
        "asset_balance_history",
        "investment_plans",
        "simulation_scenarios",
        "asset_return_assumptions",
        "goals",
    }
    assert expected.issubset(tables)
    assert "simulation_settings" not in tables

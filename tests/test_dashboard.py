from pathlib import Path
from datetime import date

from core.asset import get_assets, save_balance
from core.dashboard import (
    get_asset_history,
    get_assets_by_purpose,
    get_annual_investment,
    get_investment_breakdown,
    get_latest_update_date,
    get_monthly_investment,
    get_total_assets,
)
from core.investment import save_investment_plan
from data.database import get_connection, initialize_database


def test_dashboard_asset_aggregation(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    save_balance(assets[0]["id"], 1_000_000, date(2026, 9, 5), db)
    save_balance(assets[1]["id"], 500_000, date(2026, 9, 5), db)
    save_balance(assets[2]["id"], 300_000, date(2026, 9, 5), db)
    save_balance(assets[3]["id"], 200_000, date(2026, 9, 5), db)

    assert get_total_assets(db_path=db) == 2_000_000
    assert get_assets_by_purpose(db_path=db) == {
        "asset_formation": 1_500_000,
        "retirement": 300_000,
        "emergency_fund": 200_000,
    }


def test_dashboard_investment_metrics(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=assets[0]["id"], plan_name="毎月", frequency="monthly", amount=50_000, db_path=db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=assets[0]["id"], plan_name="夏", frequency="yearly", amount=300_000, month=6, db_path=db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=assets[1]["id"], plan_name="冬", frequency="yearly", amount=200_000, month=12, db_path=db)

    assert get_annual_investment(year=2026, db_path=db) == 1_100_000
    assert get_monthly_investment(year=2026, month=6, db_path=db) == 350_000
    breakdown = get_investment_breakdown(year=2026, db_path=db)
    assert breakdown[0]["annual_investment"] == 900_000
    assert breakdown[1]["annual_investment"] == 200_000


def test_dashboard_history_and_latest_update(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 1_000_000, date(2026, 8, 1), db)
    save_balance(asset["id"], 1_100_000, date(2026, 9, 5), db)

    history = get_asset_history(db_path=db)
    assert history[-1]["record_date"] == "2026-09-05"
    assert history[-1]["total_balance"] == 1_100_000
    assert get_latest_update_date(db_path=db) == "2026-09-05"

from datetime import date, timedelta
from pathlib import Path

from core.asset import get_assets, save_balance
from core.history import (
    get_asset_history_detail,
    get_history_date_range,
    resolve_history_start_date,
)
from data.database import initialize_database


def test_history_detail_returns_selected_assets_and_metadata(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    d = date.today()

    save_balance(assets[0]["id"], 1_000_000, d, db)
    save_balance(assets[1]["id"], 500_000, d, db)

    rows = get_asset_history_detail(
        asset_ids=[assets[0]["id"]], db_path=db
    )
    assert len(rows) == 1
    assert rows[0]["asset_name"] == "NISA・オルカン"
    assert rows[0]["balance"] == 1_000_000


def test_history_date_range(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset_id = get_assets(db_path=db)[0]["id"]
    d1 = date.today() - timedelta(days=30)
    d2 = date.today()

    save_balance(asset_id, 900_000, d1, db)
    save_balance(asset_id, 1_000_000, d2, db)

    assert get_history_date_range(db_path=db) == (d1, d2)


def test_resolve_history_start_date():
    earliest = date(2026, 1, 1)
    end = date(2026, 9, 5)
    assert resolve_history_start_date(end, "全期間", earliest) == earliest
    assert resolve_history_start_date(end, "3か月", earliest) == date(2026, 6, 7)
    assert resolve_history_start_date(end, "1年", earliest) == earliest

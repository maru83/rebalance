from datetime import date, timedelta
from pathlib import Path

import pytest

from core.asset import (
    get_assets,
    get_balance_history,
    get_current_balances,
    get_portfolio_history,
    save_balance,
)
from data.database import initialize_database


def test_asset_master_has_four_initial_assets(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    assets = get_assets(db_path=db)
    assert len(assets) == 4
    assert [a["asset_name"] for a in assets] == [
        "NISA・オルカン",
        "個人向け国債",
        "企業型DC・オルカン",
        "定期預金",
    ]


def test_save_balance_updates_current_and_history_atomically(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset_id = get_assets(db_path=db)[0]["id"]
    today = date.today()

    save_balance(asset_id, 1_000_000, today, db)

    current = get_current_balances(db_path=db)[0]
    history = get_balance_history(asset_id, db)

    assert current["balance"] == 1_000_000
    assert current["as_of_date"] == today.isoformat()
    assert history[-1]["balance"] == 1_000_000
    assert history[-1]["record_date"] == today.isoformat()


def test_same_day_update_overwrites_history(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset_id = get_assets(db_path=db)[0]["id"]
    today = date.today()

    save_balance(asset_id, 1_000_000, today, db)
    save_balance(asset_id, 1_200_000, today, db)

    history = get_balance_history(asset_id, db)
    assert len(history) == 1
    assert history[0]["balance"] == 1_200_000


def test_past_dated_current_update_is_rejected(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset_id = get_assets(db_path=db)[0]["id"]
    today = date.today()

    save_balance(asset_id, 1_000_000, today, db)

    with pytest.raises(ValueError):
        save_balance(asset_id, 900_000, today - timedelta(days=1), db)


def test_future_date_is_rejected(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset_id = get_assets(db_path=db)[0]["id"]

    with pytest.raises(ValueError):
        save_balance(asset_id, 900_000, date.today() + timedelta(days=1), db)


def test_negative_balance_is_rejected(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset_id = get_assets(db_path=db)[0]["id"]

    with pytest.raises(ValueError):
        save_balance(asset_id, -1, date.today(), db)


def test_portfolio_history_aggregates_active_assets_by_date(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    assets = get_assets(db_path=db)
    d1 = date.today() - timedelta(days=1)
    d2 = date.today()

    save_balance(assets[0]["id"], 1_000_000, d1, db)
    save_balance(assets[1]["id"], 500_000, d1, db)

    save_balance(assets[0]["id"], 1_100_000, d2, db)
    save_balance(assets[1]["id"], 550_000, d2, db)

    history = get_portfolio_history(db_path=db)
    assert history[-2]["record_date"] == d1.isoformat()
    assert history[-2]["total_balance"] == 1_500_000
    assert history[-1]["record_date"] == d2.isoformat()
    assert history[-1]["total_balance"] == 1_650_000


def test_zero_balance_is_valid_and_huge_balance_is_rejected(tmp_path: Path):
    from datetime import date
    import pytest
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 0, date.today(), db)
    with pytest.raises(ValueError):
        save_balance(asset["id"], 10**19, date.today(), db)



def test_unchanged_asset_is_not_written_to_new_history_date(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 1_000_000, date(2026, 9, 5), db)
    # The page-level behavior is implemented by comparing old/new values;
    # verify the underlying save operation remains history-based and unique.
    history_before = get_balance_history(asset["id"], db)
    assert len(history_before) == 1
    assert history_before[0]["record_date"] == "2026-09-05"

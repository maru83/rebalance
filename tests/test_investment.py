from datetime import date
from pathlib import Path

import pytest

from core.asset import get_assets
from core.investment import (
    calculate_annual_investment,
    calculate_monthly_contributions,
    calculate_monthly_total,
    get_investment_plans,
    save_investment_plan,
)
from data.database import initialize_database


def test_save_and_get_investment_plans(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset = get_assets(db_path=db)[0]

    plan_id = save_investment_plan(
        plan_id=None,
        user_id=1,
        asset_id=asset["id"],
        plan_name="NISA毎月",
        frequency="monthly",
        amount=50000,
        db_path=db,
    )

    plans = get_investment_plans(db_path=db)
    assert len(plans) == 1
    assert plans[0]["id"] == plan_id
    assert plans[0]["amount"] == 50000


def test_monthly_and_bonus_contributions(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    assets = get_assets(db_path=db)

    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="NISA毎月", frequency="monthly", amount=50000, db_path=db
    )
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="NISA夏", frequency="yearly", amount=300000, month=6, db_path=db
    )
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[1]["id"],
        plan_name="国債夏", frequency="yearly", amount=100000, month=6, db_path=db
    )
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="NISA冬", frequency="yearly", amount=300000, month=12, db_path=db
    )

    plans = get_investment_plans(db_path=db)
    monthly = calculate_monthly_total(plans, year=date.today().year)

    assert monthly[1] == 50000
    assert monthly[6] == 450000
    assert monthly[12] == 350000
    assert calculate_annual_investment(plans, year=date.today().year) == (
        50000 * 12 + 300000 + 100000 + 300000
    )


def test_dc_monthly_is_included(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset = get_assets(db_path=db)[2]

    save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="DC毎月", frequency="monthly", amount=30000, db_path=db
    )

    plans = get_investment_plans(db_path=db)
    monthly = calculate_monthly_total(plans, year=date.today().year)

    assert all(monthly[m] == 30000 for m in range(1, 13))
    assert calculate_annual_investment(plans, year=date.today().year) == 360000


def test_plan_date_range(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset = get_assets(db_path=db)[0]

    save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="期間限定", frequency="monthly", amount=10000,
        start_date=date(date.today().year, 4, 1),
        end_date=date(date.today().year, 6, 30),
        db_path=db
    )

    plans = get_investment_plans(db_path=db)
    monthly = calculate_monthly_total(plans, year=date.today().year)

    assert monthly[3] == 0
    assert monthly[4] == 10000
    assert monthly[6] == 10000
    assert monthly[7] == 0


def test_one_time_plan(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)

    asset = get_assets(db_path=db)[0]

    save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="一回のみ", frequency="one_time", amount=200000,
        month=9, start_date=date(date.today().year, 9, 1), db_path=db
    )

    plans = get_investment_plans(db_path=db)
    monthly = calculate_monthly_total(plans, year=date.today().year)
    assert monthly[9] == 200000


def test_zero_amount_plan_is_valid(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    plan_id = save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="0円", frequency="monthly", amount=0, db_path=db,
    )
    assert plan_id > 0


def test_huge_amount_is_rejected(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    with pytest.raises(ValueError):
        save_investment_plan(
            plan_id=None, user_id=1, asset_id=asset["id"],
            plan_name="過大", frequency="monthly", amount=10**19, db_path=db,
        )

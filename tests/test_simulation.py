from datetime import date
from pathlib import Path

import pytest

from core.asset import get_assets, save_balance
from core.investment import save_investment_plan
from core.simulation import (
    aggregate_portfolio_results,
    calculate_monthly_rate,
    simulate_asset,
    simulate_portfolio,
)
from data.database import get_connection, initialize_database


def test_effective_monthly_rate():
    assert calculate_monthly_rate(0) == pytest.approx(0)
    assert (1 + calculate_monthly_rate(0.12)) ** 12 == pytest.approx(1.12)


def test_simulate_asset_zero_return_only_contributions():
    result = simulate_asset(
        asset_id=1,
        initial_balance=1_000_000,
        annual_rate=0,
        contributions={(2026, 10): 100_000, (2026, 11): 200_000},
        start_date=date(2026, 9, 5),
        months=3,
        current_age=25,
    )

    assert [r["ending_balance"] for r in result] == [1_100_000, 1_300_000, 1_300_000]
    assert result[-1]["cumulative_contribution"] == 300_000
    assert result[-1]["cumulative_gain"] == pytest.approx(0)
    assert result[0]["date"] == "2026-10-31"
    assert result[2]["age"] == 25


def test_simulate_asset_compounds_and_separates_gain():
    result = simulate_asset(
        asset_id=1,
        initial_balance=1_000_000,
        annual_rate=0.12,
        contributions={},
        start_date=date(2026, 1, 1),
        months=12,
        current_age=25,
    )

    expected = 1_000_000 * 1.12
    assert result[-1]["ending_balance"] == pytest.approx(expected)
    assert result[-1]["cumulative_contribution"] == 0
    assert result[-1]["cumulative_gain"] == pytest.approx(expected - 1_000_000)


def test_portfolio_simulation_uses_asset_specific_rates_and_plans(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)

    save_balance(assets[0]["id"], 1_000_000, date(2026, 9, 5), db)
    save_balance(assets[1]["id"], 500_000, date(2026, 9, 5), db)
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="NISA毎月", frequency="monthly", amount=100_000, db_path=db,
    )
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="NISA夏", frequency="yearly", amount=300_000, month=6, db_path=db,
    )
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[1]["id"],
        plan_name="国債冬", frequency="yearly", amount=200_000, month=12, db_path=db,
    )

    results = simulate_portfolio(
        current_age=25,
        years=1,
        start_date=date(2026, 9, 5),
        scenario="BASE",
        db_path=db,
    )
    portfolio = aggregate_portfolio_results(results)

    assert len(results) == 4 * 12
    assert len(portfolio) == 12
    october = next(r for r in portfolio if r["date"] == "2026-10-31")
    assert october["contribution"] == 100_000
    december = next(r for r in portfolio if r["date"] == "2026-12-31")
    assert december["contribution"] == 300_000


def test_simulation_runs_all_three_scenarios_and_does_not_write_db(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    save_balance(assets[0]["id"], 1_000_000, date(2026, 9, 5), db)

    before = get_connection(db).execute(
        "SELECT COUNT(*) AS c FROM asset_balance_history"
    ).fetchone()["c"]

    results = simulate_portfolio(
        current_age=25, years=1, start_date=date(2026, 9, 5), db_path=db
    )

    after = get_connection(db).execute(
        "SELECT COUNT(*) AS c FROM asset_balance_history"
    ).fetchone()["c"]
    scenarios = {row["scenario"] for row in results}
    assert scenarios == {"BEAR", "BASE", "BULL"}
    assert before == after


def test_target_age_sets_months():
    # Use a temporary DB so the test remains isolated from the app DB.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.db"
        initialize_database(path)
        results = simulate_portfolio(
            current_age=25,
            target_age=27,
            start_date=date(2026, 9, 5),
            scenario="BASE",
            db_path=path,
        )
        assert len(results) == 4 * 24
        assert max(r["age"] for r in results) == 27


def test_one_time_plan_occurs_only_in_its_year(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="一回のみ", frequency="one_time", amount=500_000,
        month=6, start_date=date(2027, 6, 1), db_path=db,
    )

    results = simulate_portfolio(
        current_age=25, years=2, start_date=date(2026, 9, 5), db_path=db
    )
    contributions = [
        r["contribution"] for r in results
        if r["asset_id"] == asset["id"] and r["scenario"] == "BASE"
    ]
    assert sum(contributions) == 500_000


def test_target_age_final_row_is_target_age(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    results = simulate_portfolio(
        current_age=25,
        target_age=27,
        start_date=date(2026, 9, 5),
        scenario="BASE",
        db_path=db,
    )
    portfolio = aggregate_portfolio_results(results)
    assert portfolio[-1]["age"] == 27


def test_manual_compound_with_monthly_contribution(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    save_balance(assets[0]["id"], 1_000_000, date(2026, 9, 5), db)
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=assets[0]["id"],
        plan_name="毎月", frequency="monthly", amount=100_000, db_path=db,
    )
    results = simulate_portfolio(
        current_age=25, years=1, start_date=date(2026, 9, 5),
        scenario="BASE", db_path=db,
    )
    portfolio = aggregate_portfolio_results(results)
    # BASE rate for the fund is 6%; 12 month-end contributions.
    r = (1.06) ** (1/12) - 1
    balance = 1_000_000
    for _ in range(12):
        balance = balance * (1 + r) + 100_000
    assert portfolio[-1]["ending_balance"] == pytest.approx(balance)
    assert portfolio[-1]["cumulative_contribution"] == 1_200_000



def test_what_if_changes_monthly_plan_without_writing_db(tmp_path: Path):
    from core.simulation import run_what_if
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 1_000_000, date(2026, 9, 5), db)
    save_investment_plan(
        plan_id=None, user_id=1, asset_id=asset["id"],
        plan_name="毎月", frequency="monthly", amount=50_000, db_path=db,
    )
    result = run_what_if(
        current_age=25, target_age=27, scenario="BASE",
        monthly_asset_id=asset["id"], what_if_monthly_amount=60_000,
        db_path=db,
    )
    assert result["current_monthly"] == 50_000
    assert result["what_if_monthly"] == 60_000
    assert result["forecast_difference"] > 0
    stored = get_connection(db).execute(
        "SELECT amount FROM investment_plans WHERE id = 1"
    ).fetchone()["amount"]
    assert stored == 50_000

from pathlib import Path

import pytest

from core.asset import get_assets, save_balance
from core.goal import calculate_required_monthly_investment, evaluate_goal, get_goals, save_goal
from core.investment import save_investment_plan
from data.database import initialize_database


def test_goal_crud(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    goal_id = save_goal(
        goal_id=None, user_id=1, goal_name="60歳5,000万円",
        target_age=60, target_amount=50_000_000, purpose="老後", db_path=db
    )
    goals = get_goals(user_id=1, db_path=db)
    assert goals[0]["id"] == goal_id
    assert goals[0]["target_amount"] == 50_000_000


def test_goal_evaluation_reaches_target_with_zero_return(tmp_path: Path, monkeypatch):
    db = tmp_path / "test.db"
    initialize_database(db)
    assets = get_assets(db_path=db)
    save_balance(assets[0]["id"], 1_000_000, __import__("datetime").date(2026, 9, 5), db)
    save_goal(goal_id=None, user_id=1, goal_name="27歳200万円", target_age=27, target_amount=2_000_000, db_path=db)
    # Make the base return zero for all assets so the assertion is deterministic.
    from data.database import get_connection
    conn = get_connection(db)
    conn.execute("UPDATE asset_return_assumptions SET annual_return_rate = 0 WHERE scenario_id = 2")
    conn.commit(); conn.close()
    save_investment_plan(plan_id=None, user_id=1, asset_id=assets[0]["id"], plan_name="毎月", frequency="monthly", amount=100_000, db_path=db)
    result = evaluate_goal(goal=get_goals(db_path=db)[0], current_age=25, scenario="BASE", db_path=db)
    assert result["forecast_amount"] == pytest.approx(3_400_000)
    assert result["status"] == "達成見込み"


def test_required_monthly_is_zero_when_current_plan_not_needed(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 10_000_000, __import__("datetime").date(2026, 9, 5), db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=asset["id"], plan_name="毎月", frequency="monthly", amount=100_000, db_path=db)
    goal = {"id": 1, "goal_name": "小目標", "target_age": 26, "target_amount": 1_000_000}
    result = calculate_required_monthly_investment(goal=goal, current_age=25, scenario="BASE", monthly_asset_id=asset["id"], db_path=db)
    assert result["required_monthly"] == 0


def test_required_monthly_keeps_bonus_and_returns_minimum_rounded(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_balance(asset["id"], 0, __import__("datetime").date(2026, 9, 5), db)
    # Base return = 0 to make expected required monthly easy to verify.
    from data.database import get_connection
    conn = get_connection(db)
    conn.execute("UPDATE asset_return_assumptions SET annual_return_rate = 0 WHERE scenario_id = 2")
    conn.commit(); conn.close()
    save_investment_plan(plan_id=None, user_id=1, asset_id=asset["id"], plan_name="毎月", frequency="monthly", amount=50_000, db_path=db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=asset["id"], plan_name="6月ボーナス", frequency="yearly", amount=300_000, month=6, db_path=db)
    save_investment_plan(plan_id=None, user_id=1, asset_id=asset["id"], plan_name="12月ボーナス", frequency="yearly", amount=300_000, month=12, db_path=db)
    goal = {"id": 1, "goal_name": "27歳1,800,000円", "target_age": 27, "target_amount": 1_800_000}
    result = calculate_required_monthly_investment(goal=goal, current_age=25, scenario="BASE", monthly_asset_id=asset["id"], db_path=db)
    # Current bonus contribution is 600k/year. Over two years: 1.2m, so exact monthly is 25k.
    assert result["required_monthly"] == 30_000
    assert result["current_monthly"] == 50_000
    assert result["difference"] == -20_000


def test_zero_target_amount_is_immediately_achieved(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    asset = get_assets(db_path=db)[0]
    save_goal(goal_id=None, user_id=1, goal_name="0円", target_age=26, target_amount=0, db_path=db)
    result = evaluate_goal(goal=get_goals(db_path=db)[0], current_age=25, scenario="BASE", db_path=db)
    assert result["status"] == "達成見込み"
    assert result["achievement_rate"] == 0.0


def test_goal_amount_too_large_is_rejected(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    with pytest.raises(ValueError):
        save_goal(goal_id=None, user_id=1, goal_name="過大", target_age=60, target_amount=10**19, db_path=db)


def test_goal_target_age_before_current_age_is_rejected_by_evaluation(tmp_path: Path):
    db = tmp_path / "test.db"
    initialize_database(db)
    goal = {"id": 1, "goal_name": "矛盾", "target_age": 24, "target_amount": 1_000_000}
    with pytest.raises(ValueError):
        evaluate_goal(goal=goal, current_age=25, scenario="BASE", db_path=db)

from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.display import format_amount, get_display_settings
from core.settings import get_settings
from core.goal import (
    calculate_required_monthly_investment,
    evaluate_goal,
    get_current_age,
    get_goals,
    save_goal,
    deactivate_goal,
)
from core.investment import get_investment_plans
from core.simulation import get_simulation_inputs
from data.database import DB_PATH

USER_ID = 1


settings = get_settings(USER_ID, DB_PATH)
_, DISPLAY_UNIT = get_display_settings(settings)

def yen(value: float | int) -> str:
    return format_amount(value, DISPLAY_UNIT)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


st.title("🎯 目標")
st.caption("目標年齢・目標資産額を設定し、現在の投資ペースでの達成見込みと必要月額を確認します。")

current_age = get_current_age(db_path=DB_PATH)
if current_age is None:
    st.warning("初回設定が未完了です。設定画面で現在年齢を登録してください。")
    if st.button("設定画面を開く", type="primary"):
        st.switch_page("pages/6_Settings.py")
    st.stop()

# --- Goal CRUD ---
goals = get_goals(user_id=USER_ID, active_only=False, db_path=DB_PATH)
active_goals = [g for g in goals if g["is_active"] == 1]

st.subheader("目標設定")
with st.form("goal_form"):
    existing_options = [{"id": None, "goal_name": "新しい目標", "target_age": int(current_age) + 10, "target_amount": 50_000_000, "purpose": ""}]
    existing_options += active_goals
    selected = st.selectbox(
        "登録・更新する目標",
        existing_options,
        format_func=lambda g: "新しい目標" if g["id"] is None else f"{g['goal_name']}（{g['target_age']}歳）",
    )
    c1, c2 = st.columns(2)
    goal_name = c1.text_input("目標名", value=selected.get("goal_name", ""), disabled=selected["id"] is None and False)
    target_age = c2.number_input("目標年齢", min_value=max(1, int(current_age) + 1), max_value=150, value=max(int(current_age) + 1, int(selected.get("target_age", int(current_age) + 10))), step=1)
    target_amount = st.number_input("目標資産額（円）", min_value=0, value=int(selected.get("target_amount", 50_000_000)), step=100_000)
    purpose = st.text_input("目的（任意）", value=selected.get("purpose") or "")
    submitted = st.form_submit_button("目標を保存", type="primary", use_container_width=True)

if submitted:
    try:
        save_goal(
            goal_id=selected["id"],
            user_id=USER_ID,
            goal_name=goal_name,
            target_age=int(target_age),
            target_amount=int(target_amount),
            purpose=purpose or None,
            db_path=DB_PATH,
        )
        st.success("目標を保存しました。")
        st.rerun()
    except Exception as exc:
        st.error(f"目標の保存に失敗しました: {exc}")

if active_goals:
    st.subheader("登録済みの目標")
    for goal in active_goals:
        col1, col2 = st.columns([5, 1])
        col1.write(f"**{goal['goal_name']}**　{goal['target_age']}歳　{yen(goal['target_amount'])}" + (f"　{goal['purpose']}" if goal['purpose'] else ""))
        if col2.button("無効化", key=f"deactivate_{goal['id']}"):
            deactivate_goal(goal["id"], user_id=USER_ID, db_path=DB_PATH)
            st.success("目標を無効化しました。")
            st.rerun()

# --- Assessment ---
if not active_goals:
    st.info("まず目標を1件以上登録してください。")
    st.stop()

st.divider()
st.subheader("目標達成状況")
selected_goal = st.selectbox(
    "評価する目標",
    active_goals,
    format_func=lambda g: f"{g['goal_name']}（{g['target_age']}歳・{yen(g['target_amount'])}）",
)
scenario_labels = {"BEAR": "悲観", "BASE": "標準", "BULL": "楽観"}
scenario = st.selectbox("判定シナリオ", list(scenario_labels), index=1, format_func=lambda x: scenario_labels[x])

try:
    evaluation = evaluate_goal(goal=selected_goal, current_age=int(current_age), scenario=scenario, db_path=DB_PATH)
except Exception as exc:
    st.error(f"目標達成判定に失敗しました: {exc}")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("目標資産", yen(evaluation["target_amount"]))
k2.metric("将来資産", yen(evaluation["forecast_amount"]))
k3.metric("達成率", pct(evaluation["achievement_rate"]))
k4.metric("目標との差額", yen(evaluation["gap"]))

if evaluation["status"] == "達成見込み":
    st.success("目標達成見込み")
else:
    st.warning("現在の投資ペースでは目標未達の可能性があります。")

# --- Required monthly calculation ---
st.subheader("必要月額投資額")
inputs = get_simulation_inputs(user_id=USER_ID, db_path=DB_PATH)
plans = get_investment_plans(user_id=USER_ID, active_only=True, db_path=DB_PATH)
monthly_assets = []
for p in plans:
    if p["frequency"] == "monthly" and int(p["asset_id"]) not in [x[0] for x in monthly_assets]:
        monthly_assets.append((int(p["asset_id"]), p["asset_name"]))

if not monthly_assets:
    st.info("必要月額を逆算するには、対象資産の毎月投資計画が必要です。")
else:
    monthly_asset_id, monthly_asset_name = st.selectbox(
        "月額を調整する資産",
        monthly_assets,
        format_func=lambda x: x[1],
    )
    st.caption("既存のボーナス・毎年投資は維持し、選択した資産の毎月投資額だけを変化させて逆算します。")
    try:
        required = calculate_required_monthly_investment(
            goal=selected_goal,
            current_age=int(current_age),
            scenario=scenario,
            monthly_asset_id=monthly_asset_id,
            db_path=DB_PATH,
        )
        if not required["calculable"]:
            st.error("設定した上限額でも目標に届かないため、必要月額を計算できません。")
        else:
            r1, r2, r3 = st.columns(3)
            r1.metric("現在の月額", yen(required["current_monthly"]))
            r2.metric("必要月額", yen(required["required_monthly"]))
            r3.metric("差額", yen(required["difference"]))
            if required["difference"] <= 0:
                st.success("現在の月額投資で目標達成可能です。")
            else:
                st.info(f"目標達成には、月額を約 {yen(required['difference'])} 増やす必要があります。")
    except Exception as exc:
        st.error(f"必要月額の計算に失敗しました: {exc}")

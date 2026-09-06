from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core.goal import get_current_age, get_goals
from core.display import format_amount, get_display_settings
from core.settings import get_settings
from core.simulation import aggregate_portfolio_results, get_simulation_inputs, run_what_if, simulate_portfolio
from data.database import DB_PATH

USER_ID = 1



settings = get_settings(USER_ID, DB_PATH)
_, DISPLAY_UNIT = get_display_settings(settings)

def yen(value: float | int) -> str:
    return format_amount(value, DISPLAY_UNIT)


def build_annual_summary(portfolio: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(portfolio)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    # Keep the final month in each calendar year; this makes the long-term
    # trend readable while the engine itself remains monthly.
    annual = (
        df.sort_values("date")
        .groupby(["scenario", "year"], as_index=False)
        .last()
    )
    return annual


st.title("📈 シミュレーション")
st.caption("現在の資産・投資計画・資産別想定利回りから将来資産を試算します。")

current_age = get_current_age()
if current_age is None:
    st.warning("初回設定が未完了です。設定画面で現在年齢を登録してください。")
    if st.button("設定画面を開く", type="primary"):
        st.switch_page("pages/6_Settings.py")
    st.stop()

period = st.radio(
    "シミュレーション期間",
    ["10年", "20年", "30年", "目標年齢まで"],
    horizontal=True,
)

scenario_labels = {"BEAR": "悲観", "BASE": "標準", "BULL": "楽観"}
scenario = st.selectbox("シナリオ", ["BASE", "BEAR", "BULL"], format_func=lambda x: scenario_labels[x])

active_goals = get_goals(user_id=USER_ID, active_only=True, db_path=DB_PATH)
target_age = None
if period == "目標年齢まで":
    valid_goals = [g for g in active_goals if g["target_age"] > current_age]
    if not valid_goals:
        st.error("現在年齢より後の有効な目標年齢がありません。目標画面で目標を設定してください。")
        st.stop()
    selected_goal = st.selectbox(
        "目標",
        valid_goals,
        format_func=lambda g: f"{g['goal_name']}（{g['target_age']}歳・{yen(g['target_amount'])}）",
    )
    target_age = int(selected_goal["target_age"])

try:
    inputs = get_simulation_inputs(user_id=USER_ID, db_path=DB_PATH)
    balances = {int(row["asset_id"]): float(row["balance"] or 0) for row in inputs["assets"]}
    current_assets = sum(balances.values())
    annual_plan = 0
    # Annual planned amount is calculated from the same active plans used by the engine.
    from core.investment import calculate_annual_investment
    annual_plan = calculate_annual_investment(inputs["plans"], year=date.today().year)
    if not any(float(row["balance"] or 0) > 0 for row in inputs["assets"]):
        st.info("現在残高が未登録、またはすべて0円です。0円としてシミュレーションします。")
    if not inputs["plans"]:
        st.info("投資計画が未登録です。追加投資0円としてシミュレーションします。")
except Exception as exc:
    st.error(f"シミュレーション入力の取得に失敗しました: {exc}")
    st.stop()

st.divider()

col1, col2 = st.columns(2)
col1.metric("現在資産", yen(current_assets))
col2.metric("年間投資予定額", yen(annual_plan))

if st.button("シミュレーション実行", type="primary", use_container_width=True):
    with st.spinner("シミュレーションを計算しています…"):
        try:
            years = None if target_age is not None else int(period.replace("年", ""))
            results = simulate_portfolio(
                user_id=USER_ID,
                current_age=int(current_age),
                years=years,
                target_age=target_age,
                scenario=None,
                db_path=DB_PATH,
            )
            portfolio = aggregate_portfolio_results(results)
            st.session_state["simulation_results"] = results
            st.session_state["simulation_portfolio"] = portfolio
            st.session_state["simulation_selected_scenario"] = scenario
            st.session_state["simulation_target_age"] = target_age
            st.success("シミュレーションを実行しました。")
        except Exception as exc:
            st.error(f"シミュレーションに失敗しました: {exc}")

portfolio = st.session_state.get("simulation_portfolio")
results = st.session_state.get("simulation_results")
if not portfolio:
    st.info("条件を選択して「シミュレーション実行」を押してください。")
    st.stop()

selected_scenario = st.session_state.get("simulation_selected_scenario", scenario)
scenario_result = [r for r in portfolio if r["scenario"] == selected_scenario]
scenario_result = sorted(scenario_result, key=lambda r: r["date"])
final = scenario_result[-1]

st.subheader(f"{scenario_labels[selected_scenario]}シナリオ：将来資産")

k1, k2, k3, k4 = st.columns(4)
k1.metric("現在資産", yen(current_assets))
k2.metric("累計追加投資", yen(final["cumulative_contribution"]))
k3.metric("累計運用益", yen(final["cumulative_gain"]))
k4.metric("将来資産", yen(final["ending_balance"]))

st.caption(f"最終時点：{final['date']} / {int(final['age'])}歳")

st.subheader("将来資産推移")
trend_df = pd.DataFrame(scenario_result)
trend_df["年齢"] = trend_df["age"].astype(int)
trend_df["資産額"] = trend_df["ending_balance"]
fig = px.line(trend_df, x="年齢", y="資産額", markers=False)
fig.update_layout(xaxis_title="年齢", yaxis_title="資産額（円）", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

st.subheader("シナリオ比較")
all_portfolio = sorted(portfolio, key=lambda r: (r["date"], r["scenario"]))
final_by_scenario = {}
for code in scenario_labels:
    rows = [r for r in all_portfolio if r["scenario"] == code]
    if rows:
        final_by_scenario[code] = rows[-1]
comparison_df = pd.DataFrame(
    [{"シナリオ": scenario_labels[c], "将来資産": final_by_scenario[c]["ending_balance"]} for c in scenario_labels if c in final_by_scenario]
)
st.bar_chart(comparison_df.set_index("シナリオ"))

st.subheader("資産別構成")
asset_rows = [r for r in results if r["scenario"] == selected_scenario and r["date"] == final["date"]]
asset_name_map = {int(r["asset_id"]): r["asset_name"] for r in inputs["assets"]}
composition_df = pd.DataFrame(
    [
        {"資産": asset_name_map.get(int(r["asset_id"]), str(r["asset_id"])), "将来資産": r["ending_balance"]}
        for r in asset_rows
    ]
)
if not composition_df.empty:
    st.plotly_chart(
        px.pie(composition_df, names="資産", values="将来資産", hole=0.35),
        use_container_width=True,
    )
    st.dataframe(composition_df, use_container_width=True)

st.subheader("🔄 What-if：投資額を変更した場合")
st.caption("現在の投資計画は変更せず、選択した資産の毎月投資予定額だけを一時的に変更して将来資産を比較します。")
monthly_assets = []
for p in inputs["plans"]:
    if p["frequency"] == "monthly" and int(p["asset_id"]) not in [x[0] for x in monthly_assets]:
        monthly_assets.append((int(p["asset_id"]), p["asset_name"]))
what_if_target_age = target_age if target_age is not None else int(current_age) + int(period.replace("年", ""))
if monthly_assets:
    w1, w2 = st.columns(2)
    with w1:
        what_if_asset_id, what_if_asset_name = st.selectbox("変更する資産", monthly_assets, format_func=lambda x: x[1], key="what_if_asset")
    current_monthly = sum(int(p["amount"]) for p in inputs["plans"] if int(p["asset_id"]) == what_if_asset_id and p["frequency"] == "monthly")
    with w2:
        what_if_amount = st.number_input("What-if月間投資予定額（円）", min_value=0, value=current_monthly, step=10000, key="what_if_amount")
    if st.button("What-ifを計算", key="run_what_if", use_container_width=True):
        try:
            what_if_result = run_what_if(current_age=int(current_age), target_age=what_if_target_age, scenario=selected_scenario, monthly_asset_id=what_if_asset_id, what_if_monthly_amount=int(what_if_amount), db_path=DB_PATH)
            w3, w4, w5 = st.columns(3)
            w3.metric("現在の月間投資予定額", yen(what_if_result["current_monthly"]))
            w4.metric("What-if月間投資予定額", yen(what_if_result["what_if_monthly"]))
            w5.metric("将来資産の差額", yen(what_if_result["forecast_difference"]))
            st.info(f"{what_if_asset_name}を月{yen(what_if_result['current_monthly'])}から月{yen(what_if_result['what_if_monthly'])}に変更すると、{what_if_target_age}歳時点の将来資産は{yen(what_if_result['forecast_difference'])}変化する試算です。")
        except Exception as exc:
            st.error(f"What-if計算に失敗しました: {exc}")
else:
    st.info("What-ifを利用するには、毎月の投資予定が1件以上必要です。")

st.subheader("現在資産・追加投資・運用益")
source_df = pd.DataFrame(
    [
        {"項目": "現在資産", "金額": current_assets},
        {"項目": "累計追加投資", "金額": final["cumulative_contribution"]},
        {"項目": "累計運用益", "金額": final["cumulative_gain"]},
    ]
)
st.bar_chart(source_df.set_index("項目"))

st.subheader("シミュレーション結果（年次）")
annual_df = build_annual_summary(portfolio)
if not annual_df.empty:
    display_df = annual_df[["year", "age", "scenario", "ending_balance", "cumulative_contribution", "cumulative_gain"]].copy()
    display_df.columns = ["年", "年齢", "シナリオ", "将来資産", "累計追加投資", "累計運用益"]
    display_df["シナリオ"] = display_df["シナリオ"].map(scenario_labels)
    st.dataframe(display_df, use_container_width=True)

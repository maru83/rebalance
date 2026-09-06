from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from core.dashboard import (
    get_asset_history,
    get_assets_by_purpose,
    get_annual_investment,
    get_goal_status,
    get_investment_breakdown,
    get_latest_update_date,
    get_monthly_investment,
    get_simulation_summary,
    get_total_assets,
)
from core.goal import get_current_age
from core.display import format_amount, get_display_settings
from core.settings import get_settings
from data.database import DB_PATH

USER_ID = 1

st.set_page_config(page_title="Dashboard | 資産形成ナビ", page_icon="🏠", layout="wide")


settings = get_settings(USER_ID, DB_PATH)
_, DISPLAY_UNIT = get_display_settings(settings)

def yen(value: float | int) -> str:
    return format_amount(value, DISPLAY_UNIT)


def yen_delta(value: float | int) -> str:
    return f"{int(round(value)):+,}円"


st.title("🏠 Dashboard")
st.caption("資産形成の現在地と、これからの見通しをひと目で確認できます。")

try:
    total = get_total_assets(USER_ID, DB_PATH)
    purposes = get_assets_by_purpose(USER_ID, DB_PATH)
    annual = get_annual_investment(USER_ID, db_path=DB_PATH)
    monthly = get_monthly_investment(USER_ID, db_path=DB_PATH)
    latest = get_latest_update_date(USER_ID, DB_PATH)
except Exception as exc:
    st.error("Dashboardのデータ取得に失敗しました。データを確認してください。")
    st.exception(exc)
    st.stop()

current_age = get_current_age(db_path=DB_PATH, user_id=USER_ID)
try:
    goal_status = get_goal_status(USER_ID, DB_PATH)
except Exception as exc:
    goal_status = None
    st.warning(f"目標達成状況を取得できませんでした: {exc}")

try:
    forecast = get_simulation_summary(USER_ID, DB_PATH)
except Exception:
    forecast = None

# ============================================================
# 1. 現在地：最重要KPIだけを最上段に配置
# ============================================================
st.subheader("現在の資産状況")
k1, k2, k3, k4 = st.columns(4)
k1.metric("総金融資産", yen(total))
k2.metric("年間投資予定額", yen(annual))
k3.metric("今月の投資予定額", yen(monthly))
if goal_status:
    k4.metric("目標資産額", yen(goal_status["target_amount"]))
else:
    k4.metric("目標資産額", "未設定")

# ============================================================
# 2. 目標・将来予測：意思決定に直結する情報を上に
# ============================================================
st.divider()
st.subheader("🎯 目標と将来予測")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**目標達成状況**")
    if goal_status:
        status = goal_status["status"]
        if status == "達成見込み":
            st.success(f"✓ {status}")
        else:
            st.warning(f"△ {status}")
        g1, g2, g3 = st.columns(3)
        g1.metric("目標", yen(goal_status["target_amount"]))
        g2.metric("予想", yen(goal_status["forecast_amount"]))
        g3.metric("達成率", f"{goal_status['achievement_rate'] * 100:.1f}%")
        st.caption(
            f"{goal_status['goal_name']} / {goal_status['target_age']}歳 / "
            f"差額 {yen_delta(goal_status['gap'])}"
        )
    else:
        st.info("目標を登録すると、達成見込みをここで確認できます。")

with c2:
    st.markdown("**標準シナリオの将来予測**")
    if forecast:
        f1, f2, f3 = st.columns(3)
        f1.metric(forecast["horizon_label"], yen(forecast["forecast_amount"]))
        f2.metric("累計追加投資", yen(forecast["cumulative_contribution"]))
        f3.metric("累計運用益", yen(forecast["cumulative_gain"]))
        st.caption("現在の投資計画を維持した場合の標準シナリオです。")
    elif current_age is None:
        st.info("設定画面で現在年齢を登録すると将来予測を表示できます。")
    else:
        st.info("将来予測に必要なデータがありません。")

# ============================================================
# 3. 資産推移：Dashboardでは概要だけ
# ============================================================
st.divider()
st.subheader("📈 資産推移")
history = get_asset_history(USER_ID, DB_PATH)
if history:
    df = pd.DataFrame(history)
    df["record_date"] = pd.to_datetime(df["record_date"])
    fig = px.line(df, x="record_date", y="total_balance", markers=True)
    fig.update_layout(
        xaxis_title="",
        yaxis_title="総資産（円）",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=20, b=20),
        height=360,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("詳細な期間比較・資産別推移は「Assets」から確認できます。")
else:
    st.info("資産履歴がまだありません。Assetsから残高を登録してください。")

# ============================================================
# 4. 資産の内訳：2つの情報をコンパクトに
# ============================================================
st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("💰 目的別資産")
    purpose_rows = [
        {"目的": "資産形成資産", "残高": purposes["asset_formation"]},
        {"目的": "老後資産", "残高": purposes["retirement"]},
        {"目的": "生活防衛資金", "残高": purposes["emergency_fund"]},
    ]
    pdf = pd.DataFrame(purpose_rows)
    pdf = pdf[pdf["残高"] > 0]
    if not pdf.empty:
        fig = px.pie(pdf, names="目的", values="残高", hole=0.5)
        fig.update_traces(textinfo="label+percent")
        fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=300)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("現在残高が登録されていません。")

with c2:
    st.subheader("📅 年間投資予定額")
    breakdown = get_investment_breakdown(USER_ID, db_path=DB_PATH)
    if breakdown:
        bdf = pd.DataFrame(breakdown)
        bdf = bdf.rename(columns={"asset_name": "資産", "annual_investment": "年間投資予定額"})
        bdf["年間投資予定額"] = bdf["年間投資予定額"].map(yen)
        st.dataframe(bdf[["資産", "年間投資予定額"]], use_container_width=True)
    else:
        st.info("投資計画が登録されていません。")

# ============================================================
# 5. フッター：更新導線を控えめに
# ============================================================
st.divider()
footer_col, action_col = st.columns([5, 1])
footer_col.caption(f"最終更新日：{latest or '未登録'}")
if action_col.button("資産を更新", type="primary", use_container_width=True):
    st.switch_page("pages/2_Assets.py")

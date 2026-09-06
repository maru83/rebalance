from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.asset import get_assets
from core.investment import (
    calculate_annual_investment,
    calculate_monthly_contributions,
    calculate_monthly_total,
    deactivate_investment_plan,
    get_investment_plans,
    save_investment_plan,
)
from data.database import DB_PATH, database_exists, initialize_database

USER_ID = 1

st.set_page_config(
    page_title="投資計画 | 資産形成ナビ",
    page_icon="📅",
    layout="wide",
)
st.title("📅 投資計画")
st.caption("毎月・ボーナス月など、今後の投資予定を登録します。")

if not database_exists(DB_PATH):
    initialize_database(DB_PATH)

assets = get_assets(USER_ID, db_path=DB_PATH)
plans = get_investment_plans(USER_ID, db_path=DB_PATH)
current_year = date.today().year

asset_map = {int(a["id"]): a for a in assets}
asset_options = [(int(a["id"]), a["asset_name"]) for a in assets]

# -----------------------------
# Existing plans
# -----------------------------
st.subheader("現在の投資計画")

if plans:
    rows = []
    for p in plans:
        if p["frequency"] == "monthly":
            frequency_label = "毎月"
        elif p["frequency"] == "yearly":
            frequency_label = f"{p['month']}月"
        else:
            frequency_label = "1回"

        rows.append(
            {
                "ID": p["id"],
                "資産": p["asset_name"],
                "計画名": p["plan_name"],
                "頻度": frequency_label,
                "金額": f"{int(p['amount']):,}円",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("投資計画はまだ登録されていません。")

# -----------------------------
# Add / update
# -----------------------------
st.subheader("投資計画を登録・更新")

plan_choices = [(None, "新しい投資計画")]
plan_choices += [
    (int(p["id"]), f"{p['plan_name']}（{p['asset_name']}）") for p in plans
]
selected_plan_id = st.selectbox(
    "操作対象",
    options=plan_choices,
    format_func=lambda x: x[1],
    key="investment_plan_target",
)[0]
selected_plan = next((p for p in plans if int(p["id"]) == selected_plan_id), None)

frequency_default = selected_plan["frequency"] if selected_plan else "monthly"
frequency = st.selectbox(
    "頻度",
    options=["monthly", "yearly", "one_time"],
    index=["monthly", "yearly", "one_time"].index(frequency_default),
    format_func=lambda x: {
        "monthly": "毎月",
        "yearly": "毎年指定月",
        "one_time": "1回のみ",
    }[x],
    key=f"investment_frequency_{selected_plan_id}",
)

month = None
if frequency in {"yearly", "one_time"}:
    default_month = int(selected_plan["month"]) if selected_plan and selected_plan["month"] else 6
    month = st.selectbox(
        "投資月",
        options=list(range(1, 13)),
        index=default_month - 1,
        format_func=lambda m: f"{m}月",
        key=f"investment_month_{selected_plan_id}",
    )

with st.form("investment_plan_form"):
    default_asset_id = int(selected_plan["asset_id"]) if selected_plan else asset_options[0][0]
    asset_index = next(
        (i for i, option in enumerate(asset_options) if option[0] == default_asset_id), 0
    )
    selected_asset = st.selectbox(
        "投資先資産",
        options=asset_options,
        index=asset_index,
        format_func=lambda x: x[1],
    )
    plan_name = st.text_input(
        "計画名",
        value=selected_plan["plan_name"] if selected_plan else "",
        placeholder="例：NISA毎月積立",
    )
    amount = st.number_input(
        "金額（円）",
        min_value=0,
        value=int(selected_plan["amount"]) if selected_plan else 50000,
        step=10000,
    )
    start_value = date.fromisoformat(selected_plan["start_date"]) if selected_plan and selected_plan["start_date"] else None
    end_value = date.fromisoformat(selected_plan["end_date"]) if selected_plan and selected_plan["end_date"] else None
    start_date = st.date_input("開始日（任意）", value=start_value)
    end_date = st.date_input("終了日（任意）", value=end_value)

    submitted = st.form_submit_button(
        "💾 投資計画を保存",
        type="primary",
    )

if submitted:
    try:
        save_investment_plan(
            plan_id=selected_plan_id,
            user_id=USER_ID,
            asset_id=int(selected_asset[0]),
            plan_name=plan_name,
            frequency=frequency,
            amount=int(amount),
            month=month,
            start_date=start_date,
            end_date=end_date,
            db_path=DB_PATH,
        )
        st.success("投資計画を保存しました。")
        st.rerun()
    except Exception as exc:
        st.error(f"保存に失敗しました：{exc}")

# -----------------------------
# Deactivate
# -----------------------------
if plans:
    st.subheader("投資計画を停止")
    deactivate_options = [
        (int(p["id"]), f"{p['plan_name']}（{p['asset_name']}）")
        for p in plans
    ]

    selected_plan = st.selectbox(
        "停止する計画",
        options=deactivate_options,
        format_func=lambda x: x[1],
    )

    if st.button("この投資計画を停止"):
        try:
            deactivate_investment_plan(selected_plan[0], USER_ID, DB_PATH)
            st.success("投資計画を停止しました。")
            st.rerun()
        except Exception as exc:
            st.error(f"停止に失敗しました：{exc}")

# -----------------------------
# Annual calculation / calendar
# -----------------------------
st.divider()
st.header("📊 年間投資予定額")

plans = get_investment_plans(USER_ID, db_path=DB_PATH)
annual = calculate_annual_investment(plans, year=current_year)
monthly = calculate_monthly_total(plans, year=current_year)
monthly_by_asset = calculate_monthly_contributions(plans, year=current_year)

col1, col2 = st.columns(2)
col1.metric("年間投資予定額", f"{annual:,}円")
col2.metric("平均月額", f"{annual / 12:,.0f}円")

calendar_rows = []
for month in range(1, 13):
    by_asset = monthly_by_asset[month]
    breakdown = []
    for asset_id, amount in sorted(by_asset.items()):
        breakdown.append(
            f"{asset_map[asset_id]['asset_name']}：{amount:,}円"
        )

    calendar_rows.append(
        {
            "月": f"{month}月",
            "投資予定額": monthly[month],
            "内訳": " / ".join(breakdown) if breakdown else "—",
        }
    )

calendar_df = pd.DataFrame(calendar_rows)
calendar_df["投資予定額"] = calendar_df["投資予定額"].map(
    lambda x: f"{int(x):,}円"
)
st.dataframe(calendar_df, use_container_width=True)

if annual > 100_000_000:
    st.warning("年間投資予定額が1億円を超えています。入力内容を確認してください。")

st.caption(
    "年間投資予定額は、登録した投資ルールから自動計算した予定額です。"
    "投資実績との比較はV1.1 MVPの対象外です。"
)

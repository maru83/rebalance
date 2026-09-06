from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core.asset import get_balance_history, get_current_balances, get_assets, save_balance
from data.database import DB_PATH, database_exists, initialize_database

USER_ID = 1

st.set_page_config(page_title="現在の資産 | 資産形成ナビ", page_icon="💰", layout="wide")
st.title("💰 現在の資産")

if not database_exists(DB_PATH):
    initialize_database(DB_PATH)

balances = get_current_balances(USER_ID, DB_PATH)

if not balances:
    st.warning("管理対象の資産がありません。")
    st.stop()

# -----------------------------
# Current balance update
# -----------------------------
st.caption("前回の残高を自動表示し、変更した資産だけ更新できます。")

latest_dates = [row["as_of_date"] for row in balances if row["as_of_date"]]
default_date = date.fromisoformat(max(latest_dates)) if latest_dates else date.today()

record_date = st.date_input(
    "基準日",
    value=min(default_date, date.today()),
    max_value=date.today(),
    help="未来日は指定できません。既存の現在残高より過去の日付も指定できません。",
)

with st.form("asset_balance_form"):
    values: dict[int, int] = {}

    for row in balances:
        asset_id = int(row["asset_id"])
        previous = int(row["balance"] or 0)

        st.markdown(f"**{row['asset_name']}**　{row['institution_name']}")
        values[asset_id] = st.number_input(
            "現在残高（円）",
            min_value=0,
            value=previous,
            step=10000,
            key=f"balance_{asset_id}",
        )

        if row["as_of_date"]:
            st.caption(
                f"前回更新日：{row['as_of_date']} / 前回残高：{previous:,}円"
            )
        else:
            st.caption("前回残高：未登録")

    submitted = st.form_submit_button("💾 資産残高を保存", type="primary")

if submitted:
    errors: list[str] = []

    for row in balances:
        if row["as_of_date"] and record_date.isoformat() < row["as_of_date"]:
            errors.append(
                f"{row['asset_name']}：基準日 {record_date.isoformat()} は、"
                f"現在の更新日 {row['as_of_date']} より過去です。"
            )

    if errors:
        for message in errors:
            st.error(message)
    else:
        try:
            changed_count = 0
            for row in balances:
                asset_id = int(row["asset_id"])
                previous = row["balance"]
                balance = values[asset_id]
                # Unchanged assets keep their existing as-of date and do not
                # create a redundant history row. Initial 0円 can be recorded.
                if previous is None or int(previous) != int(balance):
                    save_balance(asset_id, balance, record_date, DB_PATH)
                    changed_count += 1
            if changed_count:
                st.success(f"{changed_count}件の資産残高を更新しました。")
            else:
                st.info("変更された資産はありません。履歴も追加していません。")
            st.rerun()
        except Exception as exc:
            st.error(f"保存に失敗しました：{exc}")

st.divider()

# -----------------------------
# Detailed history
# -----------------------------
st.divider()
st.header("📈 資産推移")
st.caption(
    "期間や資産を切り替えて、残高の推移を詳しく確認できます。"
    "履歴の正本は asset_balance_history です。"
)

from core.history import (
    get_asset_history_detail,
    get_history_date_range,
    resolve_history_start_date,
)

history_min, history_max = get_history_date_range(USER_ID, DB_PATH)

if history_min is None or history_max is None:
    st.info("資産履歴がまだありません。現在の資産画面から残高を登録してください。")
else:
    period_options = ["3か月", "6か月", "1年", "全期間", "指定期間"]
    period = st.radio(
        "表示期間",
        period_options,
        horizontal=True,
        index=3,
        key="history_period",
    )

    if period == "指定期間":
        c1, c2 = st.columns(2)
        selected_start = c1.date_input(
            "開始日", value=history_min, min_value=history_min, max_value=history_max
        )
        selected_end = c2.date_input(
            "終了日", value=history_max, min_value=history_min, max_value=history_max
        )
        if selected_start > selected_end:
            st.error("開始日は終了日以前にしてください。")
            st.stop()
    else:
        selected_end = history_max
        selected_start = resolve_history_start_date(
            selected_end, period, history_min
        )

    asset_options = [
        (int(row["asset_id"]), f"{row['asset_name']}（{row['institution_name']}）")
        for row in balances
    ]
    selected_assets = st.multiselect(
        "表示する資産",
        options=asset_options,
        default=asset_options,
        format_func=lambda x: x[1],
        key="history_assets",
    )

    if not selected_assets:
        st.info("表示する資産を1つ以上選択してください。")
    else:
        selected_ids = [asset_id for asset_id, _ in selected_assets]
        detail = get_asset_history_detail(
            USER_ID,
            asset_ids=selected_ids,
            start_date=selected_start,
            end_date=selected_end,
            db_path=DB_PATH,
        )

        if not detail:
            st.info("選択した期間・資産に該当する履歴がありません。")
        else:
            detail_df = pd.DataFrame(detail)
            detail_df["record_date"] = pd.to_datetime(detail_df["record_date"])
            detail_df["balance"] = detail_df["balance"].astype(int)

            # Summary KPIs for the selected period.
            first_by_asset = (
                detail_df.sort_values("record_date")
                .groupby("asset_id", as_index=False)
                .first()
            )
            last_by_asset = (
                detail_df.sort_values("record_date")
                .groupby("asset_id", as_index=False)
                .last()
            )
            first_total = int(first_by_asset["balance"].sum())
            last_total = int(last_by_asset["balance"].sum())
            change_total = last_total - first_total

            c1, c2, c3 = st.columns(3)
            c1.metric("期間開始時の残高", f"{first_total:,}円")
            c2.metric("期間終了時の残高", f"{last_total:,}円")
            c3.metric("期間中の増減", f"{change_total:+,}円")

            st.subheader("資産別の残高推移")
            pivot_df = detail_df.pivot_table(
                index="record_date",
                columns="asset_name",
                values="balance",
                aggfunc="last",
            ).sort_index()
            st.line_chart(pivot_df, height=380)

            st.subheader("選択資産の推移")
            display_summary = (
                detail_df.sort_values("record_date")
                .groupby(["asset_id", "asset_name", "institution_name"], as_index=False)
                .agg(
                    開始残高=("balance", "first"),
                    終了残高=("balance", "last"),
                    記録件数=("balance", "count"),
                )
            )
            display_summary["増減"] = (
                display_summary["終了残高"] - display_summary["開始残高"]
            )
            display_summary = display_summary[
                ["asset_name", "institution_name", "開始残高", "終了残高", "増減", "記録件数"]
            ].rename(
                columns={
                    "asset_name": "資産",
                    "institution_name": "金融機関",
                }
            )
            for col in ["開始残高", "終了残高", "増減"]:
                display_summary[col] = display_summary[col].map(lambda x: f"{int(x):+,}円")
            st.dataframe(display_summary, use_container_width=True)

            st.subheader("履歴一覧")
            history_table = detail_df[
                ["record_date", "asset_name", "institution_name", "balance"]
            ].copy()
            history_table["record_date"] = history_table["record_date"].dt.strftime("%Y-%m-%d")
            history_table["balance"] = history_table["balance"].map(lambda x: f"{int(x):,}円")
            history_table = history_table.rename(
                columns={
                    "record_date": "記録日",
                    "asset_name": "資産",
                    "institution_name": "金融機関",
                    "balance": "残高",
                }
            )
            st.dataframe(history_table, use_container_width=True)

# -----------------------------
# All-asset history summary
# -----------------------------
st.divider()
st.subheader("📊 全資産の履歴状況")

asset_master = get_assets(USER_ID, db_path=DB_PATH)
summary_rows = []

for asset in asset_master:
    h = get_balance_history(int(asset["id"]), DB_PATH)
    summary_rows.append(
        {
            "資産": asset["asset_name"],
            "金融機関": asset["institution_name"],
            "記録件数": len(h),
            "最終記録日": h[-1]["record_date"] if h else "未登録",
            "最終残高": int(h[-1]["balance"]) if h else 0,
        }
    )

summary_df = pd.DataFrame(summary_rows)
summary_df["最終残高"] = summary_df["最終残高"].map(lambda x: f"{x:,}円")
st.dataframe(summary_df, use_container_width=True)

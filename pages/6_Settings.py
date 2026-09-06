from __future__ import annotations

import pandas as pd
import streamlit as st

from core.settings import get_return_assumptions, get_settings, save_return_assumptions, save_settings
from data.database import DB_PATH, database_exists, initialize_database

USER_ID = 1

st.set_page_config(page_title="設定 | 資産形成ナビ", page_icon="⚙️", layout="wide")

if not database_exists(DB_PATH):
    initialize_database(DB_PATH)

st.title("⚙️ 設定")
st.caption("資産形成シミュレーションで共通利用する基本設定と想定利回りを管理します。")

settings = get_settings(USER_ID, DB_PATH)

st.subheader("基本設定")
with st.form("settings_form"):
    current_age = st.number_input(
        "現在年齢",
        min_value=0,
        max_value=150,
        value=int(settings["current_age"]) if settings else 25,
        step=1,
        help="シミュレーションの開始年齢として使用します。",
    )
    simulation_years = st.number_input(
        "標準シミュレーション期間（年）",
        min_value=1,
        max_value=100,
        value=int(settings["simulation_years"]) if settings else 30,
        step=1,
    )
    currency = st.selectbox(
        "通貨",
        options=["JPY"],
        format_func=lambda x: "日本円（JPY）",
        index=0,
    )
    display_unit = st.selectbox(
        "表示単位",
        options=["yen", "man", "million"],
        format_func=lambda x: {"yen": "円", "man": "万円", "million": "百万円"}[x],
        index=["yen", "man", "million"].index(settings["display_unit"]) if settings and settings["display_unit"] in {"yen", "man", "million"} else 0,
    )
    submitted = st.form_submit_button("💾 基本設定を保存", type="primary")

if submitted:
    try:
        save_settings(
            user_id=USER_ID,
            current_age=int(current_age),
            simulation_years=int(simulation_years),
            currency=currency,
            display_unit=display_unit,
            db_path=DB_PATH,
        )
        st.success("基本設定を保存しました。")
        st.rerun()
    except Exception as exc:
        st.error(f"保存に失敗しました：{exc}")

st.divider()
st.subheader("想定利回り")
st.caption("年率を入力します。悲観・標準・楽観のシナリオごとに資産別に設定できます。")

assumptions = get_return_assumptions(USER_ID, DB_PATH)
if not assumptions:
    st.info("想定利回りが登録されていません。")
else:
    df = pd.DataFrame(assumptions)
    asset_names = list(dict.fromkeys(df["asset_name"].tolist()))
    scenario_order = [("BEAR", "悲観"), ("BASE", "標準"), ("BULL", "楽観")]

    with st.form("return_assumptions_form"):
        edited: list[dict] = []
        for asset_name in asset_names:
            st.markdown(f"**{asset_name}**")
            asset_df = df[df["asset_name"] == asset_name]
            cols = st.columns(3)
            for idx, (code, label) in enumerate(scenario_order):
                row = asset_df[asset_df["scenario_code"] == code].iloc[0]
                rate = cols[idx].number_input(
                    f"{label}（%）",
                    min_value=-100.0,
                    max_value=100.0,
                    value=float(row["annual_return_rate"]) * 100,
                    step=0.1,
                    key=f"rate_{int(row['asset_id'])}_{code}",
                )
                edited.append({
                    "asset_id": int(row["asset_id"]),
                    "scenario_code": code,
                    "annual_return_rate": float(rate) / 100,
                })
        rate_submitted = st.form_submit_button("💾 想定利回りを保存", type="primary")

    if rate_submitted:
        try:
            save_return_assumptions(edited, user_id=USER_ID, db_path=DB_PATH)
            st.success("想定利回りを保存しました。")
            st.rerun()
        except Exception as exc:
            st.error(f"想定利回りの保存に失敗しました：{exc}")

st.divider()
current = get_settings(USER_ID, DB_PATH)
if current:
    st.caption(
        f"現在年齢：{current['current_age']}歳 / "
        f"標準期間：{current['simulation_years']}年 / "
        f"表示単位：{'円' if current['display_unit']=='yen' else '万円' if current['display_unit']=='man' else '百万円'}"
    )
else:
    st.warning("基本設定が未保存です。現在年齢などを設定してください。")

import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

# --- 関数定義エリア ---

def get_market_fear():
    """Yahoo FinanceからVIX指数を取得する"""
    try:
        ticker = "^VIX"
        # 1日分のデータを取得
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception:
        return None
    return None

# --- ページ設定 ---
st.set_page_config(page_title="Annual Portfolio Rebalancer", layout="wide")

st.title("⚖️ ポートフォリオ・リバランス")
st.markdown("年に一回、資産配分を目標比率に戻すために使ってください。")

# --- サイドバー：入力エリア ---
st.sidebar.header("1. 目標比率の設定 (%)")
target_orkan = st.sidebar.number_input("オルカン (株式)", value=60, step=5)
target_gold = st.sidebar.number_input("ゴールド (金)", value=10, step=5)
target_cash = st.sidebar.number_input("キャッシュ (現金)", value=30, step=5)

# 合計チェック
total_ratio = target_orkan + target_gold + target_cash
if total_ratio != 100:
    st.sidebar.error(f"合計が {total_ratio}% です。100%になるように調整してください。")

st.sidebar.markdown("---")

st.sidebar.header("2. 現在の評価額 (万円)")
current_orkan = st.sidebar.number_input("オルカン評価額", value=650, step=10)
current_gold = st.sidebar.number_input("ゴールド評価額", value=150, step=10)
current_cash = st.sidebar.number_input("現在の現金保有額", value=200, step=10)

st.sidebar.markdown("---")

st.sidebar.header("3. 追加資金 (任意)")
st.sidebar.caption("リバランスと同時に追加投資（ボーナス等）をする場合は入力してください。")
additional_fund = st.sidebar.number_input("今回投入する資金 (万円)", value=0, step=5)

# --- 計算ロジック ---

# 現在の合計資産 + 追加資金
total_assets = current_orkan + current_gold + current_cash + additional_fund

# 目標となる金額（あるべき姿）
ideal_orkan = total_assets * (target_orkan / 100)
ideal_gold = total_assets * (target_gold / 100)
ideal_cash = total_assets * (target_cash / 100)

# 差額（プラスなら買い、マイナスなら売り）
diff_orkan = ideal_orkan - current_orkan
diff_gold = ideal_gold - current_gold
diff_cash = ideal_cash - current_cash

# --- メイン画面 ---

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📊 現在の配分状況")
    
    # 円グラフ用データ
    df_chart = pd.DataFrame({
        "Asset": ["オルカン", "ゴールド", "キャッシュ"],
        "Value": [current_orkan, current_gold, current_cash]
    })
    
    fig = px.pie(df_chart, values='Value', names='Asset', hole=0.4,
                 color='Asset',
                 color_discrete_map={'オルカン':'royalblue', 'ゴールド':'gold', 'キャッシュ':'lightgray'})
    st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"資産合計: **{total_assets - additional_fund:,.1f} 万円**")
    if additional_fund > 0:
        st.success(f"＋ 追加資金: **{additional_fund:,.1f} 万円**")

with col2:
    st.subheader("🛠 リバランス指示書")
    st.write("目標比率に戻すためのアクション：")
    
    # 結果を見やすく整形
    data = []
    assets = [("オルカン", diff_orkan), ("ゴールド", diff_gold), ("キャッシュ", diff_cash)]
    
    for name, val in assets:
        action = ""
        amount = 0
        
        # 0.1万円（1000円）未満の差は無視する設定
        if val > 0.1: 
            action = "🟢 買い (安値)"
            amount = f"{val:,.1f} 万円"
        elif val < -0.1: 
            action = "🔴 売り (高値)"
            amount = f"{abs(val):,.1f} 万円"
        else:
            action = "⚪️ 維持 (Hold)"
            amount = "0 万円"
            
        data.append([name, action, amount])
        
    df_res = pd.DataFrame(data, columns=["資産クラス", "アクション", "金額"])
    
    # テーブル表示
    st.table(df_res)
    
    st.markdown("---")

    # --- ここにVIX指数を移動 ---
    st.subheader("📉 市場の温度感")
    
    vix = get_market_fear()
    if vix:
        # メイン画面用の表示 (st.metricを使用)
        st.metric(label="VIX指数 (恐怖指数)", value=f"{vix:.2f}")
        
        # VIXの水準によるアドバイス
        if vix > 30:
            st.error("⚠️ **パニック相場**\n\n今は株が安売りされている「買い場」かもしれません。安易な狼狽売りは避けましょう。")
        elif vix > 20:
            st.warning("⚠️ **警戒水準**\n\n少し市場が不安定です。値動きに注意してください。")
        elif vix < 15:
            st.success("✅ **楽観相場**\n\n市場は落ち着いていますが、株価が高すぎる可能性もあります。")
        else:
            st.info("ℹ️ **通常運転**\n\n平穏な相場です。淡々とリバランスを行いましょう。")
    else:
        st.caption("※VIX指数の取得に失敗しました")

# --- シミュレーション ---
with st.expander("詳細データ: リバランス後の姿"):
    st.write(f"リバランスを実施すると、資産合計は **{int(total_assets):,} 万円** になり、比率は以下のようになります。")
    
    df_after = pd.DataFrame({
        "資産クラス": ["オルカン", "ゴールド", "キャッシュ"],
        "金額": [f"{ideal_orkan:,.1f} 万円", f"{ideal_gold:,.1f} 万円", f"{ideal_cash:,.1f} 万円"],
        "比率": [f"{target_orkan}%", f"{target_gold}%", f"{target_cash}%"]
    })
    st.dataframe(df_after)
    

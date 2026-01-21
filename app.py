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
st.set_page_config(page_title="Annual Portfolio Allocator", layout="wide")

st.title("⚖️ ポートフォリオ・リバランス")
st.markdown("今年投入する追加資金を配分します。\n\n**目標比率とのズレが許容範囲内（±5~10%）の場合は、ズレを埋めることよりも、目標比率通りの積立を優先します。**")

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

st.sidebar.header("3. 追加資金 (万円)")
st.sidebar.caption("今年一年で追加する資金（積立総額＋ボーナス＋貯金）を入力してください。")
additional_fund = st.sidebar.number_input("今回投入する資金合計", value=100, step=10)

# --- 計算ロジック ---

# 1. リバランス後の総資産予測 (現在額 + 追加資金)
projected_total_assets = current_orkan + current_gold + current_cash + additional_fund

# 2. リバランス後にあるべき理想の金額 (Target Amount)
ideal_orkan = projected_total_assets * (target_orkan / 100)
ideal_gold = projected_total_assets * (target_gold / 100)
ideal_cash = projected_total_assets * (target_cash / 100)

# 3. 現状とのギャップ (理想 - 現在) = 不足している金額
raw_gap_orkan = ideal_orkan - current_orkan
raw_gap_gold = ideal_gold - current_gold
raw_gap_cash = ideal_cash - current_cash

# --- 許容範囲の判定とギャップの調整 (Filtering) ---

def check_tolerance(gap_val, target_pct, total_assets):
    """
    許容範囲内かどうかを判定し、範囲内ならGapを0にする
    """
    # 乖離率（全体資産に対するズレの％）の計算
    deviation_pct = (abs(gap_val) / total_assets) * 100
    
    # しきい値の設定 (目標20%以下は±5%、それ以外は±10%)
    threshold = 5.0 if target_pct <= 20 else 10.0
    
    is_within_tolerance = deviation_pct <= threshold
    
    # 許容範囲内なら、リバランスのためのギャップは「0」とみなす
    adjusted_gap = 0 if is_within_tolerance else gap_val
    
    status_text = ""
    if is_within_tolerance:
        status_text = f"⚪️ 維持 (許容範囲内 ±{int(threshold)}%)"
    elif gap_val > 0:
        status_text = "🟢 買い (乖離大)"
    else:
        status_text = "🔴 売り (乖離大)"
        
    return adjusted_gap, status_text

# 各資産の判定実施
adj_gap_orkan, status_orkan = check_tolerance(raw_gap_orkan, target_orkan, projected_total_assets)
adj_gap_gold, status_gold = check_tolerance(raw_gap_gold, target_gold, projected_total_assets)
adj_gap_cash, status_cash = check_tolerance(raw_gap_cash, target_cash, projected_total_assets)

# 4. 配分ロジック (Allocation Logic)

# 調整後の「不足分（プラス）」だけを取り出す
pos_gap_orkan = max(0, adj_gap_orkan)
pos_gap_gold = max(0, adj_gap_gold)
pos_gap_cash = max(0, adj_gap_cash)
total_positive_gap = pos_gap_orkan + pos_gap_gold + pos_gap_cash

# 追加資金の配分計算
if total_positive_gap > 0:
    # A. 許容範囲を超えて不足している資産がある場合 → その穴埋めに優先配分
    alloc_orkan = additional_fund * (pos_gap_orkan / total_positive_gap)
    alloc_gold = additional_fund * (pos_gap_gold / total_positive_gap)
    alloc_cash = additional_fund * (pos_gap_cash / total_positive_gap)
else:
    # B. 全て許容範囲内（または全て超過）の場合 → 目標比率通りに「ニュートラル配分」
    alloc_orkan = additional_fund * (target_orkan / 100)
    alloc_gold = additional_fund * (target_gold / 100)
    alloc_cash = additional_fund * (target_cash / 100)
    
    # ステータス表示の微調整（配分がある場合は「積立」と表記）
    if alloc_orkan > 0: status_orkan = "🔵 積立 (比率配分)"
    if alloc_gold > 0: status_gold = "🔵 積立 (比率配分)"
    if alloc_cash > 0: status_cash = "🔵 積立 (比率配分)"

# 5. 購入後の予想資産額
future_orkan = current_orkan + alloc_orkan
future_gold = current_gold + alloc_gold
future_cash = current_cash + alloc_cash
future_total = future_orkan + future_gold + future_cash

# --- メイン画面 ---

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📊 ポートフォリオの変化")
    
    tab1, tab2 = st.tabs(["現在 (Before)", "購入後 (After)"])
    color_map = {'オルカン':'royalblue', 'ゴールド':'gold', 'キャッシュ':'lightgray'}
    
    with tab1:
        df_current = pd.DataFrame({
            "Asset": ["オルカン", "ゴールド", "キャッシュ"],
            "Value": [current_orkan, current_gold, current_cash]
        })
        fig_cur = px.pie(df_current, values='Value', names='Asset', hole=0.4,
                     color='Asset', color_discrete_map=color_map)
        st.plotly_chart(fig_cur, use_container_width=True)
        st.info(f"現在の総資産: **{current_orkan+current_gold+current_cash:,.1f} 万円**")

    with tab2:
        df_future = pd.DataFrame({
            "Asset": ["オルカン", "ゴールド", "キャッシュ"],
            "Value": [future_orkan, future_gold, future_cash]
        })
        fig_fut = px.pie(df_future, values='Value', names='Asset', hole=0.4,
                     color='Asset', color_discrete_map=color_map)
        st.plotly_chart(fig_fut, use_container_width=True)
        
        st.success(f"購入後の総資産: **{future_total:,.1f} 万円**")
        st.caption("購入後の比率 vs 目標:")
        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("オルカン", f"{future_orkan/future_total*100:.1f}%", f"目標 {target_orkan}%")
        col_r2.metric("ゴールド", f"{future_gold/future_total*100:.1f}%", f"目標 {target_gold}%")
        col_r3.metric("キャッシュ", f"{future_cash/future_total*100:.1f}%", f"目標 {target_cash}%")

with col2:
    st.subheader("🛠 リバランス指示書")
    
    if additional_fund <= 0:
        st.warning("左側のサイドバーで「追加資金」を入力してください。")
    else:
        st.write(f"追加資金 **{additional_fund:,.1f} 万円** の最適な配分は以下の通りです。")
        
        # テーブルデータの作成
        assets_info = [
            ("オルカン (株式)", status_orkan, alloc_orkan),
            ("ゴールド (金)", status_gold, alloc_gold),
            ("キャッシュ (現金)", status_cash, alloc_cash)
        ]
        
        table_data = []
        for name, status, alloc in assets_info:
            amount_str = f"{alloc:,.1f} 万円"
            table_data.append([name, status, amount_str])
            
        df_res = pd.DataFrame(table_data, columns=["資産クラス", "判定 (Status)", "今回配分額"])
        st.table(df_res)
        
        # 具体的な手順
        st.markdown("### 📝 具体的な手順")
        
        if alloc_cash > 0:
             st.write(f"- 銀行口座に **{alloc_cash:,.1f} 万円** をそのまま貯金（または国債購入）してください。")
             
        invest_total = alloc_orkan + alloc_gold
        if invest_total > 0:
            st.write(f"- 証券口座で合計 **{invest_total:,.1f} 万円** の注文を出してください。")
            if alloc_orkan > 0:
                st.write(f"  - うち **{alloc_orkan:,.1f} 万円** でオルカンを購入")
            if alloc_gold > 0:
                st.write(f"  - うち **{alloc_gold:,.1f} 万円** でゴールドを購入")
    
    st.markdown("---")

    # --- VIX指数エリア ---
    st.subheader("📉 株式市場の温度感")
    
    vix = get_market_fear()
    if vix:
        st.metric(label="VIX指数 (恐怖指数)", value=f"{vix:.2f}")
        
        if vix > 30:
            st.error("⚠️ **パニック相場**\n\n今は株が安売りされている「買い場」かもしれません。積極的な配分を検討しても良いでしょう。")
        elif vix > 20:
            st.warning("⚠️ **警戒水準**\n\n少し市場が不安定です。")
        elif vix < 15:
            st.success("✅ **楽観相場**\n\n株価が高すぎる可能性があります。高値掴みに注意してください。")
        else:
            st.info("ℹ️ **通常運転**\n\n平穏な相場です。計算通りの配分で問題ありません。")
    else:
        st.caption("※VIX指数の取得に失敗しました")

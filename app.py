import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import datetime
import io

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

def get_vix_data(period="1y"):
    """Yahoo FinanceからVIX指数の履歴と現在値を取得する"""
    try:
        ticker = "^VIX"
        data = yf.Ticker(ticker).history(period=period)
        if not data.empty:
            current_value = data['Close'].iloc[-1]
            return current_value, data.reset_index()
    except Exception:
        return None, None
    return None, None

# --- ページ設定 ---
st.set_page_config(page_title="Annual Portfolio Allocator", layout="wide")

st.title("⚖️ リバランスアプリ")
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

st.sidebar.header("2. 現在の評価額 & 元本 (万円)")
st.sidebar.caption("損益計算のため、元本（投資額）も入力してください。")

# オルカン
current_orkan = st.sidebar.number_input("オルカン 評価額", value=650, step=10)
principal_orkan = st.sidebar.number_input("オルカン 元本", value=500, step=10)

# ゴールド
st.sidebar.markdown("---") 
current_gold = st.sidebar.number_input("ゴールド 評価額", value=150, step=10)
principal_gold = st.sidebar.number_input("ゴールド 元本", value=100, step=10)

# キャッシュ
st.sidebar.markdown("---")
current_cash = st.sidebar.number_input("現在の現金保有額", value=200, step=10)
# キャッシュの元本は常に評価額と同じとみなす
principal_cash = current_cash 

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
    deviation_pct = (abs(gap_val) / total_assets) * 100
    threshold = 5.0 if target_pct <= 20 else 10.0
    is_within_tolerance = deviation_pct <= threshold
    adjusted_gap = 0 if is_within_tolerance else gap_val
    
    status_text = ""
    if is_within_tolerance:
        status_text = f"⚪️ 維持 (許容範囲内 ±{int(threshold)}%)"
    elif gap_val > 0:
        status_text = "🟢 買い (乖離大)"
    else:
        status_text = "🔴 売り (乖離大)"
        
    return adjusted_gap, status_text

adj_gap_orkan, status_orkan = check_tolerance(raw_gap_orkan, target_orkan, projected_total_assets)
adj_gap_gold, status_gold = check_tolerance(raw_gap_gold, target_gold, projected_total_assets)
adj_gap_cash, status_cash = check_tolerance(raw_gap_cash, target_cash, projected_total_assets)

# 4. 配分ロジック (Allocation Logic)
pos_gap_orkan = max(0, adj_gap_orkan)
pos_gap_gold = max(0, adj_gap_gold)
pos_gap_cash = max(0, adj_gap_cash)
total_positive_gap = pos_gap_orkan + pos_gap_gold + pos_gap_cash

if total_positive_gap > 0:
    alloc_orkan = additional_fund * (pos_gap_orkan / total_positive_gap)
    alloc_gold = additional_fund * (pos_gap_gold / total_positive_gap)
    alloc_cash = additional_fund * (pos_gap_cash / total_positive_gap)
else:
    alloc_orkan = additional_fund * (target_orkan / 100)
    alloc_gold = additional_fund * (target_gold / 100)
    alloc_cash = additional_fund * (target_cash / 100)
    
    if alloc_orkan > 0: status_orkan = "🔵 積立 (比率配分)"
    if alloc_gold > 0: status_gold = "🔵 積立 (比率配分)"
    if alloc_cash > 0: status_cash = "🔵 積立 (比率配分)"

# 5. 購入後の予想資産額
future_orkan = current_orkan + alloc_orkan
future_gold = current_gold + alloc_gold
future_cash = current_cash + alloc_cash
future_total = future_orkan + future_gold + future_cash

# --- 損益計算ロジック ---
# オルカン
profit_orkan = current_orkan - principal_orkan
profit_rate_orkan = (profit_orkan / principal_orkan * 100) if principal_orkan > 0 else 0

# ゴールド
profit_gold = current_gold - principal_gold
profit_rate_gold = (profit_gold / principal_gold * 100) if principal_gold > 0 else 0

# 全体（キャッシュ含む）
total_current = current_orkan + current_gold + current_cash
total_principal = principal_orkan + principal_gold + principal_cash
total_profit = total_current - total_principal
total_profit_rate = (total_profit / total_principal * 100) if total_principal > 0 else 0

# VIX取得（ここで取得しておく）
current_vix, history_vix = get_vix_data(period="1y")

# --- メイン画面 ---

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📊 アセットアロケーション")
    
    tab1, tab2 = st.tabs(["現在 (Before)", "購入後 (After)"])
    color_map = {'オルカン':'royalblue', 'ゴールド':'gold', 'キャッシュ':'lightgray'}
    
    with tab1:
        # 1. 円グラフを先に表示
        df_current = pd.DataFrame({
            "Asset": ["オルカン", "ゴールド", "キャッシュ"],
            "Value": [current_orkan, current_gold, current_cash]
        })
        fig_cur = px.pie(df_current, values='Value', names='Asset', hole=0.4,
                     color='Asset', color_discrete_map=color_map)
        st.plotly_chart(fig_cur, use_container_width=True)
        
        st.markdown("---")

        # 2. 運用成績をグラフの下に表示
        st.markdown("##### 運用成績")
        
        # 全体の損益
        st.metric(
            label="総資産 損益率",
            value=f"{total_current:,.1f} 万円",
            delta=f"{total_profit_rate:+.1f}% ({total_profit:+.1f} 万円)"
        )
        
        # 個別の損益（2列で表示）
        c1, c2 = st.columns(2)
        c1.metric(
            label="オルカン",
            value=f"{current_orkan:,.1f} 万円",
            delta=f"{profit_rate_orkan:+.1f}%"
        )
        c2.metric(
            label="ゴールド",
            value=f"{current_gold:,.1f} 万円",
            delta=f"{profit_rate_gold:+.1f}%"
        )

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
            ratio = (alloc / additional_fund * 100) if additional_fund > 0 else 0
            amount_str = f"{alloc:,.1f} 万円"
            ratio_str = f"{ratio:.1f} %"
            table_data.append([name, status, amount_str, ratio_str])
            
        df_res = pd.DataFrame(table_data, columns=["資産クラス", "判定 (Status)", "今回配分額", "配分比率"])
        st.table(df_res)
        
        # 具体的な手順
        st.markdown("### 📝 具体的な手順")
        
        if alloc_cash > 0:
             st.write(f"- 銀行口座に **{alloc_cash:,.1f} 万円** をそのまま貯金（または国債購入）してください。")
             
        invest_total = alloc_orkan + alloc_gold
        if invest_total > 0:
            st.write(f"- 証券口座で合計 **{invest_total:,.1f} 万円** の注文を出してください。")
            if alloc_orkan > 0:
                st.write(f"  - うち **{alloc_orkan:,.1f} 万円** ({alloc_orkan/additional_fund*100:.1f}%) でオルカンを購入")
            if alloc_gold > 0:
                st.write(f"  - うち **{alloc_gold:,.1f} 万円** ({alloc_gold/additional_fund*100:.1f}%) でゴールドを購入")
    
    st.markdown("---")
    
    # --- レポートCSV作成機能 ---
    def create_report_csv(df_instructions, current_vix, additional_fund):
        # メモリ上にテキストバッファを作成
        output = io.StringIO()
        
        # 1. 基本情報
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        vix_str = f"{current_vix:.2f}" if current_vix else "取得失敗"
        
        output.write("【基本情報】\n")
        output.write(f"ダウンロード日時,{now_str}\n")
        output.write(f"VIX指数,{vix_str}\n")
        output.write(f"追加資金合計,{additional_fund} 万円\n")
        output.write("\n")
        
        # 2. 資産状況サマリー
        output.write("【資産運用状況】\n")
        summary_data = [
            ["オルカン", current_orkan, principal_orkan, profit_orkan, f"{profit_rate_orkan:.1f}%"],
            ["ゴールド", current_gold, principal_gold, profit_gold, f"{profit_rate_gold:.1f}%"],
            ["キャッシュ", current_cash, principal_cash, 0, "0.0%"],
            ["合計", total_current, total_principal, total_profit, f"{total_profit_rate:.1f}%"]
        ]
        df_summary = pd.DataFrame(summary_data, columns=["資産名", "評価額(万円)", "元本(万円)", "損益(万円)", "損益率"])
        df_summary.to_csv(output, index=False)
        output.write("\n")
        
        # 3. リバランス指示書
        output.write("【リバランス配分指示】\n")
        df_instructions.to_csv(output, index=False)
        
        # バッファの内容をutf-8-sigでエンコードして返す
        return output.getvalue().encode('utf-8-sig')

    if additional_fund > 0:
        csv_data = create_report_csv(df_res, current_vix, additional_fund)
        
        st.download_button(
            label="📥 詳細レポートをCSVでダウンロード",
            data=csv_data,
            file_name=f'portfolio_report_{datetime.date.today()}.csv',
            mime='text/csv',
        )

    st.markdown("---")

    # --- VIX指数エリア（グラフ付き） ---
    st.subheader("📉 市場の温度感")
    
    if current_vix:
        st.metric(label="現在のVIX指数", value=f"{current_vix:.2f}")
        
        if history_vix is not None:
            fig_vix = px.line(history_vix, x="Date", y="Close", title="VIX指数の推移 (過去1年)")
            fig_vix.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="パニック (30)")
            fig_vix.add_hline(y=20, line_dash="dash", line_color="orange", annotation_text="警戒 (20)")
            fig_vix.update_layout(xaxis_title="日付", yaxis_title="VIX", height=350)
            st.plotly_chart(fig_vix, use_container_width=True)

        if current_vix > 30:
            st.error("⚠️ **パニック相場**\n\n今は株が安売りされている「買い場」かもしれません。積極的な配分を検討しても良いでしょう。")
        elif current_vix > 20:
            st.warning("⚠️ **警戒水準**\n\n少し市場が不安定です。")
        elif current_vix < 15:
            st.success("✅ **楽観相場**\n\n株価が高すぎる可能性があります。高値掴みに注意してください。")
        else:
            st.info("ℹ️ **通常運転**\n\n平穏な相場です。計算通りの配分で問題ありません。")
            
    else:
        st.caption("※VIX指数の取得に失敗しました")

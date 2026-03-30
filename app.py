import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import datetime
import io

# --- 関数定義エリア ---

def get_market_fear():
    try:
        ticker = "^VIX"
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception:
        return None
    return None

def get_vix_data(period="1y"):
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

st.title("⚖️ ノーセルリバランス")
st.markdown("毎月のオルカン積立をベースとし、**今年のボーナスをオルカンとキャッシュにどう配分すれば目標比率に近づくか**を自動計算します。\n\n※少しでも目標比率からズレている場合は、ボーナスを使って重点的に補填します（許容値0%）。")

# --- サイドバー：入力エリア ---
st.sidebar.header("1. 目標比率の設定 (%)")
target_orkan = st.sidebar.number_input("オルカン (株式)", value=70, step=5)
target_cash = st.sidebar.number_input("キャッシュ (現金)", value=30, step=5)

# 合計チェック
total_ratio = target_orkan + target_cash
if total_ratio != 100:
    st.sidebar.error(f"合計が {total_ratio}% です。100%になるように調整してください。")

st.sidebar.markdown("---")

st.sidebar.header("2. 現在の評価額 (万円)")
current_orkan = st.sidebar.number_input("オルカン 評価額", value=650, step=10)
current_cash = st.sidebar.number_input("現在のキャッシュ保有額", value=200, step=10)

st.sidebar.markdown("---")

st.sidebar.header("3. 今年の積立＆ボーナス (万円)")
st.sidebar.caption("毎月の積立額と、今年見込めるボーナスの総額を入力してください。")
monthly_invest = st.sidebar.number_input("毎月のオルカン積立額", value=5.0, step=1.0)
bonus_total = st.sidebar.number_input("今年のボーナス見込み額 (合計)", value=100.0, step=10.0)

# --- 計算ロジック ---

# 1. 毎月積立による1年後のベース資産（ボーナス配分前）
yearly_orkan_invest = monthly_invest * 12
base_orkan = current_orkan + yearly_orkan_invest
base_cash = current_cash

# 2. ボーナスを含めた1年後の「予想総資産」
future_total = base_orkan + base_cash + bonus_total

# 3. 予想総資産に対する「あるべき理想の金額」
ideal_orkan = future_total * (target_orkan / 100)
ideal_cash = future_total * (target_cash / 100)

# 4. ベース資産と理想額のギャップ（＝ボーナスで埋めるべき不足額）
raw_gap_orkan = ideal_orkan - base_orkan
raw_gap_cash = ideal_cash - base_cash

# --- 許容範囲の判定とギャップの調整 ---
def check_tolerance(gap_val, target_pct, total_assets):
    deviation_pct = (abs(gap_val) / total_assets) * 100 if total_assets > 0 else 0
    # 許容範囲を0%に設定（計算誤差を考慮し 0.001% 以下はズレなしとみなす）
    is_within_tolerance = deviation_pct <= 0.001
    adjusted_gap = 0 if is_within_tolerance else gap_val
    
    status_text = ""
    if is_within_tolerance:
        status_text = "⚪️ 維持 (ズレなし)"
    elif gap_val > 0:
        status_text = "🟢 重点配分 (不足を補填)"
    else:
        status_text = "🔴 配分なし (既に超過)"
        
    return adjusted_gap, status_text

adj_gap_orkan, status_orkan = check_tolerance(raw_gap_orkan, target_orkan, future_total)
adj_gap_cash, status_cash = check_tolerance(raw_gap_cash, target_cash, future_total)

# 5. ボーナスの配分計算
pos_gap_orkan = max(0, adj_gap_orkan)
pos_gap_cash = max(0, adj_gap_cash)
total_positive_gap = pos_gap_orkan + pos_gap_cash

bonus_to_orkan = 0.0
bonus_to_cash = 0.0

if bonus_total > 0:
    if total_positive_gap > 0:
        # ギャップに応じてボーナスを傾斜配分
        bonus_to_orkan = bonus_total * (pos_gap_orkan / total_positive_gap)
        bonus_to_cash = bonus_total * (pos_gap_cash / total_positive_gap)
    else:
        # 完全に一致しているなら、ボーナスは目標比率通りに配分
        bonus_to_orkan = bonus_total * (target_orkan / 100)
        bonus_to_cash = bonus_total * (target_cash / 100)
        status_orkan = "🔵 比率配分 (完全一致)"
        status_cash = "🔵 比率配分 (完全一致)"

# 6. ボーナス配分後の最終予想資産額
future_orkan = base_orkan + bonus_to_orkan
future_cash = base_cash + bonus_to_cash

total_current = current_orkan + current_cash

# VIX取得
current_vix, history_vix = get_vix_data(period="1y")

# --- メイン画面 ---

col1, col2 = st.columns([1, 1.5])

with col1:
    st.subheader("📊 アセットアロケーション")
    
    tab1, tab2 = st.tabs(["現在 (Before)", "1年後 (After)"])
    color_map = {'オルカン':'royalblue', 'キャッシュ':'lightgray'}
    
    with tab1:
        df_current = pd.DataFrame({
            "Asset": ["オルカン", "キャッシュ"],
            "Value": [current_orkan, current_cash]
        })
        fig_cur = px.pie(df_current, values='Value', names='Asset', hole=0.4,
                     color='Asset', color_discrete_map=color_map)
        st.plotly_chart(fig_cur, use_container_width=True)
        st.info(f"現在の総資産: **{total_current:,.1f} 万円**")

    with tab2:
        df_future = pd.DataFrame({
            "Asset": ["オルカン", "キャッシュ"],
            "Value": [future_orkan, future_cash]
        })
        fig_fut = px.pie(df_future, values='Value', names='Asset', hole=0.4,
                     color='Asset', color_discrete_map=color_map)
        st.plotly_chart(fig_fut, use_container_width=True)
        
        st.success(f"1年後の予想総資産: **{future_total:,.1f} 万円**")
        st.caption("1年後の比率 vs 目標:")
        col_r1, col_r2 = st.columns(2)
        col_r1.metric("オルカン", f"{future_orkan/future_total*100:.1f}%", f"目標 {target_orkan}%")
        col_r2.metric("キャッシュ", f"{future_cash/future_total*100:.1f}%", f"目標 {target_cash}%")

with col2:
    st.subheader("🛠 配分指示書")
    
    if bonus_total <= 0:
        st.warning("ボーナス見込み額が0円に設定されています。ボーナスによる調整は行われません。")
    else:
        st.write(f"今年のボーナス **{bonus_total:,.1f} 万円** の最適な配分は以下の通りです。")
        
        # テーブルデータの作成
        assets_info = [
            ("オルカン (株式)", status_orkan, bonus_to_orkan),
            ("キャッシュ (国債)", status_cash, bonus_to_cash)
        ]
        
        table_data = []
        for name, status, alloc in assets_info:
            ratio = (alloc / bonus_total * 100) if bonus_total > 0 else 0
            amount_str = f"{alloc:,.1f} 万円"
            ratio_str = f"{ratio:.1f} %"
            table_data.append([name, status, amount_str, ratio_str])
            
        df_res = pd.DataFrame(table_data, columns=["資産クラス", "判定 (Status)", "ボーナス配分額", "配分比率"])
        st.table(df_res)
        
    # 具体的な手順
    st.markdown("### 📝 手順")
    
    st.write("**1. 毎月の自動積立（固定）**")
    st.write(f"- 証券口座にて、毎月 **{monthly_invest:,.1f} 万円** のオルカン積立を継続してください。（年間 {yearly_orkan_invest:,.1f} 万円）")
    
    st.write("") # 改行
    
    st.write("**2. ボーナスの振り分け**")
    if bonus_total > 0:
        if bonus_to_orkan > 0:
            st.write(f"-**{bonus_to_orkan:,.1f} 万円** をオルカンのスポット購入に回してください。")
        if bonus_to_cash > 0:
            st.write(f"-**{bonus_to_cash:,.1f} 万円** を個人向け国債の購入に回してください")
    else:
        st.write("- ボーナスによる追加の振り分けはありません。")
    
    st.markdown("---")
    
    # --- レポートCSV作成機能 ---
    def create_report_csv(df_instructions, current_vix, bonus_orkan, bonus_cash, total_bonus, yearly_orkan):
        output = io.StringIO()
        
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        vix_str = f"{current_vix:.2f}" if current_vix else "取得失敗"
        
        output.write("【基本情報】\n")
        output.write(f"ダウンロード日時,{now_str}\n")
        output.write(f"VIX指数,{vix_str}\n")
        output.write(f"毎月のオルカン積立額,{monthly_invest} 万円 (年間 {yearly_orkan} 万円)\n")
        output.write(f"ボーナス見込み額,{total_bonus} 万円\n")
        output.write("\n")
        
        output.write("【現在の資産状況】\n")
        summary_data = [
            ["オルカン", current_orkan],
            ["キャッシュ", current_cash],
            ["合計", total_current]
        ]
        df_summary = pd.DataFrame(summary_data, columns=["資産名", "現在の評価額(万円)"])
        df_summary.to_csv(output, index=False)
        output.write("\n")
        
        output.write("【ボーナス配分指示】\n")
        if total_bonus > 0:
            df_instructions.to_csv(output, index=False)
        else:
            output.write("ボーナス配分なし\n")
        
        return output.getvalue().encode('utf-8-sig')

    csv_data = create_report_csv(df_res if bonus_total > 0 else pd.DataFrame(), current_vix, bonus_to_orkan, bonus_to_cash, bonus_total, yearly_orkan_invest)
    
    st.download_button(
        label="📥 詳細レポートをCSVでダウンロード",
        data=csv_data,
        file_name=f'portfolio_plan_{datetime.date.today()}.csv',
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
            st.error("⚠️ **パニック相場**\n\n今は株が安売りされている「買い場」かもしれません。ボーナスの株式への配分を強気に見直すのも一考です。")
        elif current_vix > 20:
            st.warning("⚠️ **警戒水準**\n\n少し市場が不安定です。")
        elif current_vix < 15:
            st.success("✅ **楽観相場**\n\n株価が高すぎる可能性があります。高値掴みに注意してください。")
        else:
            st.info("ℹ️ **通常運転**\n\n平穏な相場です。計算通りの配分で問題ありません。")
            
    else:
        st.caption("※VIX指数の取得に失敗しました")

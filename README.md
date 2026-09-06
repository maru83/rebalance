# 資産形成ナビ MVP

Streamlit + SQLiteで構築する、現在資産・投資予定・将来資産・目標を一元管理する個人向け資産形成アプリです。

## MVPの対象

- 現在資産：残高、前回値、履歴
- 投資計画：毎月、毎年指定月、1回のみ、年間投資予定額、月別カレンダー
- シミュレーション：10年 / 20年 / 30年 / 目標年齢、悲観 / 標準 / 楽観
- 目標：目標年齢、目標資産額、達成見込み、必要月額投資額
- What-if：月額投資額を一時変更して将来資産を比較（DBへ保存しない）
- 資産推移：期間・資産別の履歴確認
- Dashboard：現在資産、目的別資産、年間投資予定額、将来予測、目標達成状況
- 設定：現在年齢、標準シミュレーション期間、表示単位、想定利回り

MVPでは「年間投資予定額」を正式な管理対象とし、実際の投資実績・取引明細はPhase 2です。

## ディレクトリ

```text
asset_management_app/
├── app.py
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Assets.py
│   ├── 3_Investment_Plan.py
│   ├── 4_Simulation.py
│   ├── 5_Goals.py
│   └── 6_Settings.py
├── core/
│   ├── asset.py
│   ├── dashboard.py
│   ├── display.py
│   ├── goal.py
│   ├── history.py
│   ├── investment.py
│   ├── settings.py
│   └── simulation.py
├── data/
│   ├── database.py
│   ├── schema.sql
│   └── asset_management.db
└── tests/
```

## 起動

Python 3.11を推奨します。

```bash
pip install -r requirements.txt
streamlit run app.py
```

初回起動時に `data/asset_management.db` が存在しなければ `schema.sql` から自動作成します。

その後、設定画面で以下を登録してください。

1. 現在年齢
2. 標準シミュレーション期間
3. 表示単位
4. 想定利回り

## テスト

```bash
pytest
```

`pytest.ini` にプロジェクトルートをPythonパスとして設定しているため、プロジェクトルートから上記コマンドで実行できます。

## 計算ルール

- 月次計算
- 月利：`(1 + 年率)^(1/12) - 1`
- 投資タイミング：月末投入モデル（簡易モデル）
- 期末残高：期首残高 × (1 + 月利) + 当月投資額
- シミュレーション結果はDBへ保存しない
- 目標の必要月額は二分探索で算出し、表示値は1万円単位に切り上げ

## 重要なUX方針

- 2回目以降は安定情報を再入力させない
- 現在年齢・投資計画・目標・想定利回りはDB値を初期表示
- 月次更新では原則として現在資産残高だけを更新
- Dashboardは概要、詳細分析は各機能ページで行う

## Phase 2候補

- 投資実績・取引明細
- 計画 vs 実績
- NISA利用状況
- リバランス
- インフレ考慮
- 市場データ連携
- CSV入出力

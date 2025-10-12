# レシピ原価計算Bot

LINEで画像を送信すると、Azure VisionとGroqで自動解析し、Supabaseに保存して原価を計算してくれるボットシステムです。

## 📋 システムフロー

```
LINE (画像送信)
  ↓
Render (Webhook受信)
  ↓
Azure Vision API (OCR画像解析)
  ↓
Groq LLM (テキスト構造化)
  ↓
Supabase (原価表参照 & データ保存)
  ↓
LINE (合計原価を返信)
```

## 🏗️ アーキテクチャ

- **フロントエンド**: LINE Bot (Messaging API)
- **バックエンド**: Flask + Gunicorn (Renderでホスティング)
- **画像解析**: Azure Computer Vision (OCR)
- **テキスト解析**: Groq (llama-3.1-70b-versatile)
- **データベース**: Supabase (PostgreSQL)
- **ストレージ**: Supabase Storage (原価表CSV)

## 📁 プロジェクト構成

```
recipe-management/
├── app.py                    # メインアプリケーション
├── azure_vision.py           # Azure Vision API処理
├── groq_parser.py            # Groqによるレシピ解析
├── cost_calculator.py        # 原価計算ロジック
├── cost_master_manager.py    # 原価表管理（NEW!）
├── test_local.py             # ローカルテスト用スクリプト
├── requirements.txt          # Python依存パッケージ
├── Procfile                  # Render設定
├── runtime.txt               # Pythonバージョン
├── env.template              # 環境変数テンプレート
├── supabase_setup.sql        # Supabaseテーブル定義
├── cost_master_sample.csv    # 原価表サンプル
├── README.md                 # このファイル
├── setup_instructions.md     # 詳細セットアップ手順
└── QUICKSTART.md             # クイックスタート
```

## 🚀 セットアップ手順

### 1. 環境変数の設定

`.env.example`を`.env`にコピーして、各種APIキーを設定してください。

```bash
cp .env.example .env
```

#### 必要なAPIキー・設定

##### LINE Bot
1. [LINE Developers Console](https://developers.line.biz/)でチャネルを作成
2. `LINE_CHANNEL_SECRET`と`LINE_CHANNEL_ACCESS_TOKEN`を取得

##### Azure Vision API
1. [Azure Portal](https://portal.azure.com/)でComputer Visionリソースを作成
2. エンドポイントとキーを取得

##### Groq API
1. [Groq Console](https://console.groq.com/)でAPIキーを取得

##### Supabase
1. [Supabase](https://supabase.com/)でプロジェクトを作成（無料枠で可）
2. Project URLとAnon Keyを取得

### 2. Supabaseのセットアップ

#### 2.1 テーブル作成

`supabase_setup.sql`の内容をSupabase SQL Editorで実行してください。

```sql
-- recipes, ingredients, cost_master テーブルが作成されます
```

#### 2.2 ストレージバケット作成

1. Supabaseダッシュボードで「Storage」→「New bucket」
2. バケット名: `cost-data`
3. Public: OFF (Private)
4. `cost_master_sample.csv`を参考に原価表CSVを作成してアップロード
   - ファイル名: `cost_master.csv`
   - パス: `cost-data/cost_master.csv`

#### 2.3 原価表CSVのフォーマット

```csv
ingredient_name,unit_price,reference_unit,reference_quantity
玉ねぎ,50,個,1
豚肉,300,g,100
```

- `ingredient_name`: 材料名
- `unit_price`: 基準数量あたりの価格（円）
- `reference_unit`: 基準単位
- `reference_quantity`: 基準数量

### 3. ローカル開発

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# アプリケーション起動
python app.py
```

### 4. Renderへのデプロイ

#### 4.1 GitHubリポジトリの作成

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

#### 4.2 Renderでのデプロイ

1. [Render](https://render.com/)にサインアップ・ログイン
2. 「New +」→「Web Service」
3. GitHubリポジトリを連携
4. 設定:
   - **Name**: recipe-bot（任意）
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free

5. 環境変数を設定（Environment）:
   ```
   LINE_CHANNEL_SECRET=xxx
   LINE_CHANNEL_ACCESS_TOKEN=xxx
   AZURE_VISION_ENDPOINT=xxx
   AZURE_VISION_KEY=xxx
   GROQ_API_KEY=xxx
   SUPABASE_URL=xxx
   SUPABASE_KEY=xxx
   ```

6. 「Create Web Service」

#### 4.3 LINE Webhook URLの設定

1. RenderでデプロイされたURL（例: `https://recipe-bot-xxxx.onrender.com`）をコピー
2. LINE Developers Consoleで「Messaging API」→「Webhook settings」
3. Webhook URL: `https://recipe-bot-xxxx.onrender.com/callback`
4. 「Use webhook」をON
5. 「Verify」でテスト

### 5. 動作確認

1. LINE Botを友だち追加
2. レシピが写っている画像を送信
3. 自動で解析され、原価が返信されます

#### テスト用コマンド

**基本**
- `ヘルプ` または `help`: 使い方を表示

**原価表管理**
- `追加 トマト 100円/個`: 原価を追加
- `追加 豚肉 300円/100g`: 原価を追加（重量単位）
- `確認 トマト`: 原価を確認
- `削除 トマト`: 原価を削除
- `原価一覧`: 登録されている全材料を表示

## 📊 データベーススキーマ

### recipes テーブル
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | UUID | レシピID |
| recipe_name | TEXT | 料理名 |
| servings | INTEGER | 何人前 |
| total_cost | DECIMAL | 合計原価 |
| image_url | TEXT | 画像URL（オプション） |
| created_at | TIMESTAMP | 作成日時 |

### ingredients テーブル
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | UUID | 材料ID |
| recipe_id | UUID | レシピID（外部キー） |
| ingredient_name | TEXT | 材料名 |
| quantity | DECIMAL | 数量 |
| unit | TEXT | 単位 |
| cost | DECIMAL | 原価 |

### cost_master テーブル
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | UUID | ID |
| ingredient_name | TEXT | 材料名（ユニーク） |
| unit_price | DECIMAL | 単価 |
| reference_unit | TEXT | 基準単位 |
| reference_quantity | DECIMAL | 基準数量 |

## 🔧 トラブルシューティング

### 画像が解析されない

- Azure Vision APIのクレジットを確認
- 画像が鮮明かどうか確認
- OCR対応言語を確認（日本語対応）

### 原価が計算されない

- Supabaseストレージに`cost_master.csv`がアップロードされているか確認
- 材料名が原価表と一致しているか確認（完全一致が必要）

### Renderでタイムアウトする

- 無料プランは初回アクセス時にコールドスタートが発生します
- LINE側のタイムアウト（30秒）に注意
  - 長時間処理の場合は`reply_message`の後に`push_message`を使用

### ログの確認

```bash
# Renderのログ
Render Dashboard → Logs

# ローカルログ
python app.py
```

## 💰 料金・無料枠

| サービス | 無料枠 | 備考 |
|---------|--------|------|
| LINE Messaging API | 月1,000通まで | Push APIの送信回数 |
| Azure Vision | 月5,000トランザクション | Read API |
| Groq | 無料（制限あり） | レート制限に注意 |
| Supabase | 500MB DB, 1GB Storage | 無料プランで十分 |
| Render | 750時間/月（1サービス） | 無料プラン |

**月200件の利用であれば完全無料で運用可能です。**

## 📝 ライセンス

MIT License

## 🤝 貢献

Issue・Pull Requestを歓迎します！

---

## 💡 主な機能

### レシピ解析
- ✅ 画像からレシピを自動抽出
- ✅ 材料名、分量、単位を自動解析
- ✅ 原価表を参照して自動計算
- ✅ 単位変換対応（g、kg、ml、大さじ、小さじなど）
- ✅ Supabaseにレシピデータを保存
- ✅ 1人前の原価も表示

### 原価表管理（NEW! 🎉）
- ✅ LINEから原価を追加・更新
- ✅ 自然言語で入力可能（例: 「トマト 100円/個」）
- ✅ 原価の確認・削除
- ✅ 原価一覧の表示
- ✅ Groqによる自動解析

## 🆕 使い方（原価表管理）

### 原価を追加
```
追加 トマト 100円/個
追加 豚バラ肉 300円/100g
追加 キャベツ1玉150円
追加 牛乳 200円/1L
```

自然な日本語で入力すると、Groqが自動的に以下の情報を解析します：
- 材料名
- 単価
- 基準単位
- 基準数量

### 原価を確認
```
確認 トマト
```

### 原価を削除
```
削除 トマト
```

### 原価一覧
```
原価一覧
```
または
```
一覧
```

## 🛠️ カスタマイズ例

- ~~原価表に新しい材料を追加（`cost_master.csv`を編集）~~ → **LINEから直接追加可能！**
- レシピの保存形式を変更（`app.py`の`save_recipe_to_supabase`）
- 返信メッセージのフォーマット変更（`format_cost_response`）
- 画像解析精度の調整（`groq_parser.py`のプロンプト）
- 原価追加の解析精度調整（`cost_master_manager.py`のプロンプト）

---

**開発者**: recipe-management project  
**バージョン**: 2.0.0  
**最終更新**: 2025-10-12


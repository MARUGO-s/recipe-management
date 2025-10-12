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

- **フロントエンド**: LINE Bot (Messaging API) + Web管理画面
- **バックエンド**: Flask + Gunicorn (Renderでホスティング)
- **画像解析**: Azure Computer Vision (OCR)
- **テキスト解析**: Groq (llama-3.1-8b-instant)
- **データベース**: Supabase (PostgreSQL)
- **ファイル管理**: Web管理画面でのCSVアップロード

## 📁 プロジェクト構成

```
recipe-management/
├── app.py                    # メインアプリケーション
├── azure_vision.py           # Azure Vision API処理
├── groq_parser.py            # Groqによるレシピ解析
├── cost_calculator.py        # 原価計算ロジック
├── cost_master_manager.py    # 原価表管理
├── requirements.txt          # Python依存パッケージ
├── Procfile                  # Render設定
├── runtime.txt               # Pythonバージョン
├── env.template              # 環境変数テンプレート
├── .gitignore                # Git除外設定
├── templates/
│   └── index.html            # Web管理画面
├── static/
│   └── js/
│       └── admin.js          # 管理画面JavaScript
├── supabase/
│   └── migrations/           # データベースマイグレーション
│       ├── 20250112000000_initial_schema.sql
│       ├── 20250112000001_add_capacity_fields.sql
│       └── 20250112000002_add_capacity_to_cost_master.sql
├── README.md                 # このファイル
└── CHANGELOG.md              # 変更履歴
```

## 🚀 セットアップ手順

### 1. 環境変数の設定

`env.template`を`.env`にコピーして、各種APIキーを設定してください。

```bash
cp env.template .env
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

Supabase SQL Editorで以下のマイグレーションを順番に実行してください：

1. `supabase/migrations/20250112000000_initial_schema.sql`
2. `supabase/migrations/20250112000001_add_capacity_fields.sql`
3. `supabase/migrations/20250112000002_add_capacity_to_cost_master.sql`

#### 2.2 データベース制約の調整

以下のSQLを実行してNOT NULL制約を緩和してください：

```sql
ALTER TABLE cost_master
ALTER COLUMN reference_unit DROP NOT NULL;

ALTER TABLE cost_master
ALTER COLUMN reference_quantity DROP NOT NULL;
```

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
   SUPABASE_ANON_KEY=xxx
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

## 💡 主な機能

### レシピ解析
- ✅ 画像からレシピを自動抽出
- ✅ 材料名、分量、単位を自動解析
- ✅ 容量・規格情報の抽出（例: 500gパック）
- ✅ 原価表を参照して自動計算
- ✅ 単位変換対応（g、kg、ml、大さじ、小さじなど）
- ✅ Supabaseにレシピデータを保存
- ✅ 1人前の原価も表示

### 原価表管理
- ✅ LINEから原価を追加・更新
- ✅ 自然言語で入力可能（例: 「トマト 100円/個」）
- ✅ 材料検索機能（材料名を入力すると単価を返信）
- ✅ 原価の確認・削除
- ✅ 原価一覧の表示
- ✅ Groqによる自動解析

### Web管理画面
- ✅ データベース統計の表示
- ✅ 原価表CSVのアップロード
- ✅ 取引データCSVのアップロード（材料情報抽出）
- ✅ データの確認・エクスポート
- ✅ テンプレートファイルのダウンロード

## 🆕 使い方

### レシピ解析
LINEでレシピ画像を送信するだけで、自動的に材料と原価を解析します。

### 原価表管理（LINE）
```
追加 トマト 100円/個
追加 豚バラ肉 300円/100g
確認 トマト
削除 トマト
原価一覧
```

### 材料検索（LINE）
```
トマト
```
→ トマトの単価と取引先情報を返信

### Web管理画面
`https://your-app.onrender.com/admin` にアクセスして：
- 原価表CSVのアップロード
- 取引データCSVのアップロード
- データベースの確認・管理

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
| capacity | DECIMAL | 容量・包装量 |
| capacity_unit | TEXT | 容量単位 |
| cost | DECIMAL | 原価 |

### cost_master テーブル
| カラム名 | 型 | 説明 |
|---------|-----|------|
| id | UUID | ID |
| ingredient_name | TEXT | 材料名（ユニーク） |
| capacity | DECIMAL | 容量・包装量 |
| unit | TEXT | 単位 |
| unit_price | DECIMAL | 単価 |
| reference_unit | TEXT | 基準単位（旧形式互換） |
| reference_quantity | DECIMAL | 基準数量（旧形式互換） |
| updated_at | TIMESTAMP | 更新日時 |

## 🔧 トラブルシューティング

### 画像が解析されない
- Azure Vision APIのクレジットを確認
- 画像が鮮明かどうか確認
- OCR対応言語を確認（日本語対応）

### 原価が計算されない
- Web管理画面で原価表データがアップロードされているか確認
- 材料名が原価表と一致しているか確認（部分一致検索対応）

### アップロードが失敗する
- CSVファイルの形式が正しいか確認
- テンプレートファイルをダウンロードして使用
- データベースの制約エラーを確認

### Renderでタイムアウトする
- 無料プランは初回アクセス時にコールドスタートが発生します
- LINE側のタイムアウト（30秒）に注意

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

**開発者**: recipe-management project  
**バージョン**: 2.1.0  
**最終更新**: 2025-01-12
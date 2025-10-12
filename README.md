# レシピ原価計算Bot v3.0

LINEでレシピ画像（日本語/英語など）を送ると、AIが自動で解析・翻訳し、データベースに保存して原価を計算してくれるボットシステムです。さらに、解析後には「これの材料は？」といった自然な対話も可能です。

## 📋 システムフロー

```
LINE (画像送信)
  ↓
Render (Webhook受信)
  ↓
Azure Vision API (OCR・言語判定)
  ↓
Groq LLM (翻訳 ※日本語以外の場合)
  ↓
Groq LLM (テキスト構造化)
  ↓
Supabase (原価表参照 & データ保存)
  ↓
LINE (合計原価を返信)
  ↓
LINE (「材料は？」などの後続質問に応答)
```

## 🏗️ アーキテクチャ

- **フロントエンド**: LINE Bot (Messaging API v3) + Web管理画面
- **バックエンド**: Flask + Gunicorn (Renderでホスティング)
- **画像解析**: Azure Computer Vision (OCR)
- **テキスト解析/翻訳**: Groq (Llama3)
- **データベース**: Supabase (PostgreSQL)
- **会話状態管理**: Supabase (`conversation_state`テーブル)

## ✨ 主な機能

### レシピ解析 (LINE)
- ✅ **多言語対応**: 日本語、英語など様々な言語のレシピ画像を自動翻訳して解析。
- ✅ **会話記憶**: レシピ解析後、「これの材料は？」「合計いくら？」といった文脈を記憶した対話が可能。
- ✅ **高精度な単位変換**: `g`と`kg`、`ml`と`L`のような関連単位のみを変換し、`個`と`g`のような無関係な単位は変換しない、より正確な原価計算を実現。
- ✅ 材料名、分量、単位を自動で構造化。
- ✅ 1人前の原価も表示。

### 原価・データ管理 (LINE & Web)
- ✅ **LINEからの原価登録**: 「追加 トマト 100円/個」のような自然言語で原価を登録・更新。
- ✅ **堅牢なCSVアップロード**: Web管理画面から、文字コード（BOM, Shift-JIS）やファイル内の重複を気にせず、安定してCSVファイルをアップロード可能。
- ✅ **安全なデータクリア**: Web管理画面で「クリア」と入力しないと実行されない、安全な全データ削除機能。

## 🚀 セットアップ手順

### 1. 環境変数の設定

`env.template` を `.env` にコピーし、各種APIキー・接続情報を設定してください。

```bash
cp env.template .env
```

#### 必要なキーと設定

| 環境変数 | 説明 | 取得場所 |
| :--- | :--- | :--- |
| `LINE_CHANNEL_SECRET` | LINE BotのChannel Secret | [LINE Developers](https://developers.line.biz/) |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE BotのChannel Access Token | [LINE Developers](https://developers.line.biz/) |
| `AZURE_VISION_ENDPOINT` | Azure Computer Visionのエンドポイント | [Azure Portal](https://portal.azure.com/) |
| `AZURE_VISION_KEY` | Azure Computer Visionのキー | [Azure Portal](https://portal.azure.com/) |
| `GROQ_API_KEY` | Groq APIキー | [Groq Console](https://console.groq.com/) |
| `SUPABASE_URL` | SupabaseプロジェクトのURL | [Supabase Dashboard](https://supabase.com/dashboard) |
| `SUPABASE_KEY` | Supabaseプロジェクトの **anon key** | Supabase > Project Settings > API |
| `SUPABASE_SERVICE_KEY` | Supabaseプロジェクトの **service_role key** | Supabase > Project Settings > API |
| `SUPABASE_DB_PASSWORD` | Supabaseのデータベースパスワード | Supabase > Project Settings > Database |

**【重要】** バックエンドから安全にデータベースを操作するため、`SUPABASE_SERVICE_KEY` の設定が必須です。

### 2. Supabaseのセットアップ

SupabaseのSQL Editorで、`supabase/migrations/` ディレクトリにある以下のSQLファイルを**順番に**実行してください。

1.  `..._initial_schema.sql`
2.  `..._add_capacity_fields.sql`
3.  `..._add_capacity_to_cost_master.sql`
4.  `..._add_conversation_state.sql`

### 3. ローカル開発

```bash
# 依存パッケージのインストール
pip install -r requirements.txt

# アプリケーション起動 (ポート5001で起動する場合)
PORT=5001 python3 app.py
```

Web管理画面には `http://localhost:5001/` でアクセスできます。

### 4. Renderへのデプロイ

基本的な手順は同じですが、Renderの環境変数設定で、必ず `SUPABASE_SERVICE_KEY` を追加してください。

## 📊 データベーススキーマ

### `conversation_state` テーブル (New!)
| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| `user_id` | TEXT | LINEのユーザーID（主キー） |
| `state` | JSONB | 会話の状態（直前のレシピ情報など） |
| `updated_at` | TIMESTAMPTZ | 最終更新日時 |

### `cost_master` テーブル
| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| `id` | UUID | ID |
| `ingredient_name` | TEXT | 材料名（ユニーク） |
| `capacity` | DECIMAL | 容量・包装量 |
| `unit` | TEXT | 単位 |
| `unit_price` | DECIMAL | 単価 |
| `updated_at` | TIMESTAMP | 更新日時 |

(recipes, ingredients テーブルは変更なし)

---

**開発者**: recipe-management project  
**バージョン**: 3.0.0  
**最終更新**: 2025-10-12

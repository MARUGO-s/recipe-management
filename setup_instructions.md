# セットアップ手順詳細

このドキュメントでは、レシピ原価計算Botの詳細なセットアップ手順を説明します。

## 📋 事前準備

以下のアカウントを作成してください（すべて無料プランで可）：

1. **LINE Developers** - https://developers.line.biz/
2. **Azure** - https://portal.azure.com/
3. **Groq** - https://console.groq.com/
4. **Supabase** - https://supabase.com/
5. **Render** - https://render.com/
6. **GitHub** - https://github.com/

---

## 1️⃣ LINE Bot設定

### 1.1 LINE Developersでチャネル作成

1. [LINE Developers Console](https://developers.line.biz/console/)にログイン
2. 「プロバイダー」を作成（既存のものがあれば選択）
3. 「チャネルを作成」→「Messaging API」を選択
4. 以下を入力：
   - チャネル名: `レシピ原価計算Bot`
   - チャネル説明: `画像からレシピを解析して原価を計算`
   - カテゴリ: `飲食`
5. 利用規約に同意して作成

### 1.2 チャネル設定

1. 作成したチャネルの「Messaging API」タブへ
2. 以下をコピー：
   - **Channel Secret** → `.env`の`LINE_CHANNEL_SECRET`
   - **Channel access token (long-lived)** → 「発行」をクリックしてトークンを取得 → `.env`の`LINE_CHANNEL_ACCESS_TOKEN`

3. 以下の設定を変更：
   - **応答メッセージ**: OFF
   - **Webhook**: ON（後でURLを設定）
   - **友だち追加時あいさつ**: お好みで設定

---

## 2️⃣ Azure Vision API設定

### 2.1 Computer Visionリソース作成

1. [Azure Portal](https://portal.azure.com/)にログイン
2. 「リソースの作成」→「AI + Machine Learning」→「Computer Vision」
3. 以下を入力：
   - サブスクリプション: （お使いのサブスクリプション）
   - リソースグループ: 新規作成 `recipe-bot-rg`
   - リージョン: `Japan East`（東日本）
   - 名前: `recipe-bot-vision`（一意の名前）
   - 価格レベル: `Free F0`（無料枠）
4. 「確認および作成」→「作成」

### 2.2 エンドポイントとキーを取得

1. 作成したリソースへ移動
2. 左メニュー「キーとエンドポイント」
3. 以下をコピー：
   - **エンドポイント** → `.env`の`AZURE_VISION_ENDPOINT`
   - **キー1** → `.env`の`AZURE_VISION_KEY`

---

## 3️⃣ Groq API設定

### 3.1 APIキー取得

1. [Groq Console](https://console.groq.com/)にサインアップ・ログイン
2. 左メニュー「API Keys」
3. 「Create API Key」
4. 名前を入力（例: `recipe-bot`）→ 作成
5. 表示されたAPIキーをコピー → `.env`の`GROQ_API_KEY`

> ⚠️ APIキーは一度しか表示されないので必ず保存してください

---

## 4️⃣ Supabase設定

### 4.1 プロジェクト作成

1. [Supabase](https://supabase.com/)にサインアップ・ログイン
2. 「New Project」
3. 以下を入力：
   - 組織: （既存または新規作成）
   - プロジェクト名: `recipe-management`
   - データベースパスワード: （強力なパスワードを生成・保存）
   - リージョン: `Northeast Asia (Tokyo)`
   - プラン: `Free`
4. プロジェクトが準備完了するまで数分待機

### 4.2 接続情報を取得

1. プロジェクトダッシュボード→「Settings」→「API」
2. 以下をコピー：
   - **Project URL** → `.env`の`SUPABASE_URL`
   - **anon public** key → `.env`の`SUPABASE_KEY`

### 4.3 テーブル作成

1. 左メニュー「SQL Editor」
2. 「New Query」
3. `supabase_setup.sql`の内容をすべてコピー＆ペースト
4. 「Run」をクリック
5. 成功メッセージを確認

### 4.4 ストレージ設定

1. 左メニュー「Storage」
2. 「New bucket」をクリック
3. 以下を入力：
   - Bucket name: `cost-data`
   - Public bucket: OFF（プライベート）
4. 作成

### 4.5 原価表のアップロード

1. 作成した`cost-data`バケットを開く
2. 「Upload file」
3. `cost_master_sample.csv`を参考に原価表CSVを作成してアップロード
   - ファイル名: `cost_master.csv`（正確に）
4. または、`cost_master_sample.csv`をそのままアップロード（テスト用）

### 4.6 ストレージポリシー設定（必要に応じて）

```sql
-- Storageへのアクセスポリシー（必要に応じて）
CREATE POLICY "Allow authenticated uploads" 
ON storage.objects FOR INSERT 
TO authenticated 
WITH CHECK (bucket_id = 'cost-data');

CREATE POLICY "Allow public downloads" 
ON storage.objects FOR SELECT 
TO public 
USING (bucket_id = 'cost-data');
```

---

## 5️⃣ ローカル開発環境

### 5.1 環境構築

```bash
# リポジトリをクローン
cd /Users/yoshito/recipe-management

# 仮想環境作成（オプション）
python -m venv venv
source venv/bin/activate  # Windowsの場合: venv\Scripts\activate

# 依存パッケージをインストール
pip install -r requirements.txt

# .envファイルを作成（すでに作成済みの場合はスキップ）
# 各APIキーを設定
```

### 5.2 テスト実行

```bash
# テストスクリプトで各モジュールを確認
python test_local.py
```

### 5.3 ローカルサーバー起動

```bash
# アプリケーションを起動
python app.py

# 別ターミナルでngrokを使用（LINEからのWebhookをローカルで受信）
ngrok http 5000
```

---

## 6️⃣ Renderへのデプロイ

### 6.1 GitHubリポジトリ作成

```bash
# Gitの初期化
git init

# .gitignoreがあることを確認
cat .gitignore

# コミット
git add .
git commit -m "Initial commit: Recipe cost calculator bot"

# GitHubにプッシュ
git remote add origin https://github.com/yourusername/recipe-management.git
git branch -M main
git push -u origin main
```

### 6.2 Renderでデプロイ

1. [Render](https://render.com/)にログイン
2. 「New +」→「Web Service」
3. 「Connect GitHub」→ リポジトリを選択
4. 以下を設定：

**Basic Settings:**
- Name: `recipe-bot`（任意）
- Region: `Singapore`（無料プランでは選択不可）
- Branch: `main`
- Runtime: `Python 3`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

**Instance Type:**
- `Free`を選択

5. 「Advanced」→「Environment Variables」で環境変数を追加：

```
LINE_CHANNEL_SECRET = xxx
LINE_CHANNEL_ACCESS_TOKEN = xxx
AZURE_VISION_ENDPOINT = https://xxx.cognitiveservices.azure.com/
AZURE_VISION_KEY = xxx
GROQ_API_KEY = gsk_xxx
SUPABASE_URL = https://xxx.supabase.co
SUPABASE_KEY = xxx
```

6. 「Create Web Service」

### 6.3 デプロイ完了確認

1. デプロイが完了するまで待機（5-10分）
2. ログで確認：`Your service is live 🎉`
3. URLをコピー（例: `https://recipe-bot-xxxx.onrender.com`）

---

## 7️⃣ LINE Webhook設定

### 7.1 Webhook URLの登録

1. [LINE Developers Console](https://developers.line.biz/console/)
2. 作成したチャネル→「Messaging API」タブ
3. **Webhook settings**:
   - Webhook URL: `https://recipe-bot-xxxx.onrender.com/callback`
   - 「Update」→「Verify」でテスト
   - 成功メッセージが表示されればOK
4. **Use webhook**: ONにする

---

## 8️⃣ 動作確認

### 8.1 LINE Botを友だち追加

1. LINE Developers Console→「Messaging API」タブ
2. QRコードをスキャン、または友だち追加URL
3. 友だち追加

### 8.2 テストメッセージ

1. `ヘルプ`と送信
2. 使い方が返信されることを確認

### 8.3 画像送信テスト

1. レシピ画像を撮影または用意
2. LINE Botに送信
3. 数秒後、原価計算結果が返信されることを確認

### 8.4 原価表管理テスト（NEW!）

**原価を追加:**
```
追加 トマト 100円/個
```

**原価を確認:**
```
確認 トマト
```

**原価一覧:**
```
原価一覧
```

**原価を削除:**
```
削除 トマト
```

---

## 🐛 トラブルシューティング

### Webhook検証に失敗する

- RenderのURLが正しいか確認
- `/callback`がパスに含まれているか確認
- Renderのデプロイが完了しているか確認（ログを確認）

### 画像を送っても反応がない

1. Renderのログを確認：
   - Dashboard → Logs
2. エラーメッセージを確認
3. Azure Vision APIのクレジットを確認
4. 環境変数が正しく設定されているか確認

### 原価が計算されない

- Supabaseの`cost_master.csv`がアップロードされているか確認
- CSVのフォーマットが正しいか確認
- 材料名が完全一致しているか確認（大文字小文字、スペースに注意）

### Renderがスリープする

- 無料プランは15分間アクセスがないとスリープ
- 最初のアクセスで起動するため30秒程度かかる
- 定期的にアクセスするcronジョブを設定（別サービス）

---

## 📊 モニタリング

### Supabaseでデータ確認

1. Supabase Dashboard→「Table Editor」
2. `recipes`テーブルで保存されたレシピを確認
3. `ingredients`テーブルで材料詳細を確認

### Renderのログ確認

```bash
# リアルタイムログ
Render Dashboard → recipe-bot → Logs
```

---

## 🔄 アップデート手順

```bash
# コードを修正
git add .
git commit -m "Update: xxx"
git push origin main

# Renderが自動的に再デプロイ
```

---

## ✅ チェックリスト

セットアップ完了前に以下を確認：

- [ ] LINE Bot チャネル作成完了
- [ ] Azure Vision リソース作成完了
- [ ] Groq APIキー取得完了
- [ ] Supabase プロジェクト作成完了
- [ ] Supabase テーブル作成完了
- [ ] Supabase ストレージ設定完了
- [ ] 原価表CSV アップロード完了
- [ ] Render デプロイ完了
- [ ] 環境変数 設定完了
- [ ] LINE Webhook URL 設定完了
- [ ] 動作確認（テストメッセージ）完了
- [ ] 動作確認（画像送信）完了

---

**セットアップ完了！お疲れ様でした！** 🎉


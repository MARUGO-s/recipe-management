# クイックスタートガイド

最短でレシピ原価計算Botを動かすための手順です。

## 📝 前提条件

- Pythonがインストールされていること（3.11推奨）
- 各サービスのアカウント作成完了

## ⚡ 5ステップでセットアップ

### ステップ1: APIキーを取得

以下のサービスでAPIキー・設定を取得：

1. **LINE Developers** → Channel Secret, Access Token
2. **Azure Portal** → Computer Vision Endpoint, Key
3. **Groq Console** → API Key
4. **Supabase** → Project URL, Anon Key

### ステップ2: 環境変数を設定

```bash
# env.templateを.envにコピー
cp env.template .env

# .envファイルを編集して各APIキーを設定
nano .env  # または好みのエディタで編集
```

### ステップ3: Supabaseをセットアップ

1. Supabase SQL Editorで`supabase_setup.sql`を実行
2. Storageで`cost-data`バケットを作成
3. `cost_master_sample.csv`を`cost_master.csv`としてアップロード

### ステップ4: ローカルでテスト

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# テストスクリプトを実行
python test_local.py

# 問題なければアプリを起動
python app.py
```

### ステップ5: Renderにデプロイ

```bash
# GitHubにプッシュ
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main

# Renderで:
# 1. New Web Service
# 2. GitHubリポジトリを接続
# 3. 環境変数を設定
# 4. Deploy

# LINEに戻って:
# Webhook URL: https://your-app.onrender.com/callback
```

## ✅ 動作確認

1. LINE Botを友だち追加
2. `ヘルプ`と送信 → 使い方が返信される
3. レシピ画像を送信 → 原価が返信される

### 原価表管理も試してみましょう！

```
追加 トマト 100円/個
確認 トマト
原価一覧
```

## 🆘 問題が発生したら

詳細は`setup_instructions.md`を参照してください。

---

**所要時間: 約30分**（各サービスのアカウント作成含む）


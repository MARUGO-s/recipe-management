# 変更履歴

## [2.0.0] - 2025-10-12

### 🎉 新機能

#### LINEから原価表管理が可能に

- **原価追加**: 自然言語で原価を追加できるようになりました
  - 例: `追加 トマト 100円/個`
  - Groq LLMが自動的に材料名、単価、単位、数量を解析
  
- **原価確認**: 登録済み材料の価格を確認できます
  - 例: `確認 トマト`
  
- **原価削除**: 不要な材料を削除できます
  - 例: `削除 トマト`
  
- **原価一覧**: 登録されている全材料を表示
  - 例: `原価一覧`

#### 新規ファイル

- `cost_master_manager.py`: 原価表管理モジュール
- `USAGE_GUIDE.md`: 詳細な使い方ガイド
- `CHANGELOG.md`: 変更履歴（このファイル）

### ✨ 改善

- `app.py`: 
  - テキストメッセージハンドラーを拡張
  - 原価管理コマンドの処理を追加
  - ヘルプメッセージを更新

- `test_local.py`: 
  - Cost Master Managerのテストを追加

- `README.md`:
  - 原価表管理機能の説明を追加
  - 使い方セクションを追加
  - バージョンを2.0.0に更新

- `setup_instructions.md`:
  - 原価表管理テストの手順を追加

- `QUICKSTART.md`:
  - 原価表管理の動作確認を追加

### 🔧 技術詳細

**追加されたエンドポイント/ハンドラー:**
- `handle_add_cost_command()`: 原価追加処理
- `handle_check_cost_command()`: 原価確認処理
- `handle_delete_cost_command()`: 原価削除処理
- `handle_list_cost_command()`: 原価一覧処理

**新規依存関係:**
なし（既存のGroq APIを活用）

**データベース変更:**
なし（既存の`cost_master`テーブルを使用）

### 💡 使用例

```
# 原価を追加
追加 トマト 100円/個

# 確認
確認 トマト

# 一覧表示
原価一覧

# 削除
削除 トマト
```

---

## [1.0.0] - 2025-10-12

### 初回リリース

#### 主な機能

- LINE Bot統合
- Azure Vision APIによる画像解析（OCR）
- Groq LLMによるレシピテキスト構造化
- Supabaseへのレシピ保存
- 原価計算機能
- 単位変換機能

#### ファイル構成

- `app.py`: メインアプリケーション
- `azure_vision.py`: Azure Vision API処理
- `groq_parser.py`: Groqによるレシピ解析
- `cost_calculator.py`: 原価計算ロジック
- `test_local.py`: ローカルテスト用スクリプト
- `requirements.txt`: Python依存パッケージ
- `Procfile`: Render設定
- `runtime.txt`: Pythonバージョン
- `env.template`: 環境変数テンプレート
- `supabase_setup.sql`: Supabaseテーブル定義
- `cost_master_sample.csv`: 原価表サンプル
- `README.md`: プロジェクト概要
- `setup_instructions.md`: 詳細セットアップ手順
- `QUICKSTART.md`: クイックスタート

#### アーキテクチャ

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

---

## 今後の予定

### 近日実装予定

- [ ] 材料の類義語対応（例: 「豚肉」「豚バラ肉」を同一視）
- [ ] バッチ登録機能（複数の原価を一度に登録）
- [ ] グラフ表示（原価推移、材料別コスト比率）
- [ ] CSVエクスポート機能
- [ ] レシピ検索機能

### 検討中

- [ ] 画像認識精度の向上（複数の画像解析サービスの併用）
- [ ] 音声入力対応
- [ ] Webダッシュボード
- [ ] 複数ユーザー対応（認証機能）
- [ ] 通知機能（価格高騰アラート）

---

**メンテナンス**: 定期的に更新  
**最終更新**: 2025-10-12


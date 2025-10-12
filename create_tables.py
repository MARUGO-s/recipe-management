"""
Supabaseにテーブルを作成するスクリプト（CLI版）
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def create_tables():
    """SQLファイルを読み込んでテーブルを作成"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URLまたはSUPABASE_KEYが設定されていません")
        return False
    
    # SQLファイルを読み込み
    with open('supabase_setup.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # コメント行を除去してSQL文を抽出
    sql_statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        line = line.strip()
        # コメント行をスキップ
        if line.startswith('--'):
            continue
        if line:
            current_statement.append(line)
            # セミコロンで終わる場合は1つの文として追加
            if line.endswith(';'):
                sql_statements.append(' '.join(current_statement))
                current_statement = []
    
    print(f"🔗 Supabaseに接続中: {supabase_url}")
    print(f"📝 実行するSQL文: {len(sql_statements)}個\n")
    
    # 各SQL文を個別に実行（Supabase REST APIを使用）
    success_count = 0
    error_count = 0
    
    # postgRESTのrpcエンドポイントを使用してSQLを実行
    # 注: これは通常のSupabase Python SDKでは直接SQLを実行できないため、
    # 代わりに各テーブルを個別に作成します
    
    from supabase import create_client
    
    try:
        supabase = create_client(supabase_url, supabase_key)
        
        print("✅ Supabaseに接続成功\n")
        print("=" * 60)
        print("📊 テーブル作成中...")
        print("=" * 60)
        
        # テーブル作成のSQLを個別に実行
        # 注: Supabase Python SDKではDDL（CREATE TABLE等）を直接実行できないため、
        # REST APIを直接使用します
        
        # REST APIでSQLを実行する関数
        def execute_sql(sql):
            # Supabaseの管理APIエンドポイント
            # 注: anon keyではDDLを実行できないため、別の方法を使用
            pass
        
        print("\n⚠️  注意: Python SDKではDDL文（CREATE TABLE等）を直接実行できません")
        print("\n以下のいずれかの方法でテーブルを作成してください：\n")
        print("【方法1】Supabase SQL Editorを使用（推奨）")
        print("  1. https://supabase.com/dashboard/project/nnbdzwrndqtsfzobknmj/sql")
        print("  2. 以下のSQLをコピー&ペースト\n")
        
        print("【方法2】curlコマンドで実行")
        print("  以下のコマンドを実行:\n")
        
        # 各SQL文を表示
        for i, sql in enumerate(sql_statements[:10], 1):
            if 'CREATE' in sql.upper() or 'ALTER' in sql.upper():
                print(f"{i}. {sql[:80]}...")
        
        print("\n" + "=" * 60)
        print("💡 または、Supabaseダッシュボードから手動で作成してください")
        print("=" * 60)
        
        return False
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


if __name__ == "__main__":
    create_tables()


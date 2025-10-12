"""
Supabase REST APIでテーブルを作成するスクリプト
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def create_tables_via_api():
    """REST APIでテーブルを作成"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ 環境変数が設定されていません")
        return False
    
    project_ref = supabase_url.replace("https://", "").replace(".supabase.co", "")
    
    print("=" * 70)
    print("🚀 Supabase REST APIでテーブルを作成")
    print("=" * 70)
    
    # SQLファイルを読み込み
    with open('supabase_setup.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Supabase Management APIのエンドポイント
    # 注: Management APIはプロジェクトごとの権限が必要
    # 代わりにPostgREST RPCを使用
    
    print("\n⚠️  REST APIでは直接DDL（CREATE TABLE）を実行できません")
    print("\n最も確実な方法:")
    print("=" * 70)
    print("\n1. 以下のURLをブラウザで開く:")
    print(f"   https://supabase.com/dashboard/project/{project_ref}/sql")
    print("\n2. 「New query」をクリック")
    print("\n3. 以下のSQLをコピー&ペースト:")
    print("\n" + "-" * 70)
    print(sql_content)
    print("-" * 70)
    print("\n4. 「Run」ボタンをクリック")
    print("\n5. 完了したら、以下のコマンドで確認:")
    print("   python3 setup_supabase.py --check")
    print("\n" + "=" * 70)
    
    return False


if __name__ == "__main__":
    create_tables_via_api()


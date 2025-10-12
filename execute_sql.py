"""
SupabaseでSQLを実行するスクリプト（PostgreSQL接続文字列を使用）
"""
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection_string():
    """Supabase接続文字列の情報を表示"""
    supabase_url = os.getenv("SUPABASE_URL")
    
    # URLからプロジェクトIDを抽出
    project_id = supabase_url.replace("https://", "").replace(".supabase.co", "")
    
    print("=" * 70)
    print("🔗 PostgreSQL接続文字列")
    print("=" * 70)
    print("\nSupabaseダッシュボードで接続文字列を取得してください：")
    print(f"\n1. https://supabase.com/dashboard/project/{project_id}/settings/database")
    print("\n2. 「Connection string」セクションで「URI」をコピー")
    print("\n3. パスワードを入力（Supabaseプロジェクト作成時に設定したもの）")
    print("\n4. 以下のコマンドを実行:")
    print("\n   psql 'postgresql://postgres:[YOUR-PASSWORD]@...' -f supabase_setup.sql")
    print("\n" + "=" * 70)
    print("\n💡 または、以下のPythonスクリプトで直接実行できます：")
    print("=" * 70)


def create_tables_with_api():
    """Supabase Management APIを使ってSQLを実行"""
    import subprocess
    
    print("\n📦 必要なパッケージをインストール中...")
    print("=" * 70)
    
    # psycopg2をインストール
    try:
        import psycopg2
        print("✅ psycopg2は既にインストール済み")
    except ImportError:
        print("⚙️  psycopg2をインストール中...")
        result = subprocess.run(['pip3', 'install', 'psycopg2-binary'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ psycopg2のインストール完了")
        else:
            print("❌ psycopg2のインストール失敗")
            print("\n手動でインストールしてください: pip3 install psycopg2-binary")
            return False
    
    print("\n" + "=" * 70)
    print("⚠️  データベースパスワードが必要です")
    print("=" * 70)
    print("\nSupabaseプロジェクト作成時に設定したパスワードを入力してください。")
    print("（パスワードを忘れた場合は、Supabaseダッシュボードでリセットできます）")
    
    return True


if __name__ == "__main__":
    get_connection_string()
    print("\n")
    create_tables_with_api()


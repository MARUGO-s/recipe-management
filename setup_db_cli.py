"""
PostgreSQL接続でSupabaseテーブルを作成するスクリプト
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def create_tables_via_postgres():
    """PostgreSQL接続でテーブルを作成"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    
    if not supabase_url:
        print("❌ SUPABASE_URLが設定されていません")
        return False
    
    # URLからプロジェクトIDを抽出
    project_id = supabase_url.replace("https://", "").replace(".supabase.co", "")
    
    print("=" * 70)
    print("🗄️  Supabaseデータベースにテーブルを作成")
    print("=" * 70)
    print(f"\nプロジェクトID: {project_id}")
    
    # データベースパスワードを環境変数から取得（または入力を求める）
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    
    if not db_password:
        print("\n⚠️  データベースパスワードが設定されていません")
        print("\n以下のいずれかの方法でパスワードを設定してください：\n")
        print("【方法1】環境変数に追加（推奨）")
        print("  .envファイルに以下を追加:")
        print("  SUPABASE_DB_PASSWORD=your_database_password\n")
        print("【方法2】Supabaseダッシュボードから接続文字列を取得")
        print(f"  https://supabase.com/dashboard/project/{project_id}/settings/database\n")
        print("【方法3】パスワードをリセット")
        print(f"  https://supabase.com/dashboard/project/{project_id}/settings/database")
        print("  → Database Password → Reset Database Password\n")
        
        # パスワード入力を試みる
        try:
            import getpass
            db_password = getpass.getpass("\nデータベースパスワードを入力してください（入力は表示されません）: ")
        except:
            print("\n❌ パスワードの入力がキャンセルされました")
            return False
    
    # 接続文字列を構築
    connection_string = f"postgresql://postgres.{project_id}:{db_password}@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
    
    print(f"\n🔗 データベースに接続中...")
    
    try:
        # データベースに接続
        conn = psycopg2.connect(connection_string)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ データベースに接続成功\n")
        
        # SQLファイルを読み込み
        with open('supabase_setup.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        print("📊 テーブルを作成中...\n")
        print("=" * 70)
        
        # SQL文を実行
        try:
            cursor.execute(sql_content)
            print("✅ SQLの実行完了\n")
            
            # 作成されたテーブルを確認
            cursor.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('recipes', 'ingredients', 'cost_master')
                ORDER BY tablename;
            """)
            
            tables = cursor.fetchall()
            
            if tables:
                print("✅ 以下のテーブルが作成されました:")
                for table in tables:
                    print(f"   • {table[0]}")
            else:
                print("⚠️  テーブルの確認に失敗しました")
            
            print("\n" + "=" * 70)
            print("🎉 テーブル作成完了！")
            print("=" * 70)
            
            cursor.close()
            conn.close()
            
            return True
            
        except psycopg2.Error as e:
            print(f"❌ SQL実行エラー: {e}")
            cursor.close()
            conn.close()
            return False
        
    except psycopg2.OperationalError as e:
        print(f"❌ 接続エラー: {e}")
        print("\n以下を確認してください:")
        print("  1. パスワードが正しいか")
        print("  2. ネットワークに接続されているか")
        print("  3. Supabaseプロジェクトが有効か")
        return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


if __name__ == "__main__":
    success = create_tables_via_postgres()
    
    if success:
        print("\n📋 次のステップ:")
        print("  python3 setup_supabase.py --check  # テーブル確認")
        print("  python3 setup_supabase.py --insert-data  # サンプルデータ挿入")
    else:
        print("\n💡 問題が解決しない場合:")
        print("  Supabase SQL Editorで直接SQLを実行することをお勧めします")
        print(f"  https://supabase.com/dashboard/project/nnbdzwrndqtsfzobknmj/sql")


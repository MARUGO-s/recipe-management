"""
Supabaseのテーブルとストレージをセットアップするスクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def setup_database():
    """データベーステーブルを作成"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ SUPABASE_URLまたはSUPABASE_KEYが設定されていません")
        return False
    
    print(f"🔗 Supabaseに接続中: {supabase_url}")
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Supabaseに接続成功")
        
        # SQLファイルを読み込み
        with open('supabase_setup.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # コメント行とストレージ関連のコメントを除去
        sql_statements = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                sql_statements.append(line)
        
        # SQL全体を実行
        full_sql = '\n'.join(sql_statements)
        
        print("\n📊 テーブルを作成中...")
        
        # Supabase Python SDKではRPCを使用してSQLを実行
        # または、postgrestを直接使用
        
        # 個別にテーブルを確認
        try:
            # recipesテーブルの確認
            result = supabase.table('recipes').select('*').limit(1).execute()
            print("✅ recipesテーブル: 既に存在します")
        except Exception as e:
            print(f"⚠️  recipesテーブル: 作成が必要です")
        
        try:
            # ingredientsテーブルの確認
            result = supabase.table('ingredients').select('*').limit(1).execute()
            print("✅ ingredientsテーブル: 既に存在します")
        except Exception as e:
            print(f"⚠️  ingredientsテーブル: 作成が必要です")
        
        try:
            # cost_masterテーブルの確認
            result = supabase.table('cost_master').select('*').limit(1).execute()
            print("✅ cost_masterテーブル: 既に存在します")
        except Exception as e:
            print(f"⚠️  cost_masterテーブル: 作成が必要です")
        
        print("\n" + "="*60)
        print("📝 次のステップ:")
        print("="*60)
        print("\n1. Supabaseダッシュボードで以下を確認してください:")
        print(f"   https://supabase.com/dashboard/project/nnbdzwrndqtsfzobknmj")
        print("\n2. SQL Editorで以下のSQLを実行してください:")
        print("   左メニュー → SQL Editor → New Query")
        print("\n3. 以下の内容をコピー&ペーストして実行:")
        print("-"*60)
        print(open('supabase_setup.sql', 'r').read())
        print("-"*60)
        
        print("\n✅ または、以下のコマンドでテーブルを確認:")
        print("   python setup_supabase.py --check")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def check_tables():
    """テーブルの存在を確認"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    supabase: Client = create_client(supabase_url, supabase_key)
    
    tables = ['recipes', 'ingredients', 'cost_master']
    
    print("\n📊 テーブル確認中...\n")
    
    all_exist = True
    for table in tables:
        try:
            result = supabase.table(table).select('*').limit(1).execute()
            print(f"✅ {table:20s} → 存在します (データ件数: {len(result.data)}件)")
        except Exception as e:
            print(f"❌ {table:20s} → 存在しません")
            all_exist = False
    
    if all_exist:
        print("\n✅ すべてのテーブルが正常に作成されています！")
        print("\n次のステップ:")
        print("1. ストレージバケット 'cost-data' を作成")
        print("2. cost_master_sample.csv をアップロード")
    else:
        print("\n⚠️  一部のテーブルが存在しません")
        print("Supabase SQL Editorで supabase_setup.sql を実行してください")


def insert_sample_data():
    """サンプル原価データを挿入"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("\n📥 サンプル原価データを挿入中...\n")
    
    # CSVを読み込み
    import csv
    
    try:
        with open('cost_master_sample.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            count = 0
            for row in reader:
                try:
                    data = {
                        'ingredient_name': row['ingredient_name'],
                        'unit_price': float(row['unit_price']),
                        'reference_unit': row['reference_unit'],
                        'reference_quantity': float(row['reference_quantity'])
                    }
                    
                    # 既存データをチェック
                    existing = supabase.table('cost_master')\
                        .select('*')\
                        .eq('ingredient_name', row['ingredient_name'])\
                        .execute()
                    
                    if existing.data:
                        # 更新
                        supabase.table('cost_master')\
                            .update(data)\
                            .eq('ingredient_name', row['ingredient_name'])\
                            .execute()
                        print(f"🔄 更新: {row['ingredient_name']}")
                    else:
                        # 挿入
                        supabase.table('cost_master').insert(data).execute()
                        print(f"✅ 追加: {row['ingredient_name']}")
                    
                    count += 1
                    
                except Exception as e:
                    print(f"❌ エラー ({row['ingredient_name']}): {e}")
        
        print(f"\n✅ {count}件の原価データを登録しました")
        
    except Exception as e:
        print(f"❌ エラー: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--check':
            check_tables()
        elif sys.argv[1] == '--insert-data':
            insert_sample_data()
    else:
        setup_database()


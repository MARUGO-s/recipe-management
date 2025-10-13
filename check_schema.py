#!/usr/bin/env python3
"""
Supabaseテーブル構造を確認するスクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    """テーブル構造を確認"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        print("🔍 テーブル構造確認中...")
        
        # recipesテーブルの構造を確認
        try:
            # サンプルデータを1件取得して構造を確認
            result = supabase.table('recipes').select('*').limit(1).execute()
            print("✅ recipesテーブルが存在します")
            
            if result.data:
                print("📊 recipesテーブルのカラム:")
                for key in result.data[0].keys():
                    print(f"  - {key}")
            else:
                print("📊 recipesテーブルは空です")
                
        except Exception as e:
            print(f"⚠️ recipesテーブル確認エラー: {e}")
        
        # ingredientsテーブルの構造を確認
        try:
            result = supabase.table('ingredients').select('*').limit(1).execute()
            print("✅ ingredientsテーブルが存在します")
            
            if result.data:
                print("📊 ingredientsテーブルのカラム:")
                for key in result.data[0].keys():
                    print(f"  - {key}")
            else:
                print("📊 ingredientsテーブルは空です")
                
        except Exception as e:
            print(f"⚠️ ingredientsテーブル確認エラー: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

if __name__ == "__main__":
    print("🚀 テーブル構造確認開始")
    check_schema()

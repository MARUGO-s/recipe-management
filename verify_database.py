#!/usr/bin/env python3
"""
データベース接続とデータの整合性を確認するスクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def verify_database():
    """データベースの整合性を確認"""
    try:
        # 環境変数の確認
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        print("🔍 環境変数の確認:")
        print(f"  SUPABASE_URL: {supabase_url[:50]}..." if supabase_url else "  SUPABASE_URL: 未設定")
        print(f"  SUPABASE_KEY: {'設定済み' if supabase_key else '未設定'}")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        # Supabaseクライアントを作成
        supabase = create_client(supabase_url, supabase_key)
        
        # データベース接続テスト
        print("\n🔗 データベース接続テスト...")
        result = supabase.table('cost_master').select('id', count='exact').execute()
        
        print(f"✅ 接続成功")
        print(f"📊 現在のデータ件数: {result.count}件")
        
        # テーブル構造の確認
        print("\n🏗️ テーブル構造の確認...")
        sample = supabase.table('cost_master').select('*').limit(1).execute()
        
        if sample.data:
            columns = list(sample.data[0].keys())
            print(f"📋 カラム一覧: {columns}")
            
            # unit_columnの存在確認
            if 'unit_column' in columns:
                print("✅ unit_columnカラムが存在します")
            else:
                print("❌ unit_columnカラムが存在しません")
        else:
            print("📝 テーブルは空です（正常）")
        
        # 最新の更新日時を確認
        print("\n⏰ 最新の更新日時を確認...")
        result = supabase.table('cost_master').select('updated_at').order('updated_at', desc=True).limit(1).execute()
        
        if result.data:
            print(f"📅 最新更新日時: {result.data[0]['updated_at']}")
        else:
            print("📅 データが存在しません")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_database()

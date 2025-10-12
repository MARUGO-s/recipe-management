#!/usr/bin/env python3
"""
最新のデータを確認するスクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_latest_data():
    """最新のデータを確認"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 最新の10件を確認
        result = supabase.table('cost_master').select('ingredient_name, capacity, unit, unit_column, unit_price, updated_at').order('updated_at', desc=True).limit(10).execute()
        
        print("📊 最新のデータ（更新日時順）:")
        for i, item in enumerate(result.data, 1):
            print(f"{i}. {item['ingredient_name']}")
            print(f"   容量: {item['capacity']}, 単位: {item['unit']}, 単位列: {item['unit_column']}, 単価: ¥{item['unit_price']}")
            print(f"   更新日時: {item['updated_at']}")
            print()
        
        # unit_columnの値の種類を確認
        print("🔍 unit_columnの値の種類:")
        unit_columns = set()
        for item in result.data:
            if item['unit_column']:
                unit_columns.add(item['unit_column'])
        
        print(f"   発見された値: {list(unit_columns)}")
        
        # 数値のunit_columnをチェック
        numeric_units = [item for item in result.data if item['unit_column'] and str(item['unit_column']).replace('.', '').isdigit()]
        if numeric_units:
            print(f"⚠️ 数値のunit_column: {len(numeric_units)}件")
            for item in numeric_units[:3]:
                print(f"   {item['ingredient_name']}: unit_column={item['unit_column']}")
        else:
            print("✅ 数値のunit_columnは見つかりませんでした")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_latest_data()

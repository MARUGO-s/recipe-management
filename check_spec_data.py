#!/usr/bin/env python3
"""
規格データの確認スクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def check_spec_data():
    """規格データの確認"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 規格があるレコードを取得
        result = supabase.table('cost_master').select('ingredient_name, spec, unit_column').neq('spec', '').limit(10).execute()
        
        print("🔍 規格データの確認:")
        print("=" * 60)
        
        if result.data:
            for item in result.data:
                print(f"材料名: {item['ingredient_name']}")
                print(f"規格: '{item['spec']}'")
                print(f"単位列: '{item['unit_column']}'")
                print("-" * 40)
        else:
            print("規格データが見つかりませんでした")
            
        # 全データの規格分布を確認
        all_data = supabase.table('cost_master').select('spec').execute()
        
        spec_values = {}
        for item in all_data.data:
            val = item.get('spec') or '(空)'
            spec_values[val] = spec_values.get(val, 0) + 1
        
        print(f"\n📊 規格データの分布:")
        for val, count in sorted(spec_values.items(), key=lambda x: -x[1]):
            if val != '(空)':  # 空でないもののみ表示
                print(f"   '{val}': {count}件")
        
        if '(空)' in spec_values:
            print(f"   '(空)': {spec_values['(空)']}件")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_spec_data()

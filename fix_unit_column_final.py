#!/usr/bin/env python3
"""
unit_columnの数値を修正する最終スクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def fix_unit_column_final():
    """unit_columnの数値を修正"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 数値のunit_columnを持つレコードを取得
        result = supabase.table('cost_master').select('id, ingredient_name, unit_column, unit').execute()
        
        numeric_records = []
        for item in result.data:
            if item['unit_column'] and str(item['unit_column']).replace('.', '').isdigit():
                numeric_records.append(item)
        
        print(f"🔍 数値のunit_columnを持つレコード: {len(numeric_records)}件")
        
        if not numeric_records:
            print("✅ 修正が必要なレコードはありません")
            return
        
        # 修正ルール
        fix_rules = {
            '0.00': '',  # 空文字列に
            '1.00': '個',  # 個に
            '12.00': 'PC',  # PCに
        }
        
        # 修正実行
        fixed_count = 0
        for record in numeric_records:
            unit_column_value = str(record['unit_column'])
            
            # 修正ルールに従って新しい値を決定
            if unit_column_value in fix_rules:
                new_unit_column = fix_rules[unit_column_value]
            else:
                # デフォルトはunit列からコピー
                new_unit_column = record['unit'] or '個'
            
            # データベースを更新
            supabase.table('cost_master').update({
                'unit_column': new_unit_column
            }).eq('id', record['id']).execute()
            
            fixed_count += 1
            print(f"✅ 修正: {record['ingredient_name']} ({unit_column_value} → {new_unit_column})")
        
        print(f"\n🎯 修正完了: {fixed_count}件")
        
        # 修正後の確認
        result = supabase.table('cost_master').select('ingredient_name, unit_column').limit(5).execute()
        print("\n📊 修正後のサンプル:")
        for item in result.data:
            print(f"  {item['ingredient_name']}: unit_column={item['unit_column']}")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_unit_column_final()

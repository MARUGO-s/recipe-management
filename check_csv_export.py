#!/usr/bin/env python3
"""
現在のデータベースからCSVファイルをエクスポートして確認
"""
import os
import csv
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def export_current_data():
    """現在のデータをCSVにエクスポート"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 原価マスターデータを取得
        result = supabase.table('cost_master').select('*').execute()
        
        if not result.data:
            print("📝 データがありません")
            return
        
        # CSVファイルに出力
        filename = 'current_cost_master.csv'
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if result.data:
                fieldnames = list(result.data[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in result.data:
                    writer.writerow(row)
        
        print(f"✅ CSVファイルをエクスポートしました: {filename}")
        print(f"📊 データ件数: {len(result.data)}件")
        
        # 最初の5行を表示
        print("\n📋 データサンプル（最初の5行）:")
        for i, item in enumerate(result.data[:5], 1):
            print(f"{i}. {item['ingredient_name']}")
            print(f"   容量: {item['capacity']}")
            print(f"   単位: {item['unit']}")
            print(f"   単位列: '{item['unit_column']}'")
            print(f"   単価: ¥{item['unit_price']}")
            print()
        
        # unit_columnの値の分布
        unit_values = {}
        for item in result.data:
            val = item['unit_column'] or '(空)'
            unit_values[val] = unit_values.get(val, 0) + 1
        
        print("🔍 unit_columnの値の分布:")
        for val, count in sorted(unit_values.items(), key=lambda x: -x[1]):
            print(f"   '{val}': {count}件")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    export_current_data()

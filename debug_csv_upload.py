#!/usr/bin/env python3
"""
CSVアップロード処理のデバッグスクリプト
"""
import csv
import io
import re

def extract_capacity_from_spec(spec_text, product_name="", unit_column=""):
    """
    規格や商品名、単位列から容量を抽出する関数
    """
    if not spec_text:
        spec_text = ""
    
    # 規格から「×入数」パターンを除去
    spec_cleaned = re.sub(r'×\d+$', '', spec_text.strip())
    
    # 容量パターンマッチング（優先順位順）
    patterns = [
        # 重量系
        (r'(\d+(?:\.\d+)?)\s*kg', lambda m: (float(m.group(1)) * 1000, 'g')),
        (r'(\d+(?:\.\d+)?)\s*g', lambda m: (float(m.group(1)), 'g')),
        # 容量系
        (r'(\d+(?:\.\d+)?)\s*L', lambda m: (float(m.group(1)) * 1000, 'ml')),
        (r'(\d+(?:\.\d+)?)\s*ml', lambda m: (float(m.group(1)), 'ml')),
        # 個数系
        (r'(\d+(?:\.\d+)?)\s*pc', lambda m: (float(m.group(1)), 'pc')),
        (r'(\d+(?:\d+)?)\s*個', lambda m: (float(m.group(1)), '個')),
        (r'(\d+(?:\.\d+)?)\s*本', lambda m: (float(m.group(1)), '本')),
        (r'(\d+(?:\.\d+)?)\s*枚', lambda m: (float(m.group(1)), '枚')),
        # パック系
        (r'(\d+(?:\.\d+)?)\s*p', lambda m: (float(m.group(1)), 'p')),
    ]
    
    # 規格から容量を抽出
    for pattern, converter in patterns:
        match = re.search(pattern, spec_cleaned, re.IGNORECASE)
        if match:
            capacity, unit = converter(match)
            return (capacity, unit, unit_column)
    
    # 商品名から容量を抽出（規格で見つからない場合）
    if product_name:
        for pattern, converter in patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                capacity, unit = converter(match)
                return (capacity, unit, unit_column)
    
    # デフォルト値
    return (1, '個', unit_column)

def debug_csv_file():
    """CSVファイルの処理をデバッグ"""
    try:
        with open('/Users/yoshito/recipe-management/set20250911.csv', 'r', encoding='cp932') as f:
            csv_reader = csv.reader(f)
            
            extracted_materials = {}
            processed_count = 0
            
            print("🔍 CSVファイルの処理デバッグ開始")
            print("=" * 60)
            
            for row_num, row in enumerate(csv_reader, 1):
                try:
                    if not row or row[0] != 'D': 
                        continue

                    if row_num <= 5:  # 最初の5行のみデバッグ
                        print(f"\n📋 行 {row_num}:")
                        print(f"  商品名 (14列目): '{row[14] if len(row) > 14 else 'N/A'}'")
                        print(f"  規格 (16列目): '{row[15] if len(row) > 15 else 'N/A'}'")
                        print(f"  単位列 (21列目): '{row[20] if len(row) > 20 else 'N/A'}'")
                        print(f"  単価 (18列目): '{row[18] if len(row) > 18 else 'N/A'}'")
                        
                        # extract_capacity_from_specの結果を確認
                        product = row[14].strip() if len(row) > 14 else ""
                        spec = row[15].strip() if len(row) > 15 else ""
                        unit_column = row[20].strip() if len(row) > 20 else ""
                        
                        capacity, unit, unit_column_result = extract_capacity_from_spec(spec, product, unit_column)
                        
                        print(f"  📊 抽出結果:")
                        print(f"    capacity: {capacity}")
                        print(f"    unit: '{unit}'")
                        print(f"    unit_column_result: '{unit_column_result}'")
                        print(f"    spec: '{spec}'")
                        
                        if unit_column != unit_column_result:
                            print(f"  ⚠️  unit_columnが変更されました！")
                            print(f"    入力: '{unit_column}'")
                            print(f"    出力: '{unit_column_result}'")

                    price_str = row[18].strip() if len(row) > 18 else ""
                    product = row[14].strip() if len(row) > 14 else ""
                    if not product or not price_str: 
                        continue

                    price = float(price_str.replace(',', ''))
                    if price <= 0: 
                        continue

                    supplier = row[8].strip() if len(row) > 8 else ""
                    spec = row[15].strip() if len(row) > 15 else ""
                    unit_column = row[20].strip() if len(row) > 20 else ""
                    
                    capacity, unit, unit_column_data = extract_capacity_from_spec(spec, product, unit_column)
                    
                    # (商品名, 取引先名) のタプルをキーに重複排除
                    item_key = (product, supplier)
                    if item_key not in extracted_materials or price < extracted_materials[item_key]['price']:
                        extracted_materials[item_key] = {
                            'product': product,
                            'supplier': supplier,
                            'capacity': capacity,
                            'unit': unit,
                            'unit_column': unit_column_data,
                            'price': price
                        }
                    processed_count += 1
                    
                except (IndexError, ValueError) as e:
                    print(f"行 {row_num} でエラー: {e}")
                    continue
            
            print(f"\n📊 処理結果:")
            print(f"  処理行数: {processed_count}")
            print(f"  抽出材料数: {len(extracted_materials)}")
            
            print(f"\n🔍 抽出された材料のサンプル（最初の5件）:")
            for i, (key, item) in enumerate(list(extracted_materials.items())[:5], 1):
                print(f"{i}. {item['product']}")
                print(f"   capacity: {item['capacity']}")
                print(f"   unit: '{item['unit']}'")
                print(f"   unit_column: '{item['unit_column']}'")
                print(f"   spec: '{item.get('spec', '')}'")
                print(f"   price: ¥{item['price']}")
                print()
            
            # unit_columnの値の分布を確認
            unit_column_values = {}
            for item in extracted_materials.values():
                val = item['unit_column'] or '(空)'
                unit_column_values[val] = unit_column_values.get(val, 0) + 1
            
            print(f"🔍 unit_columnの値の分布:")
            for val, count in sorted(unit_column_values.items(), key=lambda x: -x[1]):
                print(f"   '{val}': {count}件")
            
            # specの値の分布を確認
            spec_values = {}
            for item in extracted_materials.values():
                val = item.get('spec') or '(空)'
                spec_values[val] = spec_values.get(val, 0) + 1
            
            print(f"\n🔍 specの値の分布:")
            for val, count in sorted(spec_values.items(), key=lambda x: -x[1]):
                if val != '(空)' or count > 0:  # 空でないもののみ表示
                    print(f"   '{val}': {count}件")
                
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_csv_file()

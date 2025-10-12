#!/usr/bin/env python3
"""
全ての問題を診断するスクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def diagnose_all():
    """全ての問題を診断"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        print("=" * 60)
        print("🔍 完全診断レポート")
        print("=" * 60)
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 1. データベース接続確認
        print("\n【1】データベース接続:")
        result = supabase.table('cost_master').select('id', count='exact').execute()
        print(f"   ✅ 接続成功")
        print(f"   📊 総データ件数: {result.count}件")
        
        # 2. unit_columnの値を全件チェック
        print("\n【2】unit_columnの値の分布:")
        all_data = supabase.table('cost_master').select('unit_column').execute()
        
        unit_column_values = {}
        for item in all_data.data:
            val = item['unit_column'] or '(空)'
            unit_column_values[val] = unit_column_values.get(val, 0) + 1
        
        for val, count in sorted(unit_column_values.items(), key=lambda x: -x[1]):
            print(f"   '{val}': {count}件")
        
        # 3. 数値のunit_columnをチェック
        print("\n【3】数値のunit_columnチェック:")
        numeric_count = 0
        numeric_examples = []
        
        for item in all_data.data:
            val = item['unit_column']
            if val and str(val).replace('.', '').replace('-', '').isdigit():
                numeric_count += 1
                if len(numeric_examples) < 5:
                    # 材料名も取得
                    full_item = supabase.table('cost_master').select('ingredient_name, unit_column').eq('unit_column', val).limit(1).execute()
                    if full_item.data:
                        numeric_examples.append(f"{full_item.data[0]['ingredient_name']}: {val}")
        
        if numeric_count > 0:
            print(f"   ❌ 数値のunit_column: {numeric_count}件")
            print(f"   例:")
            for ex in numeric_examples:
                print(f"      - {ex}")
        else:
            print(f"   ✅ 数値のunit_columnは見つかりませんでした")
        
        # 4. 最新の5件を詳細表示
        print("\n【4】最新の5件（詳細）:")
        latest = supabase.table('cost_master').select('*').order('updated_at', desc=True).limit(5).execute()
        
        for i, item in enumerate(latest.data, 1):
            print(f"\n   {i}. {item['ingredient_name']}")
            print(f"      容量: {item['capacity']}")
            print(f"      単位: {item['unit']}")
            print(f"      単位列: '{item['unit_column']}'")
            print(f"      単価: ¥{item['unit_price']}")
            print(f"      更新日時: {item['updated_at']}")
        
        # 5. CSVの16列目に相当するデータの確認
        print("\n【5】CSVの16列目（単位列）の問題:")
        print("   CSVファイルの16列目には以下のような値が入っていますか？")
        print("   - 数値（0.00, 1.00, 12.00など）")
        print("   - 文字列（個, PC, ml, gなど）")
        print("   - 空欄")
        
        # 6. アプリケーションコードの確認
        print("\n【6】アプリケーションコードの確認:")
        app_py_path = "/Users/yoshito/recipe-management/app.py"
        if os.path.exists(app_py_path):
            with open(app_py_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'unit_column' in content:
                    print("   ✅ app.pyにunit_columnの処理が含まれています")
                else:
                    print("   ❌ app.pyにunit_columnの処理が含まれていません")
        
        print("\n" + "=" * 60)
        print("🎯 次のステップ:")
        print("=" * 60)
        print("1. 上記の診断結果をスクリーンショットで送ってください")
        print("2. LINE Botで「赤水菜」と入力した時の返信をスクリーンショットで送ってください")
        print("3. ウェブ管理画面のスクリーンショットを送ってください")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_all()

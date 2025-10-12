"""
ローカル環境でのテストスクリプト
各モジュールの動作確認用
"""
import os
from dotenv import load_dotenv

load_dotenv()

def test_azure_vision():
    """Azure Vision APIのテスト"""
    print("\n=== Azure Vision API テスト ===")
    try:
        from azure_vision import AzureVisionAnalyzer
        analyzer = AzureVisionAnalyzer()
        print("✓ Azure Vision初期化成功")
        
        # テスト画像URL（公開されているサンプル画像）
        test_url = "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-sample-data-files/master/ComputerVision/Images/printed_text.jpg"
        result = analyzer.analyze_image_from_url(test_url)
        
        if result:
            print(f"✓ OCR成功")
            print(f"抽出テキスト: {result[:100]}...")
        else:
            print("✗ OCR失敗")
    except Exception as e:
        print(f"✗ エラー: {e}")


def test_groq_parser():
    """Groq Parserのテスト"""
    print("\n=== Groq Parser テスト ===")
    try:
        from groq_parser import GroqRecipeParser
        parser = GroqRecipeParser()
        print("✓ Groq初期化成功")
        
        test_text = """
        カレー（2人前）
        
        材料:
        玉ねぎ 1個
        にんじん 1本
        じゃがいも 2個
        豚肉 200g
        カレールウ 4皿分
        水 400ml
        """
        
        result = parser.parse_recipe_text(test_text)
        
        if result:
            print("✓ レシピ解析成功")
            print(f"料理名: {result['recipe_name']}")
            print(f"人数: {result['servings']}人前")
            print(f"材料数: {len(result['ingredients'])}件")
        else:
            print("✗ レシピ解析失敗")
    except Exception as e:
        print(f"✗ エラー: {e}")


def test_cost_calculator():
    """Cost Calculatorのテスト"""
    print("\n=== Cost Calculator テスト ===")
    try:
        from cost_calculator import CostCalculator
        calculator = CostCalculator()
        print("✓ Cost Calculator初期化成功")
        
        # 原価表の読み込み
        try:
            calculator.load_cost_master_from_storage()
            print("✓ ストレージから原価表読み込み成功")
        except:
            calculator._load_cost_master_from_db()
            print("✓ DBから原価表読み込み成功")
        
        # テスト材料
        test_ingredients = [
            {"name": "玉ねぎ", "quantity": 1.0, "unit": "個"},
            {"name": "にんじん", "quantity": 1.0, "unit": "本"},
            {"name": "豚肉", "quantity": 200.0, "unit": "g"}
        ]
        
        result = calculator.calculate_recipe_cost(test_ingredients)
        
        print("✓ 原価計算成功")
        print(f"合計原価: ¥{result['total_cost']:.2f}")
        print(f"計算済み材料: {len([i for i in result['ingredients_with_cost'] if i['cost'] is not None])}件")
        
        if result['missing_ingredients']:
            print(f"未登録材料: {result['missing_ingredients']}")
        
    except Exception as e:
        print(f"✗ エラー: {e}")


def test_cost_master_manager():
    """Cost Master Managerのテスト"""
    print("\n=== Cost Master Manager テスト ===")
    try:
        from cost_master_manager import CostMasterManager
        manager = CostMasterManager()
        print("✓ Cost Master Manager初期化成功")
        
        # テスト1: 自然言語から解析
        test_texts = [
            "トマト 100円/個",
            "豚バラ肉 300円/100g",
            "キャベツ1玉150円"
        ]
        
        print("\n【自然言語解析テスト】")
        for text in test_texts:
            print(f"  入力: {text}")
            result = manager.parse_cost_text(text)
            if result:
                print(f"  ✓ 解析成功: {result['ingredient_name']} - ¥{result['unit_price']}/{result['reference_quantity']}{result['reference_unit']}")
            else:
                print("  ✗ 解析失敗")
        
        # テスト2: 原価一覧の取得
        print("\n【原価一覧取得テスト】")
        costs = manager.list_all_costs(limit=5)
        if costs:
            print(f"  ✓ 取得成功: {len(costs)}件")
            for cost in costs[:3]:
                print(f"    - {cost['ingredient_name']}: ¥{cost['unit_price']}/{cost['reference_quantity']}{cost['reference_unit']}")
        else:
            print("  原価表が空です")
        
    except Exception as e:
        print(f"✗ エラー: {e}")


def test_supabase_connection():
    """Supabase接続テスト"""
    print("\n=== Supabase接続テスト ===")
    try:
        from supabase import create_client
        
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            print("✗ Supabase設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        print("✓ Supabase初期化成功")
        
        # テーブルの存在確認
        try:
            response = supabase.table('recipes').select('*').limit(1).execute()
            print("✓ recipesテーブル接続成功")
        except Exception as e:
            print(f"✗ recipesテーブルエラー: {e}")
        
        try:
            response = supabase.table('ingredients').select('*').limit(1).execute()
            print("✓ ingredientsテーブル接続成功")
        except Exception as e:
            print(f"✗ ingredientsテーブルエラー: {e}")
        
        try:
            response = supabase.table('cost_master').select('*').limit(1).execute()
            print("✓ cost_masterテーブル接続成功")
            print(f"  登録済み材料数: {len(response.data)}件")
        except Exception as e:
            print(f"✗ cost_masterテーブルエラー: {e}")
        
    except Exception as e:
        print(f"✗ エラー: {e}")


def main():
    """すべてのテストを実行"""
    print("=" * 50)
    print("レシピ原価計算Bot - ローカルテスト")
    print("=" * 50)
    
    # 環境変数チェック
    print("\n=== 環境変数チェック ===")
    required_vars = [
        'LINE_CHANNEL_SECRET',
        'LINE_CHANNEL_ACCESS_TOKEN',
        'AZURE_VISION_ENDPOINT',
        'AZURE_VISION_KEY',
        'GROQ_API_KEY',
        'SUPABASE_URL',
        'SUPABASE_KEY'
    ]
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✓ {var}: 設定済み")
        else:
            print(f"✗ {var}: 未設定")
    
    # 各モジュールのテスト
    test_supabase_connection()
    test_azure_vision()
    test_groq_parser()
    test_cost_calculator()
    test_cost_master_manager()
    
    print("\n" + "=" * 50)
    print("テスト完了")
    print("=" * 50)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
レシピテーブルの詳細調査スクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def debug_recipes():
    """レシピテーブルの詳細を調査"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        print("🔍 レシピテーブルの詳細調査...")
        
        # レシピテーブルの全データを取得
        result = supabase.table('recipes').select('*').order('created_at', desc=True).execute()
        
        print(f"📊 レシピ総数: {len(result.data)}件")
        
        for i, recipe in enumerate(result.data, 1):
            print(f"\n--- レシピ {i} ---")
            print(f"ID: {recipe['id']}")
            print(f"料理名: '{recipe['recipe_name']}'")
            print(f"人数: {recipe['servings']}人前")
            print(f"合計原価: ¥{recipe['total_cost']}")
            print(f"作成日: {recipe['created_at']}")
            print(f"更新日: {recipe['updated_at']}")
            
            # 料理名が空またはNoneの場合の詳細
            if not recipe['recipe_name'] or recipe['recipe_name'] == '':
                print("⚠️ 料理名が空です！")
                print(f"   recipe_name type: {type(recipe['recipe_name'])}")
                print(f"   recipe_name repr: {repr(recipe['recipe_name'])}")
        
        # 材料テーブルも確認
        print(f"\n🔍 材料テーブルの確認...")
        ingredients_result = supabase.table('ingredients').select('*').execute()
        print(f"📊 材料総数: {len(ingredients_result.data)}件")
        
        # レシピID別に材料をグループ化
        recipe_ingredients = {}
        for ingredient in ingredients_result.data:
            recipe_id = ingredient['recipe_id']
            if recipe_id not in recipe_ingredients:
                recipe_ingredients[recipe_id] = []
            recipe_ingredients[recipe_id].append(ingredient)
        
        print(f"\n📊 レシピ別材料数:")
        for recipe_id, ingredients in recipe_ingredients.items():
            print(f"  レシピID {recipe_id}: {len(ingredients)}種類の材料")
            
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 レシピテーブル調査開始")
    debug_recipes()

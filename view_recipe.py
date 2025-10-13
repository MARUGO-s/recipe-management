#!/usr/bin/env python3
"""
レシピ詳細をコンソールで確認するスクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def view_recipe(recipe_id=None):
    """レシピ詳細を表示"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        if recipe_id:
            # 特定のレシピを表示
            recipe_response = supabase.table('recipes').select('*').eq('id', recipe_id).execute()
            if not recipe_response.data:
                print(f"❌ レシピID {recipe_id} が見つかりません")
                return False
            recipes = recipe_response.data
        else:
            # 最新のレシピを表示
            recipes_response = supabase.table('recipes').select('*').order('created_at', desc=True).limit(1).execute()
            if not recipes_response.data:
                print("❌ レシピが見つかりません")
                return False
            recipes = recipes_response.data
        
        for recipe in recipes:
            print(f"\n🍽️ レシピ詳細: {recipe['recipe_name']}")
            print(f"📊 ID: {recipe['id']}")
            print(f"👥 人数: {recipe['servings']}人前")
            print(f"💰 合計原価: ¥{recipe['total_cost']:.2f}")
            print(f"📅 作成日: {recipe['created_at']}")
            
            # 材料情報を取得
            ingredients_response = supabase.table('ingredients').select('*').eq('recipe_id', recipe['id']).order('ingredient_name').execute()
            ingredients = ingredients_response.data if ingredients_response.data else []
            
            print(f"\n📝 材料リスト ({len(ingredients)}種類):")
            for i, ingredient in enumerate(ingredients, 1):
                cost_info = f"¥{ingredient['cost']:.2f}" if ingredient.get('cost') and ingredient['cost'] > 0 else "未登録"
                print(f"  {i:2d}. {ingredient['ingredient_name']} {ingredient['quantity']}{ingredient['unit']} ({cost_info})")
            
            print(f"\n🌐 詳細URL: https://recipe-management-nd00.onrender.com/recipe/{recipe['id']}")
            
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

def list_recipes():
    """レシピ一覧を表示"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        recipes_response = supabase.table('recipes').select('*').order('created_at', desc=True).execute()
        recipes = recipes_response.data if recipes_response.data else []
        
        print(f"📚 レシピ一覧 ({len(recipes)}件):")
        for i, recipe in enumerate(recipes, 1):
            print(f"  {i:2d}. {recipe['recipe_name']} ({recipe['servings']}人前) - ID: {recipe['id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "list":
            list_recipes()
        else:
            # レシピIDを指定
            view_recipe(sys.argv[1])
    else:
        # 最新のレシピを表示
        print("🚀 最新のレシピ詳細を表示中...")
        view_recipe()

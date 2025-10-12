"""
原価表の管理モジュール（追加・更新・削除）
"""
import os
from typing import Dict, Optional
from decimal import Decimal
from supabase import create_client, Client
from groq import Groq
import json
from dotenv import load_dotenv

load_dotenv()


class CostMasterManager:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        # サービスキーを優先的に使用し、なければanonキーにフォールバック
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_key:
            print("警告: CostMasterManagerがサービスキーではなくanonキーを使用しています。")
            supabase_key = os.getenv("SUPABASE_KEY")

        groq_api_key = os.getenv("GROQ_API_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabaseの設定が不足しています。")
        
        if not groq_api_key:
            raise ValueError("GROQ_API_KEYが設定されていません。")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.groq_client = Groq(api_key=groq_api_key)
    
    def parse_cost_text(self, text: str) -> Optional[Dict]:
        """
        自然言語のテキストから原価情報を抽出
        
        Args:
            text: ユーザーが入力したテキスト
            
        Returns:
            {
                "ingredient_name": "材料名",
                "capacity": 100.0,
                "unit": "g",
                "unit_price": 100.0
            }
        """
        try:
            # シンプルな正規表現による解析
            import re
            
            # パターン1: 「材料名 価格円/単位」
            match = re.match(r'(.+?)\s+(\d+(?:\.\d+)?)円/(\d+(?:\.\d+)?)?([a-zA-Z個gml本玉丁袋kgL]+)', text)
            if match:
                ingredient_name = match.group(1).strip()
                price = float(match.group(2))
                capacity = float(match.group(3)) if match.group(3) else 1.0
                unit = match.group(4)
                
                # 単位変換
                if unit == 'kg':
                    capacity *= 1000
                    unit = 'g'
                elif unit == 'L':
                    capacity *= 1000
                    unit = 'ml'
                
                return {
                    "ingredient_name": ingredient_name,
                    "capacity": capacity,
                    "unit": unit,
                    "unit_price": price
                }
            
            # パターン2: 「材料名 数値 単位」（通貨単位なし）
            match = re.match(r'(.+?)\s+(\d+(?:\.\d+)?)\s+([a-zA-Z個gml本玉丁袋kgL]+)', text)
            if match:
                ingredient_name = match.group(1).strip()
                price = float(match.group(2))
                unit = match.group(3)
                
                # 容量は1.0に設定（単価として解釈）
                capacity = 1.0
                
                # 単位変換
                if unit == 'kg':
                    capacity *= 1000
                    unit = 'g'
                elif unit == 'L':
                    capacity *= 1000
                    unit = 'ml'
                
                return {
                    "ingredient_name": ingredient_name,
                    "capacity": capacity,
                    "unit": unit,
                    "unit_price": price
                }
            
            # パターン3: 「材料名 容量単位 価格円」
            match = re.match(r'(.+?)\s+(\d+(?:\.\d+)?)([a-zA-Z個gml本玉丁袋kgL]+)\s+(\d+(?:\.\d+)?)円', text)
            if match:
                ingredient_name = match.group(1).strip()
                capacity = float(match.group(2))
                unit = match.group(3)
                price = float(match.group(4))
                
                # 単位変換
                if unit == 'kg':
                    capacity *= 1000
                    unit = 'g'
                elif unit == 'L':
                    capacity *= 1000
                    unit = 'ml'
                
                return {
                    "ingredient_name": ingredient_name,
                    "capacity": capacity,
                    "unit": unit,
                    "unit_price": price
                }
            
            # どのパターンにもマッチしない場合
            return None
            
        except Exception as e:
            print(f"原価テキスト解析エラー: {e}")
            return None
    
    def _validate_cost_data(self, data: Dict) -> bool:
        """
        原価データの妥当性をチェック
        """
        if not isinstance(data, dict):
            return False
        
        required_fields = ["ingredient_name", "capacity", "unit", "unit_price"]
        for field in required_fields:
            if field not in data:
                return False
        
        if not data["ingredient_name"] or not isinstance(data["ingredient_name"], str):
            return False
        
        if not isinstance(data["capacity"], (int, float)) or data["capacity"] <= 0:
            return False
        
        if not data["unit"] or not isinstance(data["unit"], str):
            return False
        
        if not isinstance(data["unit_price"], (int, float)) or data["unit_price"] <= 0:
            return False
        
        return True
    
    def add_or_update_cost(self, ingredient_name: str, capacity: float, 
                           unit: str, unit_price: float) -> bool:
        """
        原価表に材料を追加または更新
        """
        try:
            from datetime import datetime
            
            # まず既存のレコードをチェック
            existing = self.supabase.table('cost_master')\
                .select('*')\
                .eq('ingredient_name', ingredient_name)\
                .eq('capacity', capacity)\
                .eq('unit', unit)\
                .execute()
            
            data = {
                'ingredient_name': ingredient_name,
                'capacity': capacity,
                'unit': unit,
                'unit_price': unit_price,
                'updated_at': datetime.now().isoformat()
            }
            
            if existing.data:
                # 既存レコードがある場合は更新
                self.supabase.table('cost_master')\
                    .update(data)\
                    .eq('ingredient_name', ingredient_name)\
                    .eq('capacity', capacity)\
                    .eq('unit', unit)\
                    .execute()
                print(f"原価表を更新しました: {ingredient_name}")
            else:
                # 新規レコードの場合は挿入
                self.supabase.table('cost_master').insert(data).execute()
                print(f"原価表に追加しました: {ingredient_name}")
            
            return True
                
        except Exception as e:
            print(f"原価表への操作エラー: {e}")
            return False
    
    def get_cost_info(self, ingredient_name: str) -> Optional[Dict]:
        """
        指定した材料の原価情報を取得
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*, suppliers(name)')\
                .eq('ingredient_name', ingredient_name)\
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
            
        except Exception as e:
            print(f"原価情報の取得エラー: {e}")
            return None
    
    def delete_cost(self, ingredient_name: str) -> bool:
        """
        原価表から材料を削除
        """
        try:
            # 注意: この実装では同じ材料名を持つが取引先が違うものも全て削除される
            # より厳密にするにはsupplier_idも指定する必要がある
            self.supabase.table('cost_master')\
                .delete()\
                .eq('ingredient_name', ingredient_name)\
                .execute()
            
            print(f"原価表から削除しました: {ingredient_name}")
            return True
            
        except Exception as e:
            print(f"原価表からの削除エラー: {e}")
            return False
    
    def list_all_costs(self, limit: int = 50) -> list:
        """
        原価表の全材料を取得
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*, suppliers(name)')\
                .order('ingredient_name')\
                .limit(limit)\
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"原価表の取得エラー: {e}")
            return []
    
    def search_costs(self, search_term: str, limit: int = 10) -> list:
        """
        材料名で原価表を検索（部分一致）
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*, suppliers(name)')\
                .ilike('ingredient_name', f'%{search_term}%')\
                .order('ingredient_name')\
                .limit(limit)\
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"原価表の検索エラー: {e}")
            return []


if __name__ == "__main__":
    # テスト用
    manager = CostMasterManager()
    
    # テスト1: 自然言語から解析
    test_texts = [
        "トマト 100円/個",
        "豚バラ肉 300円/100g",
        "キャベツ1玉150円",
        "牛乳 200円/1L"
    ]
    
    print("=== 原価テキスト解析テスト ===")
    for text in test_texts:
        print(f"\n入力: {text}")
        result = manager.parse_cost_text(text)
        if result:
            print(f"結果: {result}")
        else:
            print("解析失敗")


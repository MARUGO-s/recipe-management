"""
Supabaseから原価表を読み込み、材料ごとに原価を計算するモジュール
"""
import os
import csv
from typing import Dict, List, Optional
from decimal import Decimal
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

"""
Supabaseから原価表を読み込み、材料ごとに原価を計算するモジュール
"""
import os
from typing import Dict, List, Optional
from decimal import Decimal, InvalidOperation
from supabase import Client
from dotenv import load_dotenv

load_dotenv()

class CostCalculator:
    def __init__(self, supabase_client: Client):
        self.supabase: Client = supabase_client
        self.cost_master: Dict[str, Dict] = {}

    def load_cost_master(self):
        """
        Supabaseデータベーステーブルから原価表を読み込み、メモリにキャッシュ
        """
        try:
            response = self.supabase.table('cost_master').select('*').execute()
            
            if not response.data:
                print("原価マスターにデータがありません。")
                self.cost_master = {}
                return

            self.cost_master = {}
            for row in response.data:
                ingredient_name = row.get('ingredient_name')
                if not ingredient_name:
                    continue
                
                try:
                    self.cost_master[ingredient_name] = {
                        'unit_price': Decimal(str(row['unit_price'])) if row.get('unit_price') is not None else Decimal('0'),
                        'capacity': Decimal(str(row['capacity'])) if row.get('capacity') is not None else Decimal('1'),
                        'unit': row.get('unit', '個')
                    }
                except (InvalidOperation, TypeError) as e:
                    print(f"原価マスターの行変換エラー（スキップ）: {e}, Row: {row}")
            
            print(f"原価表をDBから読み込みました: {len(self.cost_master)}件")
            
        except Exception as e:
            print(f"DBからの原価表読み込みエラー: {e}")
            self.cost_master = {}

    def calculate_ingredient_cost(self, ingredient_name: str, quantity: float, unit: str) -> Optional[Decimal]:
        """
        材料1つの原価を計算（新しい厳密な単位変換ロジック）
        """
        # 原価マスターから最も近い材料名を見つける（部分一致）
        best_match = None
        for master_name in self.cost_master.keys():
            if master_name in ingredient_name or ingredient_name in master_name:
                best_match = master_name
                break
        
        if not best_match:
            # print(f"警告: '{ingredient_name}' は原価表に存在しません。")
            return None

        master_data = self.cost_master[best_match]
        master_price = master_data['unit_price']
        master_capacity = master_data['capacity']
        master_unit = master_data['unit']
        
        # 数量をDecimalに変換
        decimal_quantity = Decimal(str(quantity))

        # 単位を正規化
        unit_r = self._normalize_unit(unit) # レシピの単位
        unit_m = self._normalize_unit(master_unit) # 原価マスターの単位

        # カテゴリを取得
        category_r = self._get_unit_category(unit_r)
        category_m = self._get_unit_category(unit_m)

        # 1. 単位が完全に一致する場合
        if unit_r == unit_m:
            if master_capacity == 0: return None
            cost = (decimal_quantity / master_capacity) * master_price
            return cost.quantize(Decimal('0.01'))

        # 2. 単位のカテゴリが一致しない場合は計算不可
        if category_r != category_m or category_r == 'count': # 個数系同士の変換は行わない
            print(f"警告: '{ingredient_name}' の単位変換ができません ({unit} -> {master_unit}) - カテゴリ不一致")
            return None

        # 3. カテゴリが一致する場合（重量または容量）、基準単位に変換して計算
        converted_quantity = self._convert_to_base_unit(decimal_quantity, unit_r)
        converted_master_capacity = self._convert_to_base_unit(master_capacity, unit_m)

        if converted_quantity is None or converted_master_capacity is None or converted_master_capacity == 0:
            print(f"警告: '{ingredient_name}' の単位変換に失敗しました。")
            return None

        price_per_base_unit = master_price / converted_master_capacity
        cost = converted_quantity * price_per_base_unit
        return cost.quantize(Decimal('0.01'))

    def _normalize_unit(self, unit: str) -> str:
        """単位を正規化する"""
        unit = unit.lower()
        synonyms = {
            'cc': 'ml',
            'リットル': 'l',
            'キログラム': 'kg',
            'グラム': 'g',
            'カップ': 'cup'
        }
        return synonyms.get(unit, unit)

    def _get_unit_category(self, unit: str) -> Optional[str]:
        """単位のカテゴリ（重量、容量、個数）を返す"""
        weight_units = ['g', 'kg']
        volume_units = ['ml', 'l', 'cup', '大さじ', '小さじ']
        if unit in weight_units:
            return 'weight'
        if unit in volume_units:
            return 'volume'
        return 'count' # デフォルトは個数系

    def _convert_to_base_unit(self, quantity: Decimal, unit: str) -> Optional[Decimal]:
        """各種単位を基本単位（gまたはml）に変換する"""
        # 重量単位 (基準: g)
        weight_map = {
            'kg': Decimal('1000'),
            'g': Decimal('1')
        }
        if unit in weight_map:
            return quantity * weight_map[unit]

        # 容量単位 (基準: ml)
        volume_map = {
            'l': Decimal('1000'),
            'ml': Decimal('1'),
            'cup': Decimal('200'),      # 1カップ = 200ml
            '大さじ': Decimal('15'),     # 大さじ1 = 15ml
            '小さじ': Decimal('5')       # 小さじ1 = 5ml
        }
        if unit in volume_map:
            return quantity * volume_map[unit]

        # 個数系や不明な単位は変換しない（Noneを返す）
        if self._get_unit_category(unit) == 'count':
             # 個数系の場合、そのままの数量を返す（基準単位1として扱う）
            return quantity

        return None

    def calculate_recipe_cost(self, ingredients: List[Dict]) -> Dict:
        """
        レシピ全体の原価を計算
        """
        ingredients_with_cost = []
        total_cost = Decimal('0.00')
        missing_ingredients = []
        
        for ingredient in ingredients:
            name = ingredient.get('name')
            quantity = ingredient.get('quantity')
            unit = ingredient.get('unit')

            if not all([name, quantity, unit]):
                continue
            
            cost = self.calculate_ingredient_cost(name, quantity, unit)
            
            ingredient_data = {
                'name': name,
                'quantity': quantity,
                'unit': unit,
                'cost': float(cost) if cost is not None else None,
                'capacity': ingredient.get('capacity'),
                'capacity_unit': ingredient.get('capacity_unit')
            }
            
            if cost is not None:
                total_cost += cost
            else:
                missing_ingredients.append(name)
            
            ingredients_with_cost.append(ingredient_data)
        
        return {
            'ingredients_with_cost': ingredients_with_cost,
            'total_cost': float(total_cost),
            'missing_ingredients': missing_ingredients
        }



if __name__ == "__main__":
    # テスト用
    calculator = CostCalculator()
    
    # 原価表の読み込み（ストレージまたはDB）
    try:
        calculator.load_cost_master_from_storage()
    except:
        calculator._load_cost_master_from_db()
    
    # テスト材料
    test_ingredients = [
        {"name": "玉ねぎ", "quantity": 1.0, "unit": "個"},
        {"name": "にんじん", "quantity": 1.0, "unit": "本"},
        {"name": "豚肉", "quantity": 200.0, "unit": "g"}
    ]
    
    result = calculator.calculate_recipe_cost(test_ingredients)
    print("原価計算結果:")
    print(f"合計原価: {result['total_cost']}円")
    print(f"材料別原価: {result['ingredients_with_cost']}")
    print(f"未登録材料: {result['missing_ingredients']}")


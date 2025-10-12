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

class CostCalculator:
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabaseの設定が不足しています。")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.cost_master: Dict[str, Dict] = {}
    
    def load_cost_master_from_storage(self, bucket_name: str = "cost-data", file_path: str = "cost_master.csv"):
        """
        Supabaseストレージから原価表CSVを読み込み、メモリにキャッシュ
        
        Args:
            bucket_name: ストレージバケット名
            file_path: CSVファイルのパス
        """
        try:
            # ストレージからファイルをダウンロード
            response = self.supabase.storage.from_(bucket_name).download(file_path)
            
            # CSVをパース
            csv_text = response.decode('utf-8')
            csv_reader = csv.DictReader(csv_text.splitlines())
            
            self.cost_master = {}
            for row in csv_reader:
                ingredient_name = row['ingredient_name']
                self.cost_master[ingredient_name] = {
                    'unit_price': Decimal(row['unit_price']),
                    'reference_unit': row['reference_unit'],
                    'reference_quantity': Decimal(row['reference_quantity'])
                }
            
            print(f"原価表を読み込みました: {len(self.cost_master)}件")
            
        except Exception as e:
            print(f"原価表の読み込みエラー: {e}")
            # フォールバック: データベーステーブルから読み込み
            self._load_cost_master_from_db()
    
    def _load_cost_master_from_db(self):
        """
        Supabaseデータベーステーブルから原価表を読み込み
        """
        try:
            response = self.supabase.table('cost_master').select('*').execute()
            
            self.cost_master = {}
            for row in response.data:
                ingredient_name = row['ingredient_name']
                self.cost_master[ingredient_name] = {
                    'unit_price': Decimal(str(row['unit_price'])),
                    'reference_unit': row['reference_unit'],
                    'reference_quantity': Decimal(str(row['reference_quantity']))
                }
            
            print(f"原価表をDBから読み込みました: {len(self.cost_master)}件")
            
        except Exception as e:
            print(f"DBからの原価表読み込みエラー: {e}")
    
    def calculate_ingredient_cost(self, ingredient_name: str, quantity: float, unit: str) -> Optional[Decimal]:
        """
        材料1つの原価を計算
        
        Args:
            ingredient_name: 材料名
            quantity: 数量
            unit: 単位
            
        Returns:
            原価（円）、原価マスタにない場合はNone
        """
        if ingredient_name not in self.cost_master:
            print(f"警告: '{ingredient_name}' は原価表に存在しません。")
            return None
        
        master_data = self.cost_master[ingredient_name]
        unit_price = master_data['unit_price']
        reference_unit = master_data['reference_unit']
        reference_quantity = master_data['reference_quantity']
        
        # 単位が一致する場合
        if unit == reference_unit:
            cost = (Decimal(str(quantity)) / reference_quantity) * unit_price
            return cost.quantize(Decimal('0.01'))
        
        # 単位変換が必要な場合（簡易版）
        converted_quantity = self._convert_unit(quantity, unit, reference_unit)
        if converted_quantity is not None:
            cost = (Decimal(str(converted_quantity)) / reference_quantity) * unit_price
            return cost.quantize(Decimal('0.01'))
        
        print(f"警告: '{ingredient_name}' の単位変換ができません ({unit} -> {reference_unit})")
        return None
    
    def _convert_unit(self, quantity: float, from_unit: str, to_unit: str) -> Optional[float]:
        """
        単位変換（簡易版）
        
        Args:
            quantity: 変換前の数量
            from_unit: 変換前の単位
            to_unit: 変換後の単位
            
        Returns:
            変換後の数量、変換できない場合はNone
        """
        # 重量系
        weight_units = {
            'kg': 1000,
            'g': 1,
            'mg': 0.001
        }
        
        # 容量系
        volume_units = {
            'l': 1000,
            'リットル': 1000,
            'ml': 1,
            'cc': 1,
            '大さじ': 15,
            '小さじ': 5,
            'カップ': 200
        }
        
        # 重量変換
        if from_unit in weight_units and to_unit in weight_units:
            return quantity * weight_units[from_unit] / weight_units[to_unit]
        
        # 容量変換
        if from_unit in volume_units and to_unit in volume_units:
            return quantity * volume_units[from_unit] / volume_units[to_unit]
        
        # 単位が同じ場合
        if from_unit == to_unit:
            return quantity
        
        return None
    
    def calculate_recipe_cost(self, ingredients: List[Dict]) -> Dict:
        """
        レシピ全体の原価を計算
        
        Args:
            ingredients: 材料リスト [{"name": "玉ねぎ", "quantity": 1.0, "unit": "個"}, ...]
            
        Returns:
            {
                "ingredients_with_cost": [...],
                "total_cost": 123.45,
                "missing_ingredients": [...]
            }
        """
        ingredients_with_cost = []
        total_cost = Decimal('0.00')
        missing_ingredients = []
        
        for ingredient in ingredients:
            name = ingredient['name']
            quantity = ingredient['quantity']
            unit = ingredient['unit']
            
            cost = self.calculate_ingredient_cost(name, quantity, unit)
            
            ingredient_data = {
                'name': name,
                'quantity': quantity,
                'unit': unit,
                'cost': float(cost) if cost is not None else None
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


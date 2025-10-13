#!/usr/bin/env python3
"""
日本的な調理単位を標準単位（ml, g）に変換するシステム
"""
import re
from typing import Dict, Tuple, Optional

class UnitConverter:
    """単位変換クラス"""
    
    # 日本的な調理単位の変換表（基準容量）
    CONVERSION_TABLE = {
        # 体積系（ml基準）
        '大さじ': 15,      # 大さじ1 = 15ml
        '大匙': 15,        # 大匙1 = 15ml
        'tbsp': 15,        # tablespoon = 15ml
        '小さじ': 5,       # 小さじ1 = 5ml
        '小匙': 5,         # 小匙1 = 5ml
        'tsp': 5,          # teaspoon = 5ml
        'カップ': 200,     # カップ1 = 200ml（日本式）
        'cup': 200,        # cup = 200ml
        '合': 180,         # 合1 = 180ml
        '勺': 18,          # 勺1 = 18ml
        'cc': 1,           # cc = ml
        'ml': 1,           # ml = ml
        'リットル': 1000,  # リットル1 = 1000ml
        'l': 1000,         # l = 1000ml
        'L': 1000,         # L = 1000ml
        
        # 重量系（g基準）
        'グラム': 1,       # グラム1 = 1g
        'g': 1,            # g = 1g
        'キログラム': 1000, # キログラム1 = 1000g
        'kg': 1000,        # kg = 1000g
        '斤': 600,         # 斤1 = 600g（パン）
        '匁': 3.75,        # 匁1 = 3.75g
        
        # 個数系（個基準）
        '個': 1,           # 個1 = 1個
        '枚': 1,           # 枚1 = 1枚
        '本': 1,           # 本1 = 1本
        '片': 1,           # 片1 = 1片
        '束': 1,           # 束1 = 1束
        '枝': 1,           # 枝1 = 1枝
        '房': 1,           # 房1 = 1房
        'パック': 1,       # パック1 = 1パック
        '袋': 1,           # 袋1 = 1袋
        '缶': 1,           # 缶1 = 1缶
        '瓶': 1,           # 瓶1 = 1瓶
        'PC': 1,           # PC1 = 1PC
        'pcs': 1,          # pcs1 = 1pcs
    }
    
    # 材料別の密度・重量変換（g/ml）
    MATERIAL_DENSITY = {
        # 液体・油類
        '水': 1.0,
        '牛乳': 1.03,
        '生クリーム': 1.0,
        'ヨーグルト': 1.1,
        'サラダ油': 0.92,
        'オリーブオイル': 0.92,
        'ごま油': 0.92,
        'しょうゆ': 1.18,
        'みりん': 1.2,
        '酢': 1.0,
        '酒': 0.95,
        'ワイン': 0.98,
        
        # 粉類
        '小麦粉': 0.6,
        '薄力粉': 0.6,
        '強力粉': 0.6,
        '米粉': 0.7,
        '片栗粉': 0.6,
        '砂糖': 0.8,
        'グラニュー糖': 0.8,
        '上白糖': 0.8,
        '塩': 1.2,
        'ベーキングパウダー': 0.6,
        'ベーキングソーダ': 0.9,
        'ココアパウダー': 0.5,
        '抹茶': 0.3,
        
        # その他
        'バター': 0.9,
        'マーガリン': 0.9,
        'はちみつ': 1.4,
        'メープルシロップ': 1.3,
        'ジャム': 1.2,
        'マヨネーズ': 0.95,
        'ケチャップ': 1.1,
        '味噌': 1.2,
    }
    
    @classmethod
    def convert_quantity(cls, quantity: float, unit: str, ingredient_name: str = "") -> Tuple[float, str]:
        """
        分量と単位を標準単位に変換
        
        Args:
            quantity: 分量（数値）
            unit: 単位（文字列）
            ingredient_name: 材料名（密度計算用）
            
        Returns:
            (変換後の分量, 変換後の単位)
        """
        unit = unit.strip().lower()
        
        # 単位が既に標準単位の場合はそのまま返す
        if unit in ['ml', 'g', '個', '枚', '本', '片', '束', '枝', '房', 'パック', '袋', '缶', '瓶', 'pc', 'pcs']:
            return quantity, unit
        
        # 変換表から変換
        if unit in cls.CONVERSION_TABLE:
            converted_quantity = quantity * cls.CONVERSION_TABLE[unit]
            
            # 体積系単位の場合、材料の密度を考慮して重量に変換するか判断
            if unit in ['大さじ', '大匙', 'tbsp', '小さじ', '小匙', 'tsp', 'カップ', 'cup', '合', '勺', 'cc', 'ml', 'リットル', 'l', 'L']:
                # 材料名から密度を取得
                density = cls._get_material_density(ingredient_name)
                if density and density != 1.0:
                    # 密度がある場合は重量に変換
                    return converted_quantity * density, 'g'
                else:
                    # 密度がない場合は体積のまま
                    return converted_quantity, 'ml'
            else:
                # 重量系の場合はそのまま
                return converted_quantity, 'g'
        
        # 変換できない場合はそのまま返す
        return quantity, unit
    
    @classmethod
    def _get_material_density(cls, ingredient_name: str) -> Optional[float]:
        """材料名から密度を取得"""
        if not ingredient_name:
            return None
            
        # 材料名を正規化
        normalized_name = ingredient_name.lower().strip()
        
        # 部分一致で密度を検索
        for material, density in cls.MATERIAL_DENSITY.items():
            if material in normalized_name:
                return density
        
        return None
    
    @classmethod
    def parse_quantity_unit(cls, quantity_text: str) -> Tuple[float, str]:
        """
        「2.0大さじ」のような文字列から分量と単位を分離
        
        Args:
            quantity_text: 分量文字列
            
        Returns:
            (分量, 単位)
        """
        # 数値と単位を分離する正規表現
        pattern = r'^(\d+(?:\.\d+)?)\s*(.*)$'
        match = re.match(pattern, quantity_text.strip())
        
        if match:
            quantity = float(match.group(1))
            unit = match.group(2).strip()
            return quantity, unit
        
        # パースできない場合はデフォルト値
        return 0.0, '個'
    
    @classmethod
    def format_for_display(cls, quantity: float, unit: str, ingredient_name: str = "") -> str:
        """
        表示用に分量を整形（日本的な単位に戻すことも可能）
        
        Args:
            quantity: 分量
            unit: 単位
            ingredient_name: 材料名
            
        Returns:
            整形された分量文字列
        """
        # 整数の場合は小数点以下を表示しない
        if quantity == int(quantity):
            quantity = int(quantity)
        
        return f"{quantity}{unit}"
    
    @classmethod
    def get_conversion_info(cls, original_quantity: float, original_unit: str, 
                          converted_quantity: float, converted_unit: str) -> str:
        """
        変換情報を取得
        
        Returns:
            変換情報の文字列
        """
        return f"{original_quantity}{original_unit} → {converted_quantity:.1f}{converted_unit}"


# テスト用
if __name__ == "__main__":
    converter = UnitConverter()
    
    # テストケース
    test_cases = [
        ("2.0大さじ", "オリーブオイル"),
        ("1カップ", "牛乳"),
        ("小さじ1", "塩"),
        ("500g", "小麦粉"),
        ("3個", "卵"),
    ]
    
    for quantity_text, ingredient in test_cases:
        quantity, unit = converter.parse_quantity_unit(quantity_text)
        converted_qty, converted_unit = converter.convert_quantity(quantity, unit, ingredient)
        
        print(f"{quantity_text} ({ingredient}) → {converted_qty:.1f}{converted_unit}")

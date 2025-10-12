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
                "unit_price": 100.0,
                "reference_unit": "個",
                "reference_quantity": 1.0
            }
        """
        try:
            prompt = f"""以下のテキストから材料の原価情報を抽出し、JSON形式で出力してください。

【抽出する情報】
1. ingredient_name: 材料名（文字列）
2. unit_price: 単価（数値、円）
3. reference_unit: 基準単位（「個」「g」「ml」「本」「玉」「丁」「袋」など）
4. reference_quantity: 基準数量（数値）

【重要な注意事項】
- 出力は必ず有効なJSON形式にしてください
- 余計な説明やマークダウンは含めず、JSONのみを出力してください
- unit_priceとreference_quantityは必ず数値型（float）にしてください
- 価格が「100円/個」のような形式の場合、100円が1個あたりの価格です
- 価格が「300円/100g」のような形式の場合、300円が100gあたりの価格です

【入力テキスト】
{text}

【出力JSON形式】
{{
  "ingredient_name": "材料名",
  "unit_price": 100.0,
  "reference_unit": "個",
  "reference_quantity": 1.0
}}

例1: 「トマト 100円/個」
→ {{"ingredient_name": "トマト", "unit_price": 100.0, "reference_unit": "個", "reference_quantity": 1.0}}

例2: 「豚バラ肉 300円/100g」
→ {{"ingredient_name": "豚バラ肉", "unit_price": 300.0, "reference_unit": "g", "reference_quantity": 100.0}}

例3: 「キャベツ1玉150円」
→ {{"ingredient_name": "キャベツ", "unit_price": 150.0, "reference_unit": "玉", "reference_quantity": 1.0}}
"""
            
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは食材の原価情報を構造化する専門家です。与えられたテキストから正確に原価情報を抽出し、JSON形式で出力します。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.1-8b-instant",
                temperature=0.2,
                max_tokens=500
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # JSONの抽出
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # JSONをパース
            cost_data = json.loads(response_text)
            
            # バリデーション
            if self._validate_cost_data(cost_data):
                return cost_data
            else:
                print("原価データのバリデーションに失敗しました。")
                return None
                
        except json.JSONDecodeError as e:
            print(f"JSON解析エラー: {e}")
            print(f"レスポンス: {response_text}")
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
        
        required_fields = ["ingredient_name", "unit_price", "reference_unit", "reference_quantity"]
        for field in required_fields:
            if field not in data:
                return False
        
        if not data["ingredient_name"] or not isinstance(data["ingredient_name"], str):
            return False
        
        if not isinstance(data["unit_price"], (int, float)) or data["unit_price"] <= 0:
            return False
        
        if not data["reference_unit"] or not isinstance(data["reference_unit"], str):
            return False
        
        if not isinstance(data["reference_quantity"], (int, float)) or data["reference_quantity"] <= 0:
            return False
        
        return True
    
    def add_or_update_cost(self, ingredient_name: str, unit_price: float, 
                           reference_unit: str, reference_quantity: float) -> bool:
        """
        原価表に材料を追加または更新
        
        Args:
            ingredient_name: 材料名
            unit_price: 単価
            reference_unit: 基準単位
            reference_quantity: 基準数量
            
        Returns:
            成功した場合True
        """
        try:
            # 既存の材料をチェック
            existing = self.supabase.table('cost_master')\
                .select('*')\
                .eq('ingredient_name', ingredient_name)\
                .execute()
            
            data = {
                'ingredient_name': ingredient_name,
                'unit_price': unit_price,
                'reference_unit': reference_unit,
                'reference_quantity': reference_quantity
            }
            
            if existing.data and len(existing.data) > 0:
                # 更新
                self.supabase.table('cost_master')\
                    .update(data)\
                    .eq('ingredient_name', ingredient_name)\
                    .execute()
                print(f"原価表を更新しました: {ingredient_name}")
                return True
            else:
                # 新規追加
                self.supabase.table('cost_master').insert(data).execute()
                print(f"原価表に追加しました: {ingredient_name}")
                return True
                
        except Exception as e:
            print(f"原価表への追加エラー: {e}")
            return False
    
    def get_cost_info(self, ingredient_name: str) -> Optional[Dict]:
        """
        指定した材料の原価情報を取得
        
        Args:
            ingredient_name: 材料名
            
        Returns:
            原価情報の辞書、見つからない場合はNone
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*')\
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
        
        Args:
            ingredient_name: 材料名
            
        Returns:
            成功した場合True
        """
        try:
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
        
        Args:
            limit: 取得件数の上限
            
        Returns:
            原価情報のリスト
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*')\
                .order('ingredient_name')\
                .limit(limit)\
                .execute()
            
            return response.data
            
        except Exception as e:
            print(f"原価表の取得エラー: {e}")
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


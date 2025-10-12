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
            prompt = f"""以下のテキストから材料の原価情報を抽出し、JSON形式で出力してください。

【抽出する情報】
1. ingredient_name: 材料名（文字列）
2. capacity: 容量・包装量（数値）
3. unit: 単位（「個」「g」「ml」「本」「玉」「丁」「袋」など）
4. unit_price: その容量あたりの単価（数値、円）

【重要な注意事項】
- 出力は必ず有効なJSON形式にしてください
- 余計な説明やマークダウンは含めず、JSONのみを出力してください
- capacity と unit_price は必ず数値型（float）にしてください
- 価格が「100円/個」のような形式の場合、capacity: 1, unit: "個", unit_price: 100
- 価格が「300円/100g」のような形式の場合、capacity: 100, unit: "g", unit_price: 300
- 価格が「1kg 1000円」のような形式の場合、capacity: 1000, unit: "g", unit_price: 1000
- 「kg」は「g」に、「L」は「ml」に変換してください

【入力テキスト】
{text}

【出力JSON形式】
{{
  "ingredient_name": "材料名",
  "capacity": 1.0,
  "unit": "個",
  "unit_price": 100.0
}}

例1: 「トマト 100円/個」
→ {{"ingredient_name": "トマト", "capacity": 1.0, "unit": "個", "unit_price": 100.0}}

例2: 「豚バラ肉 300円/100g」
→ {{"ingredient_name": "豚バラ肉", "capacity": 100.0, "unit": "g", "unit_price": 300.0}}

例3: 「キャベツ1玉150円」
→ {{"ingredient_name": "キャベツ", "capacity": 1.0, "unit": "個", "unit_price": 150.0}}

例4: 「牛乳 1L 200円」
→ {{"ingredient_name": "牛乳", "capacity": 1000.0, "unit": "ml", "unit_price": 200.0}}

例5: 「米 5kg 2000円」
→ {{"ingredient_name": "米", "capacity": 5000.0, "unit": "g", "unit_price": 2000.0}}
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
        原価表に材料を追加または更新（upsertを使用）
        """
        try:
            from datetime import datetime
            data = {
                'ingredient_name': ingredient_name,
                'capacity': capacity,
                'unit': unit,
                'unit_price': unit_price,
                'updated_at': datetime.now().isoformat()
            }
            
            self.supabase.table('cost_master').upsert(data, on_conflict='ingredient_name').execute()
            print(f"原価表をUpsertしました: {ingredient_name}")
            return True
                
        except Exception as e:
            print(f"原価表へのUpsertエラー: {e}")
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
    
    def search_costs(self, search_term: str, limit: int = 10) -> list:
        """
        材料名で原価表を検索（部分一致）
        
        Args:
            search_term: 検索キーワード
            limit: 取得件数の上限
            
        Returns:
            原価情報のリスト
        """
        try:
            response = self.supabase.table('cost_master')\
                .select('*')\
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


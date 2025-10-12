"""
GroqのLLMを使用してOCRテキストからレシピ情報を構造化するモジュール
"""
import os
import json
from typing import Optional, Dict, List
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class GroqRecipeParser:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEYが設定されていません。")
        
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"  # Groqの高速モデル
    
    def parse_recipe_text(self, ocr_text: str) -> Optional[Dict]:
        """
        OCRで抽出したテキストからレシピ情報を構造化
        
        Args:
            ocr_text: OCRで抽出したテキスト
            
        Returns:
            構造化されたレシピデータ（辞書形式）
            {
                "recipe_name": "料理名",
                "servings": 2,
                "ingredients": [
                    {"name": "玉ねぎ", "quantity": 1.0, "unit": "個"},
                    {"name": "豚肉", "quantity": 200.0, "unit": "g"}
                ]
            }
        """
        try:
            prompt = f"""以下のテキストはレシピ画像からOCRで抽出したものです。
このテキストから以下の情報を抽出し、JSON形式で出力してください。

【抽出する情報】
1. recipe_name: 料理名（文字列）
2. servings: 何人前のレシピか（整数）
3. ingredients: 材料リスト（配列）
   - 各材料は以下の形式: {{"name": "材料名", "quantity": 数値, "unit": "単位"}}
   - quantityは必ず数値型（float）にしてください
   - unitは「個」「g」「ml」「本」「玉」「丁」「袋」「大さじ」「小さじ」「カップ」などの単位文字列

【重要な注意事項】
- 出力は必ず有効なJSON形式にしてください
- 余計な説明やマークダウンは含めず、JSON のみを出力してください
- 材料名に数字や単位が含まれている場合は分離してください
- 数量が範囲（例: 1-2個）の場合は中央値を使用してください
- 人数が明記されていない場合は、材料の量から推測してください（通常2-4人前）

【OCRテキスト】
{ocr_text}

【出力JSON形式】
{{
  "recipe_name": "料理名",
  "servings": 2,
  "ingredients": [
    {{"name": "材料名1", "quantity": 1.0, "unit": "個"}},
    {{"name": "材料名2", "quantity": 200.0, "unit": "g"}}
  ]
}}
"""
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは料理レシピのデータを構造化する専門家です。与えられたテキストから正確にレシピ情報を抽出し、JSON形式で出力します。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=2000
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            # JSONの抽出（コードブロックで囲まれている場合に対応）
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # JSONをパース
            recipe_data = json.loads(response_text)
            
            # バリデーション
            if not self._validate_recipe_data(recipe_data):
                print("レシピデータのバリデーションに失敗しました。")
                return None
            
            return recipe_data
            
        except json.JSONDecodeError as e:
            print(f"JSON解析エラー: {e}")
            print(f"レスポンス: {response_text}")
            return None
        except Exception as e:
            print(f"Groq解析エラー: {e}")
            return None
    
    def _validate_recipe_data(self, data: Dict) -> bool:
        """
        レシピデータの妥当性をチェック
        
        Args:
            data: レシピデータ
            
        Returns:
            妥当な場合True
        """
        if not isinstance(data, dict):
            return False
        
        # 必須フィールドのチェック
        if "recipe_name" not in data or not data["recipe_name"]:
            return False
        
        if "servings" not in data or not isinstance(data["servings"], int) or data["servings"] <= 0:
            return False
        
        if "ingredients" not in data or not isinstance(data["ingredients"], list):
            return False
        
        # 材料リストのチェック
        for ingredient in data["ingredients"]:
            if not isinstance(ingredient, dict):
                return False
            if "name" not in ingredient or not ingredient["name"]:
                return False
            if "quantity" not in ingredient or not isinstance(ingredient["quantity"], (int, float)):
                return False
            if "unit" not in ingredient or not ingredient["unit"]:
                return False
        
        return True


if __name__ == "__main__":
    # テスト用
    parser = GroqRecipeParser()
    
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
    print("解析結果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


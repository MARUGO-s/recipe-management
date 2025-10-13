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
        self.model = "llama3-8b-8192"  # Groqの高速モデル
    
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
   - 各材料は以下の形式: {{"name": "材料名", "quantity": 数値, "unit": "単位", "capacity": 数値, "capacity_unit": "単位"}}
   - quantityは必ず数値型（float）にしてください
   - unitは「個」「g」「ml」「本」「玉」「丁」「袋」「大さじ」「小さじ」「カップ」などの単位文字列
   - capacityは材料の包装容量（例: 500gパックの場合は500）
   - capacity_unitは包装容量の単位（例: g, ml, 個）

【OCRテキストの解析について】
- OCRテキストは改行や点で分離されている可能性があります
- 例: 「牛乳.\n.250cc」→ 牛乳 250cc として解析
- 例: 「バニラのさやl\n.1/4本」→ バニラのさや 1/4本 として解析
- 例: 「砂糖.\n.60g」→ 砂糖 60g として解析
- 材料名と分量が別々の行になっていても、関連付けて解析してください

【容量・規格抽出の重要な注意事項】
- 材料名や説明に容量が含まれている場合は必ず抽出してください
- 例: 「トマト缶 400g」→ name: "トマト缶", capacity: 400, capacity_unit: "g"
- 例: 「牛乳 1Lパック」→ name: "牛乳", capacity: 1000, capacity_unit: "ml"
- 例: 「玉ねぎ 500g」→ name: "玉ねぎ", capacity: 500, capacity_unit: "g"
- 容量情報がない場合は、capacity: 1, capacity_unit: "個" としてください
- 「×入数」形式（例: 750ml×12本）の場合は、個別容量（750ml）を抽出してください

【重要な注意事項】
- 出力は必ず有効なJSON形式にしてください
- 余計な説明やマークダウンは含めず、JSON のみを出力してください
- 材料名に数字や単位が含まれている場合は分離してください
- 数量が範囲（例: 1-2個）の場合は中央値を使用してください
- 人数が明記されていない場合は、材料の量から推測してください（通常2-4人前）
- 料理名が明記されていない場合は、「カスタムレシピ」としてください

【OCRテキスト】
{ocr_text}

【出力JSON形式】
{{
  "recipe_name": "料理名",
  "servings": 2,
  "ingredients": [
    {{"name": "材料名1", "quantity": 1.0, "unit": "個", "capacity": 500, "capacity_unit": "g"}},
    {{"name": "材料名2", "quantity": 200.0, "unit": "g", "capacity": 1000, "capacity_unit": "g"}}
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
            
            print(f"✅ JSON解析成功: {recipe_data}")
            
            # バリデーション
            if not self._validate_recipe_data(recipe_data):
                print(f"❌ レシピデータのバリデーションに失敗しました。")
                print(f"データ内容: {json.dumps(recipe_data, ensure_ascii=False, indent=2)}")
                return None
            
            print(f"✅ バリデーション成功")
            return recipe_data
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            print(f"Groqレスポンス: {response_text}")
            return None
        except Exception as e:
            print(f"❌ Groq解析エラー: {e}")
            import traceback
            traceback.print_exc()
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
            # 容量情報のチェック（オプション）
            if "capacity" not in ingredient or not isinstance(ingredient["capacity"], (int, float)):
                ingredient["capacity"] = 1  # デフォルト値
            if "capacity_unit" not in ingredient or not ingredient["capacity_unit"]:
                ingredient["capacity_unit"] = "個"  # デフォルト値
        
        return True

    def extract_search_term(self, text: str) -> Optional[str]:
        """ユーザーの自由入力テキストから、検索対象の材料名を抽出する"""
        try:
            prompt = f"""ユーザーからの「{text}」というメッセージの中心となっている食材名、または材料名だけを抽出してください。
もし、メッセージが単なる挨拶や、特定の食材名を含まない無関係な内容の場合は「None」とだけ出力してください。

例1: 「玉ねぎの値段を教えて」 -> 玉ねぎ
例2: 「豚バラ肉 100g」 -> 豚バラ肉
例3: 「マグレカナールの原価は？」 -> マグレカナール
例4: 「こんにちは」 -> None
例5: 「ありがとう」 -> None

重要な注意: 材料名のみを出力し、余計な文字は一切含めないでください。"""

            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはユーザーのメッセージから検索キーワードとなる食材名だけを正確に抽出する専門家です。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.0,
                max_tokens=50
            )
            
            response_text = chat_completion.choices[0].message.content.strip()
            
            if response_text.lower() == 'none':
                return None
            
            return response_text

        except Exception as e:
            print(f"検索キーワードの抽出エラー: {e}")
            return None

    def translate_text(self, text: str, target_language: str = "日本語") -> Optional[str]:
        """テキストをターゲット言語に翻訳する"""
        try:
            prompt = f"""以下のテキストを{target_language}に翻訳してください。
翻訳結果のみを出力し、余計な説明は含めないでください。

【原文】
{text}
"""
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": f"あなたはプロの翻訳家です。テキストを{target_language}に自然に翻訳します。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=2000
            )
            
            return chat_completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"テキスト翻訳エラー: {e}")
            return None


if __name__ == "__main__":
    # テスト用
    parser = GroqRecipeParser()
    
    test_text = """
    カレー（2人前）
    
    材料:
    玉ねぎ 500gパック 1個
    にんじん 1kg袋 1本
    じゃがいも 2個
    豚バラ肉 1kg 200g
    カレールウ 4皿分
    水 400ml
    """
    
    result = parser.parse_recipe_text(test_text)
    print("解析結果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


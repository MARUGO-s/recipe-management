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
            prompt = f"""あなたは料理レシピの専門家です。以下のOCRテキストからレシピ情報を抽出してください。

【必須タスク】
1. 料理名を特定する（不明な場合は「カスタムレシピ」）
2. 材料リストを抽出する
3. 各材料の分量と単位を特定する
4. 何人前かを推定する（不明な場合は2人前）

【OCRテキスト解析ルール】
- 材料名と分量が別々の行に分かれている場合は結合する
- 例: 「牛乳.」と「.250cc」→ 牛乳 250cc
- 例: 「バニラのさやl」と「.1/4本」→ バニラのさや 1/4本
- 点や句読点は無視して、材料名と分量を関連付ける
- 「適量」は分量0.1、単位「適量」として処理する

【材料の解析パターン】
- 「牛乳 250cc」→ name: "牛乳", quantity: 250, unit: "cc"
- 「バニラのさや 1/4本」→ name: "バニラのさや", quantity: 0.25, unit: "本"
- 「卵黄 3個」→ name: "卵黄", quantity: 3, unit: "個"
- 「砂糖 60g」→ name: "砂糖", quantity: 60, unit: "g"
- 「バニラエッセンス 適量」→ name: "バニラエッセンス", quantity: 0.1, unit: "適量"

【重要】
- 必ず有効なJSON形式で出力する
- 余計な説明は一切含めない
- 材料名は正確に抽出する
- 分量は数値型（float）にする
- 単位はそのまま抽出する

【OCRテキスト】
{ocr_text}

【出力（JSONのみ）】
"""
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは料理レシピの専門家です。OCRで抽出されたテキストから材料情報を正確に解析し、必ずJSON形式で出力します。材料名と分量が分離されていても正しく関連付けて解析します。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=1500
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


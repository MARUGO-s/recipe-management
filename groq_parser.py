"""
AI解析エンジン（Groq + GPT対応）
レシピテキストの構造化と翻訳を担当
"""
import os
import json
from typing import Optional, Dict
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class GroqRecipeParser:
    def __init__(self, ai_provider="groq"):
        """
        AI解析エンジンの初期化
        
        Args:
            ai_provider: "groq" または "gpt" を指定
        """
        self.ai_provider = ai_provider
        
        if ai_provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEYが設定されていません。")
            
            self.client = Groq(api_key=api_key)
            self.model = "llama-3.1-8b-instant"  # Groqの最新モデル
            print(f"🤖 Groq AI エンジンを初期化しました（モデル: {self.model}）")
            
        elif ai_provider == "gpt":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEYが設定されていません。")
            
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4o-mini"  # GPT-4o-mini（コスト効率が良い）
            print(f"🤖 GPT AI エンジンを初期化しました（モデル: {self.model}）")
            
        else:
            raise ValueError("ai_providerは 'groq' または 'gpt' を指定してください。")
    
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
            if self.ai_provider == "groq":
                return self._parse_with_groq(ocr_text)
            elif self.ai_provider == "gpt":
                return self._parse_with_gpt(ocr_text)
        except Exception as e:
            print(f"❌ {self.ai_provider.upper()}解析エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_with_groq(self, ocr_text: str) -> Optional[Dict]:
        """Groqを使用してレシピを解析"""
        prompt = f"""以下のOCRテキストからレシピ情報を抽出し、厳密にJSON形式で出力してください。

## 出力形式の厳守:
{{"recipe_name": "料理名", "servings": 2, "ingredients": [{{"name": "材料名", "quantity": 数値, "unit": "単位", "capacity": 1, "capacity_unit": "個"}}]}}

## 各フィールドの抽出ルール:
1.  **recipe_name**: テキスト全体からレシピのタイトルを簡潔に抽出してください。材料リストを連結しないでください。もしレシピ名が明確でない場合は「不明なレシピ」としてください。
2.  **servings**: レシピの人数を数値で抽出してください。不明な場合は1としてください。
3.  **ingredients**: 各材料について以下のルールで抽出してください。
    *   **name**: 材料名を正確に抽出してください。
    *   **quantity**: 分量を数値（整数または小数）で抽出してください。「1/4」のような表記は小数（例: 0.25）に変換してください。「適量」の場合は0としてください。**「大さじ」「小さじ」は数値に変換せず、単位として扱ってください。**
    *   **unit**: 分量の単位を抽出してください。例: cc, g, 本, 個, 枚, 大さじ, 小さじ。**quantityが0でない場合、unitは空にしないでください。**もし単位が不明な場合は「個」としてください。
    *   **capacity**: 各材料の基準となる容量を数値で抽出してください。不明な場合は1としてください。
    *   **capacity_unit**: capacityの単位を抽出してください。不明な場合は「個」としてください。**「台」のような単位は使用しないでください。**

## 重要な注意事項:
- **必ず有効なJSON形式で出力してください。**
- **材料名と分量が別々の行に分かれている場合は、適切に結合してください。**
- **出力はJSONのみとし、余分な説明文は含めないでください。**

テキスト：
{ocr_text}

JSON："""
        
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "あなたはJSON出力の専門家です。必ず有効なJSON形式で出力します。"
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
        print(f"🔍 Groq生レスポンス: {response_text}")
        
        return self._extract_json_from_response(response_text)
    
    def _parse_with_gpt(self, ocr_text: str) -> Optional[Dict]:
        """GPTを使用してレシピを解析"""
        prompt = f"""以下のOCRテキストからレシピ情報を抽出し、厳密にJSON形式で出力してください。

## 出力形式の厳守:
{{"recipe_name": "料理名", "servings": 2, "ingredients": [{{"name": "材料名", "quantity": 数値, "unit": "単位", "capacity": 1, "capacity_unit": "個"}}]}}

## 各フィールドの抽出ルール:
1.  **recipe_name**: テキスト全体からレシピのタイトルを簡潔に抽出してください。材料リストを連結しないでください。もしレシピ名が明確でない場合は「不明なレシピ」としてください。
2.  **servings**: レシピの人数を数値で抽出してください。不明な場合は1としてください。
3.  **ingredients**: 各材料について以下のルールで抽出してください。
    *   **name**: 材料名を正確に抽出してください。
    *   **quantity**: 分量を数値（整数または小数）で抽出してください。「1/4」のような表記は小数（例: 0.25）に変換してください。「適量」の場合は0としてください。**「大さじ」「小さじ」は数値に変換せず、単位として扱ってください。**
    *   **unit**: 分量の単位を抽出してください。例: cc, g, 本, 個, 枚, 大さじ, 小さじ。**quantityが0でない場合、unitは空にしないでください。**もし単位が不明な場合は「個」としてください。
    *   **capacity**: 各材料の基準となる容量を数値で抽出してください。不明な場合は1としてください。
    *   **capacity_unit**: capacityの単位を抽出してください。不明な場合は「個」としてください。**「台」のような単位は使用しないでください。**

## 重要な注意事項:
- **必ず有効なJSON形式で出力してください。**
- **材料名と分量が別々の行に分かれている場合は、適切に結合してください。**
- **出力はJSONのみとし、余分な説明文は含めないでください。**

テキスト：
{ocr_text}

JSON："""
        
        chat_completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "あなたはJSON出力の専門家です。必ず有効なJSON形式で出力します。"
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
        print(f"🔍 GPT生レスポンス: {response_text}")
        
        return self._extract_json_from_response(response_text)
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict]:
        """AIレスポンスからJSONを抽出"""
        try:
            # JSONの抽出（コードブロックで囲まれている場合に対応）
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
                print(f"🔍 JSONブロック抽出後: {response_text}")
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                print(f"🔍 コードブロック抽出後: {response_text}")
            
            # JSONオブジェクトの開始と終了を探す
            if "{" in response_text and "}" in response_text:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                response_text = response_text[start:end]
                print(f"🔍 JSONオブジェクト抽出後: {response_text}")
            
            # JSONをパース
            recipe_data = json.loads(response_text)
            
            print(f"✅ JSON解析成功: {recipe_data}")
            
            # 不足しているフィールドを自動補完
            for ingredient in recipe_data.get('ingredients', []):
                if 'capacity' not in ingredient:
                    ingredient['capacity'] = 1
                if 'capacity_unit' not in ingredient:
                    ingredient['capacity_unit'] = '個'
            
            # バリデーション
            if not self._validate_recipe_data(recipe_data):
                print(f"❌ レシピデータのバリデーションに失敗しました。")
                print(f"データ内容: {json.dumps(recipe_data, ensure_ascii=False, indent=2)}")
                return None
            
            print(f"✅ バリデーション成功")
            return recipe_data
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            print(f"AIレスポンス: {response_text}")
            return None
        except Exception as e:
            print(f"❌ レスポンス処理エラー: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _validate_recipe_data(self, data: Dict) -> bool:
        """レシピデータのバリデーション"""
        if not isinstance(data, dict):
            return False
        
        if 'recipe_name' not in data or 'servings' not in data or 'ingredients' not in data:
            return False
        
        if not isinstance(data['servings'], int) or data['servings'] <= 0:
            return False
        
        if not isinstance(data['ingredients'], list):
            return False
        
        for ingredient in data['ingredients']:
            if not isinstance(ingredient, dict):
                return False
            if 'name' not in ingredient or 'quantity' not in ingredient or 'unit' not in ingredient:
                return False
        
        return True
    
    def translate_text(self, text: str, target_language: str = "ja") -> Optional[str]:
        """テキストを指定言語に翻訳"""
        try:
            if self.ai_provider == "groq":
                return self._translate_with_groq(text, target_language)
            elif self.ai_provider == "gpt":
                return self._translate_with_gpt(text, target_language)
        except Exception as e:
            print(f"❌ {self.ai_provider.upper()}翻訳エラー: {e}")
            return None
    
    def _translate_with_groq(self, text: str, target_language: str) -> Optional[str]:
        """Groqを使用してテキストを翻訳"""
        prompt = f"以下のテキストを{target_language}に翻訳してください：\n\n{text}"
        
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "あなたは翻訳の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.1,
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
    
    def _translate_with_gpt(self, text: str, target_language: str) -> Optional[str]:
        """GPTを使用してテキストを翻訳"""
        prompt = f"以下のテキストを{target_language}に翻訳してください：\n\n{text}"
        
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "あなたは翻訳の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            model=self.model,
            temperature=0.1,
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
"""
GroqのLLMを使用してOCRテキストからレシピ情報を構造化するモジュール
"""
import os
import json
import re
from fractions import Fraction
from typing import Optional, Dict, List, Tuple
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class GroqRecipeParser:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEYが設定されていません。")
        
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"  # Groqの最新モデル
    
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

## 注意事項:
- 材料名と分量が別々の行に分かれている場合や、間に「.」などがある場合は、適切に結合して抽出してください。
- 必ず有効なJSON形式で出力してください。余計なテキストは含めないでください。

## テキスト:
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
            
            # 不足しているトップレベルフィールドを自動補完
            if 'recipe_name' not in recipe_data or not recipe_data['recipe_name']:
                recipe_data['recipe_name'] = "不明なレシピ"
            if 'servings' not in recipe_data or not isinstance(recipe_data['servings'], int) or recipe_data['servings'] <= 0:
                recipe_data['servings'] = 1
            
            # 不足している材料フィールドを自動補完
            for ingredient in recipe_data.get('ingredients', []):
                if 'capacity' not in ingredient:
                    ingredient['capacity'] = 1
                if 'capacity_unit' not in ingredient:
                    ingredient['capacity_unit'] = '個'
            
            # バリデーション
            if not self._validate_recipe_data(recipe_data):
                print("❌ レシピデータのバリデーションに失敗しました。フォールバック解析を試みます。")
                print(f"データ内容: {json.dumps(recipe_data, ensure_ascii=False, indent=2)}")
                return self._fallback_parse_recipe(ocr_text)

            print(f"✅ バリデーション成功")
            return recipe_data
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            print(f"Groqレスポンス: {response_text}")
            return self._fallback_parse_recipe(ocr_text)
        except Exception as e:
            print(f"❌ Groq解析エラー: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_parse_recipe(ocr_text)
    
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
            # quantityが0の場合はunitが空でも許容する
            if ingredient["quantity"] == 0 and not ingredient.get("unit"):
                pass # unitが空でもOK
            elif "unit" not in ingredient or not ingredient["unit"]:
                return False
            # 容量情報のチェック（オプション）
            if "capacity" not in ingredient or not isinstance(ingredient["capacity"], (int, float)):
                ingredient["capacity"] = 1  # デフォルト値
            if "capacity_unit" not in ingredient or not ingredient["capacity_unit"]:
                ingredient["capacity_unit"] = "個"  # デフォルト値
        
        return True

    # ==================== フォールバック解析 ====================

    def _fallback_parse_recipe(self, ocr_text: str) -> Optional[Dict]:
        """Groq解析に失敗した際の簡易パーサー"""
        print("🛟 フォールバック解析を実行します")

        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        if not lines:
            return None

        # メタ情報行を除外
        skip_prefixes = (
            '材料', '【', '◆', '※', '料理を楽しむにあたって', 'POINT', '作り方'
        )
        cleaned_lines = []
        for line in lines:
            if any(line.startswith(prefix) for prefix in skip_prefixes):
                continue
            cleaned_lines.append(line)

        ingredients = []
        i = 0
        while i < len(cleaned_lines):
            line = cleaned_lines[i]

            # 計量行のみの場合はスキップ
            if self._parse_measurement_line(line):
                i += 1
                continue

            name = line

            quantity = 0.0
            unit = '個'

            if i + 1 < len(cleaned_lines):
                parsed = self._parse_measurement_line(cleaned_lines[i + 1])
                if parsed:
                    quantity, unit = parsed
                    i += 1

            ingredients.append({
                'name': name,
                'quantity': quantity,
                'unit': unit,
                'capacity': 1,
                'capacity_unit': '個'
            })

            i += 1

        if not ingredients:
            return None

        recipe_name = self._extract_recipe_name(ocr_text)
        servings = self._extract_servings(ocr_text)

        recipe = {
            'recipe_name': recipe_name,
            'servings': servings,
            'ingredients': ingredients
        }

        if not self._validate_recipe_data(recipe):
            print("❌ フォールバック解析でも妥当なデータを生成できませんでした。")
            return None

        print("✅ フォールバック解析でレシピデータを生成しました。")
        return recipe

    def _parse_measurement_line(self, line: str) -> Optional[Tuple[float, str]]:
        """数量と単位を含む行を解析"""
        normalized = line.replace(' ', '')

        if normalized in {'適量', '少々'}:
            return 0.0, '適量'

        fraction_match = re.match(r'^(?P<unit>[大中小]さじ|カップ)(?P<quantity>\d+/\d+)$', normalized)
        if fraction_match:
            quantity = float(Fraction(fraction_match.group('quantity')))
            unit = fraction_match.group('unit')
            return quantity, self._normalize_unit(unit)

        pattern_after = re.match(r'^(?P<quantity>\d+(?:\.\d+)?)(?P<unit>[a-zA-Zぁ-んァ-ヶ一-龥]+)$', normalized)
        if pattern_after:
            quantity = float(pattern_after.group('quantity'))
            unit = pattern_after.group('unit')
            return quantity, self._normalize_unit(unit)

        pattern_before = re.match(r'^(?P<unit>[大中小]さじ|カップ|杯|個|本|枚|台|台分)(?P<quantity>\d+(?:\.\d+)?)$', normalized)
        if pattern_before:
            quantity = float(pattern_before.group('quantity'))
            unit = pattern_before.group('unit')
            return quantity, self._normalize_unit(unit)

        # 分数 (例: 1/2カップ)
        mixed_pattern = re.match(r'^(?P<quantity>\d+/\d+)(?P<unit>[a-zA-Zぁ-んァ-ヶ一-龥]+)$', normalized)
        if mixed_pattern:
            quantity = float(Fraction(mixed_pattern.group('quantity')))
            unit = mixed_pattern.group('unit')
            return quantity, self._normalize_unit(unit)

        return None

    def _normalize_unit(self, unit: str) -> str:
        """フォールバック解析用の単位正規化"""
        mapping = {
            'cc': 'ml',
            'ＣＣ': 'ml',
            'ml': 'ml',
            'mL': 'ml',
            'l': 'l',
            'L': 'l',
            'kg': 'kg',
            'g': 'g',
            '大さじ': '大さじ',
            '小さじ': '小さじ',
            '中さじ': '中さじ',
            '杯': '杯',
            'カップ': 'カップ',
            '杯分': '杯',
            '本': '本',
            '枚': '枚',
            '個': '個',
            '台': '台',
            '台分': '台',
            '適量': '適量'
        }
        return mapping.get(unit, unit)

    def _extract_recipe_name(self, text: str) -> str:
        """テキストからレシピ名の候補を抽出"""
        # 「材料」より前に料理名が記載されていれば利用する
        parts = re.split(r'材料[:：\[]', text, maxsplit=1)
        if parts and parts[0].strip():
            candidate = parts[0].strip()
            if len(candidate) <= 40:
                return candidate
        return '不明なレシピ'

    def _extract_servings(self, text: str) -> int:
        """テキストから人数・台数などを推定"""
        match_people = re.search(r'(\d+)\s*人', text)
        if match_people:
            return max(1, int(match_people.group(1)))

        match_serving = re.search(r'(\d+)\s*台', text)
        if match_serving:
            return max(1, int(match_serving.group(1)))

        return 1

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

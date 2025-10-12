"""
Azure Vision APIを使用して画像からテキストを抽出するモジュール
"""
import os
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class AzureVisionAnalyzer:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_VISION_ENDPOINT")
        self.key = os.getenv("AZURE_VISION_KEY")
        
        if not self.endpoint or not self.key:
            raise ValueError("Azure Vision APIの設定が不足しています。")
    
    def analyze_image_from_url(self, image_url: str) -> Optional[str]:
        """
        画像URLからOCRでテキストを抽出
        
        Args:
            image_url: 画像のURL
            
        Returns:
            抽出されたテキスト（複数行の場合は改行で結合）
        """
        try:
            # Azure Vision API v3.2 (Read API)
            analyze_url = f"{self.endpoint}vision/v3.2/read/analyze"
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.key,
                "Content-Type": "application/json"
            }
            
            body = {"url": image_url}
            
            # Step 1: 画像解析を開始
            response = requests.post(analyze_url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            
            operation_location = response.headers.get('Operation-Location')
            if not operation_location:
                print("解析結果URLが見つかりません")
                return None

            # Step 2: 解析結果をポーリングして取得
            # Step 3: readResultsからテキストを抽出
            full_text, language = self._extract_text_from_result(result)
            
            return full_text, language
            
        except requests.exceptions.RequestException as e:
            print(f"Azure Vision API エラー: {e}")
            return None
        except Exception as e:
            print(f"画像解析エラー: {e}")
            return None
    
    def analyze_image_from_bytes(self, image_bytes: bytes) -> Optional[str]:
        """
        画像バイナリデータからOCRでテキストを抽出
        
        Args:
            image_bytes: 画像のバイナリデータ
            
        Returns:
            抽出されたテキスト（複数行の場合は改行で結合）
        """
        try:
            analyze_url = f"{self.endpoint}vision/v3.2/read/analyze"
            
            headers = {
                "Ocp-Apim-Subscription-Key": self.key,
                "Content-Type": "application/octet-stream"
            }
            
            # Step 1: 画像解析を開始
            response = requests.post(analyze_url, headers=headers, data=image_bytes, timeout=10)
            response.raise_for_status()
            
            operation_location = response.headers.get('Operation-Location')
            if not operation_location:
                print("解析結果URLが見つかりません")
                return None

            # Step 2: 解析結果をポーリングして取得
            result = self._get_analysis_result(operation_location)

            # Step 3: readResultsからテキストを抽出
            full_text, language = self._extract_text_from_result(result)
            
            return full_text, language
            
        except requests.exceptions.RequestException as e:
            print(f"Azure Vision API エラー: {e}")
            return None
        except Exception as e:
            print(f"画像解析エラー: {e}")
            return None

    def _get_analysis_result(self, operation_url: str) -> Optional[dict]:
        """解析結果URLをポーリングして最終的な結果を取得する"""
        import time
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        
        for _ in range(15): # 最大30秒間ポーリング (15回 * 2秒)
            response = requests.get(operation_url, headers=headers)
            response.raise_for_status()
            result = response.json()
            
            status = result.get('status')
            if status == 'succeeded':
                return result
            if status == 'failed':
                print("Azure Visionの解析が失敗しました。")
                return None
            
            time.sleep(2)
        
        print("Azure Visionの解析がタイムアウトしました。")
        return None

    def _extract_text_from_result(self, result: Optional[dict]) -> (Optional[str], Optional[str]):
        """解析結果のJSONからテキスト行と主要言語を抽出する"""
        if not result:
            return None, None

        extracted_text = []
        language_codes = []
        if result.get('analyzeResult') and result['analyzeResult'].get('readResults'):
            for page in result['analyzeResult']['readResults']:
                for line in page.get("lines", []):
                    extracted_text.append(line.get("text", ""))
                    language_codes.append(line.get("language", "ja"))
        
        if not extracted_text:
            return None, None

        # 最も頻度の高い言語を特定
        from collections import Counter
        dominant_language = Counter(language_codes).most_common(1)[0][0] if language_codes else 'ja'

        return "\n".join(extracted_text), dominant_language


if __name__ == "__main__":
    # テスト用
    analyzer = AzureVisionAnalyzer()
    test_url = "https://example.com/recipe_image.jpg"
    result = analyzer.analyze_image_from_url(test_url)
    print("抽出されたテキスト:")
    print(result)


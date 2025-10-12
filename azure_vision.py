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
            response = requests.post(analyze_url, headers=headers, json=body, timeout=30)
            response.raise_for_status()
            
            # Step 2: 解析結果を取得（非同期処理のため少し待機）
            import time
            time.sleep(2)  # 解析完了を待機
            
            # 解析結果URLを取得
            operation_location = response.headers.get('Operation-Location')
            if not operation_location:
                print("解析結果URLが見つかりません")
                return None
            
            # Step 3: 結果を取得
            result_response = requests.get(operation_location, headers={"Ocp-Apim-Subscription-Key": self.key})
            result_response.raise_for_status()
            result = result_response.json()
            
            # readResultsからテキストを抽出
            extracted_text = []
            if "analyzeResult" in result and "readResults" in result["analyzeResult"]:
                for page in result["analyzeResult"]["readResults"]:
                    for line in page.get("lines", []):
                        extracted_text.append(line.get("text", ""))
            
            return "\n".join(extracted_text) if extracted_text else None
            
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
            response = requests.post(analyze_url, headers=headers, data=image_bytes, timeout=30)
            response.raise_for_status()
            
            # Step 2: 解析結果を取得（非同期処理のため少し待機）
            import time
            time.sleep(2)  # 解析完了を待機
            
            # 解析結果URLを取得
            operation_location = response.headers.get('Operation-Location')
            if not operation_location:
                print("解析結果URLが見つかりません")
                return None
            
            # Step 3: 結果を取得
            result_response = requests.get(operation_location, headers={"Ocp-Apim-Subscription-Key": self.key})
            result_response.raise_for_status()
            result = result_response.json()
            
            # readResultsからテキストを抽出
            extracted_text = []
            if "analyzeResult" in result and "readResults" in result["analyzeResult"]:
                for page in result["analyzeResult"]["readResults"]:
                    for line in page.get("lines", []):
                        extracted_text.append(line.get("text", ""))
            
            return "\n".join(extracted_text) if extracted_text else None
            
        except requests.exceptions.RequestException as e:
            print(f"Azure Vision API エラー: {e}")
            return None
        except Exception as e:
            print(f"画像解析エラー: {e}")
            return None


if __name__ == "__main__":
    # テスト用
    analyzer = AzureVisionAnalyzer()
    test_url = "https://example.com/recipe_image.jpg"
    result = analyzer.analyze_image_from_url(test_url)
    print("抽出されたテキスト:")
    print(result)


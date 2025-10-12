#!/usr/bin/env python3
"""
アプリケーションを完全に再起動するスクリプト
"""
import os
import sys
import time
from dotenv import load_dotenv

def restart_application():
    """アプリケーションを再起動"""
    try:
        print("🔄 アプリケーションを再起動中...")
        
        # 環境変数を再読み込み
        load_dotenv()
        
        # 現在のプロセスを終了
        print("⏹️ 現在のプロセスを終了...")
        os._exit(0)
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    restart_application()

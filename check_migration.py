#!/usr/bin/env python3
"""
システム設定テーブルの確認スクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def check_system_settings():
    """システム設定テーブルの状態を確認"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        print("🔍 system_settingsテーブルの確認中...")
        
        # テーブルの存在確認とデータ取得
        result = supabase.table('system_settings').select('*').execute()
        
        print("✅ system_settingsテーブルが存在します")
        print(f"📊 登録済み設定数: {len(result.data)}")
        
        for setting in result.data:
            print(f"  - {setting['key']}: {setting['value']}")
        
        # AIプロバイダーの現在の設定を確認
        ai_setting = next((s for s in result.data if s['key'] == 'ai_provider'), None)
        if ai_setting:
            print(f"🤖 現在のAIプロバイダー: {ai_setting['value']}")
        else:
            print("⚠️ AIプロバイダー設定が見つかりません")
            
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

if __name__ == "__main__":
    print("🚀 システム設定確認開始")
    check_system_settings()

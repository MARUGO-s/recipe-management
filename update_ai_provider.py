#!/usr/bin/env python3
"""
AIプロバイダーをGPTに更新するスクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def update_ai_provider():
    """AIプロバイダーをGPTに更新"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        print("🔄 AIプロバイダーをGPTに更新中...")
        
        # AIプロバイダーをGPTに更新
        result = supabase.table('system_settings').update({
            'value': 'gpt',
            'updated_at': 'now()'
        }).eq('key', 'ai_provider').execute()
        
        print("✅ AIプロバイダーをGPTに更新しました")
        
        # 更新結果を確認
        check_result = supabase.table('system_settings').select('*').eq('key', 'ai_provider').execute()
        if check_result.data:
            print(f"📊 更新後の設定: {check_result.data[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

if __name__ == "__main__":
    print("🚀 AIプロバイダー更新開始")
    update_ai_provider()

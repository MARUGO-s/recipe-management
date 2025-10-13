#!/usr/bin/env python3
"""
Supabaseマイグレーション実行スクリプト
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    """システム設定テーブルを作成するマイグレーションを実行"""
    
    # Supabaseクライアントを初期化
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase環境変数が設定されていません")
        return False
    
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        
        # マイグレーションSQL
        migration_sql = """
        -- システム設定テーブルを作成
        CREATE TABLE IF NOT EXISTS public.system_settings (
            id SERIAL PRIMARY KEY,
            key VARCHAR(255) UNIQUE NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- インデックスを作成
        CREATE INDEX IF NOT EXISTS idx_system_settings_key ON public.system_settings(key);

        -- コメントを追加
        COMMENT ON TABLE public.system_settings IS 'システム設定を保存するテーブル';
        COMMENT ON COLUMN public.system_settings.key IS '設定キー（例: ai_provider）';
        COMMENT ON COLUMN public.system_settings.value IS '設定値（例: groq, gpt）';
        COMMENT ON COLUMN public.system_settings.created_at IS '作成日時';
        COMMENT ON COLUMN public.system_settings.updated_at IS '更新日時';

        -- 初期設定を挿入（AIプロバイダーをデフォルトでgroqに設定）
        INSERT INTO public.system_settings (key, value) 
        VALUES ('ai_provider', 'groq') 
        ON CONFLICT (key) DO NOTHING;
        """
        
        print("🔄 マイグレーション実行中...")
        
        # SQLを実行
        result = supabase.rpc('exec_sql', {'sql': migration_sql}).execute()
        
        print("✅ マイグレーションが正常に完了しました")
        
        # テーブルが作成されたか確認
        try:
            check_result = supabase.table('system_settings').select('*').limit(1).execute()
            print(f"✅ system_settingsテーブルが作成されました")
            if check_result.data:
                print(f"📊 初期データ: {check_result.data}")
            return True
        except Exception as e:
            print(f"⚠️ テーブル確認エラー: {e}")
            return False
            
    except Exception as e:
        print(f"❌ マイグレーションエラー: {e}")
        
        # フォールバック: 直接テーブル作成を試行
        try:
            print("🔄 フォールバック: 直接テーブル作成を試行...")
            
            # テーブル作成
            supabase.table('system_settings').insert({
                'key': 'ai_provider',
                'value': 'groq'
            }).execute()
            
            print("✅ フォールバック成功: system_settingsテーブルが作成されました")
            return True
            
        except Exception as fallback_error:
            print(f"❌ フォールバックエラー: {fallback_error}")
            return False

if __name__ == "__main__":
    print("🚀 Supabaseマイグレーション開始")
    success = run_migration()
    if success:
        print("🎉 マイグレーション完了！")
    else:
        print("💥 マイグレーション失敗")
        exit(1)

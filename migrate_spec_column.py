#!/usr/bin/env python3
"""
specカラムをデータベースに追加するスクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def migrate_spec_column():
    """specカラムをデータベースに追加"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # SQLを実行してspecカラムを追加
        sql_commands = [
            "ALTER TABLE public.cost_master ADD COLUMN IF NOT EXISTS spec TEXT;",
            "COMMENT ON COLUMN public.cost_master.spec IS 'CSVの規格列（16列目）から抽出した規格情報（そのまま保持）';",
            "CREATE INDEX IF NOT EXISTS idx_cost_master_spec ON public.cost_master(spec);"
        ]
        
        for sql in sql_commands:
            print(f"実行中: {sql}")
            result = supabase.rpc('exec_sql', {'sql': sql}).execute()
            print(f"✅ 完了")
        
        print("\n🎉 specカラムの追加が完了しました！")
        
        # 確認
        result = supabase.table('cost_master').select('ingredient_name, spec').limit(1).execute()
        print(f"📊 確認: {len(result.data)}件のデータが取得できました")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        print("\n手動でSupabaseのSQL Editorで以下を実行してください:")
        print("""
ALTER TABLE public.cost_master
ADD COLUMN IF NOT EXISTS spec TEXT;

COMMENT ON COLUMN public.cost_master.spec IS 'CSVの規格列（16列目）から抽出した規格情報（そのまま保持）';

CREATE INDEX IF NOT EXISTS idx_cost_master_spec ON public.cost_master(spec);
        """)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_spec_column()

#!/usr/bin/env python3
"""
データベースからデータを強制的に削除するスクリプト
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def force_delete_data():
    """データを強制的に削除"""
    try:
        # Supabaseクライアントを作成
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            print("❌ Supabaseの設定が不足しています")
            return
        
        supabase = create_client(supabase_url, supabase_key)
        
        # 現在のデータ件数を確認
        result = supabase.table('cost_master').select('id', count='exact').execute()
        count_before = result.count
        print(f"🔍 削除前のデータ件数: {count_before}件")
        
        if count_before == 0:
            print("✅ データは既に空です")
            return
        
        # 全てのデータを取得
        all_data = supabase.table('cost_master').select('id').execute()
        print(f"📋 取得したデータ件数: {len(all_data.data)}件")
        
        # バッチで削除（100件ずつ）
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(all_data.data), batch_size):
            batch = all_data.data[i:i + batch_size]
            ids = [item['id'] for item in batch]
            
            # バッチ削除
            result = supabase.table('cost_master').delete().in_('id', ids).execute()
            deleted_count += len(ids)
            print(f"🗑️ 削除済み: {deleted_count}/{len(all_data.data)}件")
        
        # 最終確認
        result = supabase.table('cost_master').select('id', count='exact').execute()
        count_after = result.count
        
        print(f"✅ 削除完了")
        print(f"📊 削除後のデータ件数: {count_after}件")
        
        if count_after == 0:
            print("🎯 次のステップ:")
            print("1. Renderでアプリケーションを再起動してください")
            print("2. ウェブ管理画面を強制リロード（Ctrl+F5）してください")
            print("3. 新しいCSVファイルをアップロードしてください")
        else:
            print("⚠️ まだデータが残っています")
        
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    force_delete_data()

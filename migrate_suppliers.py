# -*- coding: utf-8 -*-
import os
import re
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. 環境設定
load_dotenv()

print("データ移行スクリプトを開始します...")

# Supabaseクライアントをサービスキーで初期化
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("SupabaseのURLまたはサービスキーが.envファイルに設定されていません。")

supabase: Client = create_client(supabase_url, supabase_key)


def migrate_data():
    try:
        # 2. cost_masterから全データを取得
        print("\nステップ1: 既存の原価マスターデータを取得中...")
        cost_master_rows = supabase.table("cost_master").select("*").execute().data
        if not cost_master_rows:
            print("原価マスターにデータがないため、移行をスキップします。")
            return
        print(f"{len(cost_master_rows)}件のデータを取得しました。")

        # 3. 取引先名を抽出し、ユニークなリストを作成
        print("\nステップ2: 材料名から取引先名を抽出中...")
        suppliers_to_create = set()
        supplier_regex = re.compile(r'[（(](.+?)[)）]$') # 全角半角の括弧に対応

        for row in cost_master_rows:
            original_name = row.get('ingredient_name', '')
            match = supplier_regex.search(original_name)
            if match:
                supplier_name = match.group(1).strip()
                if supplier_name:
                    suppliers_to_create.add(supplier_name)
        
        print(f"{len(suppliers_to_create)}件のユニークな取引先を検出しました。")

        # 4. 新しい取引先をsuppliersテーブルに登録
        if suppliers_to_create:
            print("\nステップ3: 新しい取引先をデータベースに登録中...")
            supplier_insert_data = [{'name': name} for name in suppliers_to_create]
            supabase.table("suppliers").upsert(supplier_insert_data, on_conflict='name').execute()
            print("取引先の登録が完了しました。")
        else:
            print("\nステップ3: 新しい取引先はないため、スキップします。")

        # 5. suppliersテーブルから全データを取得し、名前とIDのマップを作成
        print("\nステップ4: 取引先IDを取得し、マッピングを作成中...")
        all_suppliers = supabase.table("suppliers").select("id, name").execute().data
        supplier_name_to_id = {s['name']: s['id'] for s in all_suppliers}
        print("マッピングの作成が完了しました。")

        # 6. cost_masterテーブルを更新するためのデータを作成
        print("\nステップ5: 原価マスターの更新データを作成中...")
        updates_for_supabase = []
        for row in cost_master_rows:
            original_name = row.get('ingredient_name', '')
            match = supplier_regex.search(original_name)
            
            cleaned_name = original_name
            supplier_id = row.get('supplier_id') # 既存のIDを維持

            if match:
                supplier_name = match.group(1).strip()
                if supplier_name in supplier_name_to_id:
                    supplier_id = supplier_name_to_id[supplier_name]
                    cleaned_name = supplier_regex.sub('', original_name).strip()
            
            # 元のデータを全て含めた上で、更新するフィールドを指定
            new_row = row.copy()
            new_row['ingredient_name'] = cleaned_name
            new_row['supplier_id'] = supplier_id
            updates_for_supabase.append(new_row)

        # 7. cost_masterテーブルをバッチ更新
        if updates_for_supabase:
            print(f"\nステップ6: {len(updates_for_supabase)}件の原価マスターデータを更新中...")
            # upsertは主キー(id)を元に更新を行う
            supabase.table("cost_master").upsert(updates_for_supabase).execute()
            print("原価マスターデータの更新が完了しました。")
        
        print("\n🎉 データ移行が正常に完了しました！")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_data()

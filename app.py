"""
LINE Bot メインアプリケーション（Render用）
LINE → Azure Vision → Groq → Supabase → LINE の一連のフロー
"""
import os
import requests
import csv
import io
import re
from datetime import datetime
from unit_converter import UnitConverter
from flask import Flask, request, abort, render_template, jsonify, send_file, redirect, url_for, flash
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, PostbackEvent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer
)
from typing import Optional # 追加

# LINE UI機能は一時的に無効化（安定性を優先）
LINE_UI_AVAILABLE = False
print("⚠️ LINE UI機能は一時的に無効化されています（安定性を優先）")
from dotenv import load_dotenv
from azure_vision import AzureVisionAnalyzer
from groq_parser import GroqRecipeParser
from cost_calculator import CostCalculator
from cost_master_manager import CostMasterManager
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# CSRF保護を無効化（フォーム機能を優先）
csrf = None
print("⚠️ CSRF保護は無効化されています（フォーム機能を優先）")

# LINE Bot設定
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
line_bot_blob_api = MessagingApiBlob(api_client)

# Supabase設定
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
if not supabase_key:
    print("警告: SUPABASE_SERVICE_KEYが設定されていません。anonキーでフォールバックします。")
    supabase_key = os.getenv('SUPABASE_KEY')

supabase: Client = create_client(supabase_url, supabase_key)

# 各種サービスの初期化
azure_analyzer = AzureVisionAnalyzer()

# AIプロバイダーの選択（環境変数で制御、DBで永続化）
def get_ai_provider():
    """現在のAIプロバイダーを取得（DB優先、環境変数フォールバック）"""
    try:
        result = supabase.table('system_settings').select('value').eq('key', 'ai_provider').execute()
        if result.data:
            print(f"📊 DB設定からAIプロバイダーを取得: {result.data[0]['value']}")
            return result.data[0]['value']
    except Exception as e:
        print(f"DB設定取得エラー: {e}")
    
    # DB設定がない場合は環境変数を使用
    env_provider = os.getenv('AI_PROVIDER', 'groq')
    print(f"📊 環境変数からAIプロバイダーを取得: {env_provider}")
    return env_provider

def set_ai_provider(provider):
    """AIプロバイダーをDBに保存"""
    try:
        # まず既存のレコードを削除
        supabase.table('system_settings').delete().eq('key', 'ai_provider').execute()
        
        # 新しいレコードを挿入
        supabase.table('system_settings').insert({
            'key': 'ai_provider',
            'value': provider,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }).execute()
        print(f"✅ AIプロバイダー設定をDBに保存: {provider}")
    except Exception as e:
        print(f"❌ AIプロバイダー設定保存エラー: {e}")

# Supabaseクライアントが初期化された後にAIプロバイダーを取得
ai_provider = get_ai_provider()
print(f"🤖 AIプロバイダー: {ai_provider}")

# Groqに強制設定（デバッグ用）
if ai_provider != 'groq':
    print(f"🔄 Groqに強制切り替え: {ai_provider} → groq")
    set_ai_provider('groq')
    ai_provider = 'groq'

groq_parser = GroqRecipeParser(ai_provider=ai_provider)
cost_calculator = CostCalculator(supabase) # 修正: Supabaseクライアントを渡す
cost_master_manager = CostMasterManager()

# 原価表の事前読み込み
try:
    cost_calculator.load_cost_master() # 修正: DBから直接読み込む
except Exception as e:
    print(f"原価表の初期読み込みでエラーが発生しました: {e}")


def extract_capacity_from_spec(spec_text, product_name="", unit_column=""):
    """
    規格や商品名、単位列から容量を抽出する関数
    
    Args:
        spec_text: 規格テキスト
        product_name: 商品名
        unit_column: CSVの単位列の内容（そのまま保持、変換しない）
    
    Returns:
        tuple: (capacity, unit, unit_column)
            - capacity: 容量の数値（kg→g, L→mlに変換済み）
            - unit: 容量の単位（g, ml, 個など、変換済み）
            - unit_column: CSVの単位列をそのまま保持（PC, kg, Lなど、変換しない）
    """
    if not spec_text:
        spec_text = ""
    
    # 規格から「×入数」パターンを除去
    # 「750ml×12」→「750ml」
    spec_cleaned = re.sub(r'×\d+$', '', spec_text.strip())
    
    # 容量パターンマッチング（優先順位順）
    patterns = [
        # 重量系
        (r'(\d+(?:\.\d+)?)\s*kg', lambda m: (float(m.group(1)) * 1000, 'g')),
        (r'(\d+(?:\.\d+)?)\s*g', lambda m: (float(m.group(1)), 'g')),
        # 容量系
        (r'(\d+(?:\.\d+)?)\s*L', lambda m: (float(m.group(1)) * 1000, 'ml')),
        (r'(\d+(?:\.\d+)?)\s*ml', lambda m: (float(m.group(1)), 'ml')),
        # 個数系
        (r'(\d+(?:\.\d+)?)\s*pc', lambda m: (float(m.group(1)), 'pc')),
        (r'(\d+(?:\d+)?)\s*個', lambda m: (float(m.group(1)), '個')),
        (r'(\d+(?:\.\d+)?)\s*本', lambda m: (float(m.group(1)), '本')),
        (r'(\d+(?:\.\d+)?)\s*枚', lambda m: (float(m.group(1)), '枚')),
        # パック系
        (r'(\d+(?:\.\d+)?)\s*p', lambda m: (float(m.group(1)), 'p')),
    ]
    
    # 規格から容量を抽出
    for pattern, converter in patterns:
        match = re.search(pattern, spec_cleaned, re.IGNORECASE)
        if match:
            capacity, unit = converter(match)
            # unit_columnは絶対に変換せず、そのまま返す
            return (capacity, unit, unit_column)
    
    # 商品名から容量を抽出（規格で見つからない場合）
    if product_name:
        for pattern, converter in patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                capacity, unit = converter(match)
                # unit_columnは絶対に変換せず、そのまま返す
                return (capacity, unit, unit_column)
    
    # デフォルト値
    # 規格や商品名から容量が抽出できない場合
    # - unit: 容量の単位として'個'を使用
    # - unit_column: CSVの単位列を絶対にそのまま保持（変換しない）
    return (1, '個', unit_column)


def get_user_state(user_id):
    """ユーザーの状態をDBから取得"""
    try:
        result = supabase.table('conversation_state').select('state').eq('user_id', user_id).execute()
        if result.data:
            return result.data[0].get('state', {})
    except Exception as e:
        print(f"ユーザー状態の取得エラー: {e}")
    return {}


def clear_user_state(user_id):
    """ユーザーの会話状態をクリア"""
    try:
        supabase.table("conversation_state").delete().eq("user_id", user_id).execute()
        print(f"ユーザー {user_id} の会話状態をクリアしました")
    except Exception as e:
        print(f"会話状態クリアエラー: {e}")

def set_user_state(user_id, state):
    """ユーザーの状態をDBに保存"""
    try:
        supabase.table('conversation_state').upsert({
            'user_id': user_id,
            'state': state
        }).execute()
    except Exception as e:
        print(f"ユーザー状態の保存エラー: {e}")



@app.route("/", methods=['GET'])
def admin_index():
    """管理画面のトップページ"""
    return render_template('index.html')


@app.route("/admin/upload", methods=['POST'])
def admin_upload():
    """原価表CSVファイルのアップロード"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "ファイルが選択されていません"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "ファイルが選択されていません"}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({"error": "CSVファイルのみアップロード可能です"}), 400
        
        csv_data = file.read().decode('utf-8-sig')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # 列名の自動検出
        fieldnames = csv_reader.fieldnames
        print(f"CSV columns: {fieldnames}")
        
        # 列名マッピング（テンプレート形式を優先）
        column_mapping = {}
        
        # まずテンプレート形式をチェック
        if 'ingredient_name' in fieldnames:
            column_mapping['ingredient_name'] = 'ingredient_name'
        if 'capacity' in fieldnames:
            column_mapping['capacity'] = 'capacity'
        if 'unit' in fieldnames:
            column_mapping['unit'] = 'unit'
        if 'unit_price' in fieldnames:
            column_mapping['unit_price'] = 'unit_price'
        
        # テンプレート形式が見つからない場合は自動検出
        if not column_mapping:
            for field in fieldnames:
                field_lower = field.lower().strip()
                if 'ingredient' in field_lower or '材料' in field_lower or 'name' in field_lower:
                    column_mapping['ingredient_name'] = field
                elif 'capacity' in field_lower or '容量' in field_lower:
                    column_mapping['capacity'] = field
                elif 'unit' in field_lower and 'price' not in field_lower or '単位' in field_lower:
                    column_mapping['unit'] = field
                elif 'price' in field_lower or '単価' in field_lower or 'cost' in field_lower:
                    column_mapping['unit_price'] = field
        
        print(f"Column mapping: {column_mapping}")
        
        items_dict = {}
        for row in csv_reader:
            try:
                # データの検証と変換
                ingredient_name = row.get(column_mapping.get('ingredient_name', ''), '').strip()
                unit_price = row.get(column_mapping.get('unit_price', ''), '').strip()
                
                if not ingredient_name or not unit_price:
                    print(f"Skipping row due to missing ingredient_name or unit_price: {row}")
                    continue
                
                # Supabaseに挿入するデータを作成
                data = {
                    'ingredient_name': ingredient_name,
                    'capacity': float(row.get(column_mapping.get('capacity', ''), 1)),
                    'unit': row.get(column_mapping.get('unit', ''), '個').strip(),
                    'unit_price': float(unit_price),
                    'updated_at': datetime.now().isoformat()
                }
                # 辞書を使って重複を除去（後のものが優先される）
                items_dict[ingredient_name] = data

            except (ValueError, KeyError) as e:
                print(f"Skipping row due to error: {e}. Row data: {row}")
                continue
        
        items_to_upsert = list(items_dict.values())
        count = 0
        if items_to_upsert:
            print(f"Upserting {len(items_to_upsert)} unique items in a batch.")
            result = supabase.table('cost_master').upsert(items_to_upsert, on_conflict='ingredient_name').execute()
            count = len(result.data)

        return jsonify({"success": True, "count": count})
    
    except Exception as e:
        print(f"アップロードエラー詳細: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"アップロードに失敗しました: {str(e)}"}), 500


@app.route("/admin/upload-transaction", methods=['POST'])
def admin_upload_transaction():
    """取引データCSVファイルのアップロード（正規化対応）"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "ファイルが選択されていません"}), 400
        file = request.files['file']
        if not file.filename.lower().endswith('.csv'):
            return jsonify({"error": "CSVファイルのみアップロード可能です"}), 400

        try:
            csv_data = file.read().decode('cp932')
        except UnicodeDecodeError:
            file.seek(0)
            csv_data = file.read().decode('utf-8-sig')

        csv_reader = csv.reader(io.StringIO(csv_data))
        
        extracted_materials = {}
        processed_count = 0
        
        for row in csv_reader:
            try:
                if not row or row[0] != 'D': continue

                price_str = row[18].strip()
                product = row[14].strip()
                if not product or not price_str: continue

                price = float(price_str.replace(',', ''))
                if price <= 0: continue

                supplier = row[8].strip()
                spec = row[15].strip()  # 規格（16列目）
                unit_column = row[20].strip() if len(row) > 20 else ""  # 単位列（21番目、インデックス20）
                capacity, unit, unit_column_data = extract_capacity_from_spec(spec, product, unit_column)
                
                # (商品名, 取引先名) のタプルをキーに重複排除
                item_key = (product, supplier)
                if item_key not in extracted_materials or price < extracted_materials[item_key]['price']:
                    extracted_materials[item_key] = {
                        'product': product,
                        'supplier': supplier,
                        'capacity': capacity,
                        'unit': unit,
                        'unit_column': unit_column_data,
                        'spec': spec,  # 規格も保存
                        'price': price
                    }
                processed_count += 1
            except (IndexError, ValueError) as e:
                print(f"行処理エラー（スキップ）: {e}")
                continue

        # 抽出した取引先名をDBに登録・更新
        supplier_names = {item['supplier'] for item in extracted_materials.values() if item['supplier']}
        if supplier_names:
            supplier_insert_data = [{'name': name} for name in supplier_names]
            supabase.table("suppliers").upsert(supplier_insert_data, on_conflict='name').execute()
        
        # 取引先名とIDのマップを作成
        all_suppliers = supabase.table("suppliers").select("id, name").execute().data
        supplier_name_to_id = {s['name']: s['id'] for s in all_suppliers}

        # cost_masterに登録するためのデータを作成
        items_to_upsert = []
        for item in extracted_materials.values():
            items_to_upsert.append({
                'ingredient_name': item['product'],
                'supplier_id': supplier_name_to_id.get(item['supplier']),
                'capacity': item['capacity'],
                'unit': item['unit'],
                'unit_column': item['unit_column'],
                'spec': item.get('spec', ''),  # 規格を追加
                'unit_price': item['price'],
                'updated_at': datetime.now().isoformat()
            })

        # データベースに一括で保存
        saved_count = 0
        if items_to_upsert:
            # ingredient_name, supplier_id, capacity, unit を複合キーとして重複を判断
            result = supabase.table('cost_master').upsert(items_to_upsert, on_conflict='ingredient_name,supplier_id,capacity,unit').execute()
            saved_count = len(result.data)

        return jsonify({
            "success": True, 
            "processed": processed_count,
            "extracted": len(extracted_materials),
            "saved": saved_count
        })
    
    except Exception as e:
        print(f"取引データアップロードエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"取引データのアップロードに失敗しました: {str(e)}"}), 500
@app.route("/admin/template", methods=['GET'])
def admin_template():
    """CSVテンプレートのダウンロード"""
    try:
        template_type = request.args.get('type', 'basic')
        
        # テンプレートデータの準備
        if template_type == 'basic':
            sample_data = [
                {
                    'ingredient_name': 'トマト',
                    'capacity': 1,
                    'unit': '個',
                    'unit_price': 100
                },
                {
                    'ingredient_name': '玉ねぎ',
                    'capacity': 1,
                    'unit': '個',
                    'unit_price': 80
                },
                {
                    'ingredient_name': '豚バラ肉',
                    'capacity': 100,
                    'unit': 'g',
                    'unit_price': 300
                }
            ]
        else:  # advanced
            sample_data = [
                {
                    'ingredient_name': 'トマト',
                    'capacity': 1,
                    'unit': '個',
                    'unit_price': 100,
                    'category': '野菜',
                    'notes': '中玉トマト'
                },
                {
                    'ingredient_name': '玉ねぎ',
                    'capacity': 1,
                    'unit': '個',
                    'unit_price': 80,
                    'category': '野菜',
                    'notes': '中サイズ'
                },
                {
                    'ingredient_name': '豚バラ肉',
                    'capacity': 100,
                    'unit': 'g',
                    'unit_price': 300,
                    'category': '肉類',
                    'notes': '国産'
                },
                {
                    'ingredient_name': '米',
                    'capacity': 1000,
                    'unit': 'g',
                    'unit_price': 200,
                    'category': '主食',
                    'notes': '新潟産コシヒカリ'
                }
            ]
        
        # CSVファイルの生成
        output = io.StringIO()
        if sample_data:
            fieldnames = sample_data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_data)
        
        csv_content = output.getvalue()
        output.close()
        
        # ファイルとして返す
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'cost_master_template_{template_type}.csv'
        )
    
    except Exception as e:
        print(f"テンプレート生成エラー: {e}")
        return jsonify({"error": "テンプレートの生成に失敗しました"}), 500

@app.route("/admin/template-transaction", methods=['GET'])
def admin_template_transaction():
    """取引データCSVテンプレートのダウンロード"""
    try:
        # 取引データテンプレート
        sample_data = [
            {
                'データ区分': '仕入',
                '伝票日付': '2025/10/12',
                '伝票No': 'S20251012001',
                '取引状態': '完了',
                '自社コード': '001',
                '自社会員名': 'テスト株式会社',
                '自社担当者': '田中太郎',
                '取引先コード': 'S001',
                '取引先名': 'ABC食品',
                '納品場所コード': '001',
                '納品場所名': '本社',
                '納品場所 住所': '東京都渋谷区',
                'マイカタログID': '',
                '自社管理商品コード': 'ITEM001',
                '商品名': 'トマト',
                '規格': '500g',
                '入数': '1',
                '入数単位': '個',
                '単価': '100',
                '数量': '10',
                '単位': 'g',
                '金額': '1000',
                '消費税': '100',
                '小計': '1100',
                '課税区分': '課税',
                '税区分': '10%',
                '合計 商品本体': '1000',
                '合計 商品消費税': '100',
                '合計 送料本体': '0',
                '合計 送料消費税': '0',
                '合計 その他': '0',
                '総合計': '1100',
                '発注日': '2025/10/10',
                '発送日': '2025/10/11',
                '納品日': '2025/10/12',
                '受領日': '2025/10/12',
                '取引ID_SYSTEM': 'TXN001',
                '伝票明細ID_SYSTEM': 'DETAIL001',
                '発注送信日': '2025/10/10',
                '発注送信時間': '09:00',
                '送信日': '2025/10/11',
                '送信時間': '14:00'
            },
            {
                'データ区分': '仕入',
                '伝票日付': '2025/10/12',
                '伝票No': 'S20251012002',
                '取引状態': '完了',
                '自社コード': '001',
                '自社会員名': 'テスト株式会社',
                '自社担当者': '田中太郎',
                '取引先コード': 'S002',
                '取引先名': 'XYZ肉店',
                '納品場所コード': '001',
                '納品場所名': '本社',
                '納品場所 住所': '東京都渋谷区',
                'マイカタログID': '',
                '自社管理商品コード': 'ITEM002',
                '商品名': '豚バラ肉',
                '規格': '1kg',
                '入数': '1',
                '入数単位': '100g',
                '単価': '300',
                '数量': '5',
                '単位': '100g',
                '金額': '1500',
                '消費税': '150',
                '小計': '1650',
                '課税区分': '課税',
                '税区分': '10%',
                '合計 商品本体': '1500',
                '合計 商品消費税': '150',
                '合計 送料本体': '0',
                '合計 送料消費税': '0',
                '合計 その他': '0',
                '総合計': '1650',
                '発注日': '2025/10/10',
                '発送日': '2025/10/11',
                '納品日': '2025/10/12',
                '受領日': '2025/10/12',
                '取引ID_SYSTEM': 'TXN002',
                '伝票明細ID_SYSTEM': 'DETAIL002',
                '発注送信日': '2025/10/10',
                '発注送信時間': '09:30',
                '送信日': '2025/10/11',
                '送信時間': '14:30'
            },
            {
                'データ区分': '仕入',
                '伝票日付': '2025/10/12',
                '伝票No': 'S20251012003',
                '取引状態': '完了',
                '自社コード': '001',
                '自社会員名': 'テスト株式会社',
                '自社担当者': '田中太郎',
                '取引先コード': 'S003',
                '取引先名': 'DEF飲料',
                '納品場所コード': '001',
                '納品場所名': '本社',
                '納品場所 住所': '東京都渋谷区',
                'マイカタログID': '',
                '自社管理商品コード': 'ITEM003',
                '商品名': 'オレンジジュース 750ml×12本',
                '規格': '750ml×12',
                '入数': '12',
                '入数単位': '本',
                '単価': '150',
                '数量': '2',
                '単位': 'ケース',
                '金額': '300',
                '消費税': '30',
                '小計': '330',
                '課税区分': '課税',
                '税区分': '10%',
                '合計 商品本体': '300',
                '合計 商品消費税': '30',
                '合計 送料本体': '0',
                '合計 送料消費税': '0',
                '合計 その他': '0',
                '総合計': '330',
                '発注日': '2025/10/10',
                '発送日': '2025/10/11',
                '納品日': '2025/10/12',
                '受領日': '2025/10/12',
                '取引ID_SYSTEM': 'TXN003',
                '伝票明細ID_SYSTEM': 'DETAIL003',
                '発注送信日': '2025/10/10',
                '発注送信時間': '10:00',
                '送信日': '2025/10/11',
                '送信時間': '15:00'
            }
        ]
        
        # CSVファイルの生成
        output = io.StringIO()
        if sample_data:
            fieldnames = sample_data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_data)
        
        csv_content = output.getvalue()
        output.close()
        
        # ファイルとして返す
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='transaction_template.csv'
        )
    
    except Exception as e:
        print(f"取引データテンプレート生成エラー: {e}")
        return jsonify({"error": "取引データテンプレートの生成に失敗しました"}), 500

@app.route("/admin/stats", methods=['GET'])
def admin_stats():
    """データベース統計情報の取得"""
    try:
        # 原価マスターの件数
        cost_master_result = supabase.table('cost_master').select('*').execute()
        ingredients_count = len(cost_master_result.data) if cost_master_result.data else 0
        
        # レシピの件数
        recipes_result = supabase.table('recipes').select('*').execute()
        recipes_count = len(recipes_result.data) if recipes_result.data else 0
        
        # 最終更新日時
        last_update = None
        if cost_master_result.data:
            # 最新のupdated_atを取得
            latest = max(cost_master_result.data, key=lambda x: x.get('updated_at', ''))
            last_update = latest.get('updated_at', '').split('T')[0] if latest.get('updated_at') else None
        
        return jsonify({
            "ingredients": ingredients_count,
            "recipes": recipes_count,
            "last_update": last_update
        })
    
    except Exception as e:
        print(f"統計取得エラー: {e}")
        return jsonify({"error": "統計情報の取得に失敗しました"}), 500

@app.route("/admin/data", methods=['GET'])
def admin_data():
    """データベース内容の取得"""
    try:
        # 原価マスターの取得
        cost_master_result = supabase.table('cost_master').select('*, suppliers(name)').order('ingredient_name').execute()
        
        # レシピの取得
        recipes_result = supabase.table('recipes').select('*').order('created_at', desc=True).limit(20).execute()
        
        return jsonify({
            "cost_master": cost_master_result.data if cost_master_result.data else [],
            "recipes": recipes_result.data if recipes_result.data else []
        })
    
    except Exception as e:
        print(f"データ取得エラー: {e}")
        return jsonify({"error": "データの取得に失敗しました"}), 500

@app.route("/admin/export", methods=['GET'])
def admin_export():
    """データベース内容のエクスポート"""
    try:
        # 原価マスターの取得
        result = supabase.table('cost_master').select('*').order('ingredient_name').execute()
        
        if not result.data:
            return jsonify({"error": "エクスポートするデータがありません"}), 404
        
        # CSVファイルの生成
        output = io.StringIO()
        fieldnames = ['ingredient_name', 'capacity', 'unit', 'unit_price']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in result.data:
            writer.writerow({
                'ingredient_name': row.get('ingredient_name', ''),
                'capacity': row.get('capacity', 1),
                'unit': row.get('unit', ''),
                'unit_price': row.get('unit_price', 0)
            })
        
        csv_content = output.getvalue()
        output.close()
        
        # ファイルとして返す
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'cost_master_export_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    
    except Exception as e:
        print(f"エクスポートエラー: {e}")
        return jsonify({"error": "エクスポートに失敗しました"}), 500

@app.route("/debug/logs", methods=['GET'])
def debug_logs():
    """デバッグ用：最新のログを表示"""
    try:
        # 最近のログをファイルから読み取り（簡易版）
        import os
        log_info = {
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv('RENDER', 'local'),
            "message": "デバッグエンドポイントにアクセスしました"
        }
        return jsonify(log_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug/test-ai", methods=['GET'])
def debug_test_ai():
    """デバッグ用：AIの動作テスト"""
    try:
        # テスト用のOCRテキスト
        test_ocr_text = """牛乳.
.250cc
バニラのさやl
.1/4本
卵黄
.3個
砂糖
.60g
バニラエッセンス ..
適量"""
        
        # AIで解析
        recipe_data = groq_parser.parse_recipe_text(test_ocr_text)
        
        return jsonify({
            "success": True,
            "ai_provider": ai_provider,
            "test_ocr_text": test_ocr_text,
            "parsed_recipe": recipe_data,
            "debug_info": {
                "ocr_text_length": len(test_ocr_text),
                "recipe_data_type": type(recipe_data).__name__,
                "recipe_data_is_none": recipe_data is None,
                "ai_raw_response": "詳細はログで確認してください"
            }
        })
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/debug/test-groq-raw", methods=['GET'])
def debug_test_groq_raw():
    """デバッグ用：Groqの生レスポンスを確認"""
    try:
        # シンプルなテスト用テキスト
        test_ocr_text = "牛乳 250cc\n砂糖 60g"
        
        # Groqに直接問い合わせて生レスポンスを取得
        prompt = f"""以下のテキストからレシピ情報を抽出し、JSON形式で出力してください。

{{"recipe_name": "テストレシピ", "servings": 2, "ingredients": [{{"name": "材料名", "quantity": 数値, "unit": "単位"}}]}}

テキスト: {test_ocr_text}"""

        response = groq_parser.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "あなたはJSON出力の専門家です。"},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1000
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        return jsonify({
            "success": True,
            "test_ocr_text": test_ocr_text,
            "groq_raw_response": raw_response,
            "response_length": len(raw_response)
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/debug/switch-ai", methods=['POST'])
def debug_switch_ai():
    """デバッグ用：AIプロバイダーの切り替え"""
    try:
        data = request.get_json() or {}
        new_provider = data.get('provider', 'groq')
        
        if new_provider not in ['groq', 'gpt']:
            return jsonify({"error": "Invalid provider. Use 'groq' or 'gpt'"}), 400
        
        # DBに設定を保存
        set_ai_provider(new_provider)
        
        # グローバル変数を更新
        global groq_parser
        groq_parser = GroqRecipeParser(ai_provider=new_provider)
        
        return jsonify({
            "success": True,
            "new_provider": new_provider,
            "message": f"AIプロバイダーを {new_provider} に切り替えました（DB保存済み）"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/debug/test-groq-step-by-step", methods=['GET'])
def debug_test_groq_step_by_step():
    """デバッグ用：Groq解析の各ステップを確認"""
    try:
        # テスト用のOCRテキスト（実際のLINE Botで失敗したものと同じ形式）
        test_ocr_text = """材料 【直径15cmの丸型1台分】 
スポンジケーキ [15cm] 
1枚 
ミント
適量
☆フランボワーズムース 
 ラズベリーピューレ
150g
牛乳
150cc
生クリーム 
200cc
砂糖
50g
粉ゼラチン 
5g
冷水
大さじ3
フランボワーズゼリー
ラズベリーピューレ
50g 
砂糖
大さじ1
水
大さじ2
粉ゼラチン 
2g
冷水
大さじ1"""
        
        # Groqに直接問い合わせ
        prompt = f"""以下のテキストからレシピ情報を抽出し、JSON形式で出力してください。

材料名と分量が別々の行に分かれている場合があります。次の行を確認して結合してください。
例：
- 「ミント」の次の行が「適量」→ ミント 適量
- 「牛乳」の次の行が「150cc」→ 牛乳 150cc
- 「砂糖」の次の行が「50g」→ 砂糖 50g

出力形式：
{{"recipe_name": "料理名", "servings": 2, "ingredients": [{{"name": "材料名", "quantity": 数値, "unit": "単位", "capacity": 1, "capacity_unit": "個"}}]}}

注意：
- 各材料には必ずcapacityとcapacity_unitを含めてください
- 分量が「適量」の場合は quantity: 0 としてください
- 単位が「枚」「本」「個」などの場合は適切に判定してください

テキスト：
{test_ocr_text}

JSON："""

        response = groq_parser.client.chat.completions.create(
            messages=[
                {"role": "system", "content": "あなたはJSON出力の専門家です。必ず有効なJSON形式で出力します。"},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            max_tokens=1500
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        # JSON抽出の各ステップを試す
        steps = {}
        
        # Step 1: 生レスポンス
        steps["raw_response"] = raw_response
        
        # Step 2: コードブロック除去
        if "```json" in raw_response:
            step2 = raw_response.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_response:
            step2 = raw_response.split("```")[1].split("```")[0].strip()
        else:
            step2 = raw_response
        steps["after_code_block_removal"] = step2
        
        # Step 3: JSONオブジェクト抽出
        if "{" in step2 and "}" in step2:
            start = step2.find("{")
            end = step2.rfind("}") + 1
            step3 = step2[start:end]
        else:
            step3 = step2
        steps["after_json_extraction"] = step3
        
        # Step 4: JSON解析試行
        try:
            import json
            parsed = json.loads(step3)
            steps["json_parse_success"] = True
            steps["parsed_data"] = parsed
        except Exception as e:
            steps["json_parse_success"] = False
            steps["json_parse_error"] = str(e)
        
        return jsonify({
            "success": True,
            "test_ocr_text": test_ocr_text,
            "steps": steps
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route("/recipe/edit_ingredients", methods=['GET'])
def edit_recipe_ingredients():
    user_id = request.args.get('user_id')
    if not user_id:
        return "User ID not provided", 400

    user_state = get_user_state(user_id)
    recipe_data = user_state.get('recipe_data')

    if not recipe_data:
        return "Recipe data not found in session. Please send an image again.", 404

    # 各材料の単価をcost_masterから取得してrecipe_dataに追加
    for ingredient in recipe_data.get('ingredients', []):
        ingredient_name = ingredient.get('name')
        if ingredient_name:
            # cost_masterから単価を取得
            # cost_master_manager.get_cost_info(ingredient_name) は単一の材料名で検索するため、
            # 複数の容量や単位を持つ材料に対応できない可能性がある。
            # ここでは簡易的に、最も近いと思われる単価を取得する。
            # 理想的には、name, capacity, unitで複合検索すべきだが、現在のget_cost_infoは単一のnameのみ。
            # したがって、ここではsearch_costsを使用して、
            # 複数の結果から最も関連性の高いものを選択するか、最初の結果を使用する。
            
            # 既存のcost_master_manager.get_cost_infoは単一の材料名で検索するため、
            # ここではsearch_costsを使って、より柔軟に単価を取得する
            search_results = cost_master_manager.search_costs(ingredient_name, limit=1)
            if search_results:
                # 最初の結果の単価を使用
                ingredient['unit_price'] = search_results[0].get('unit_price')
            else:
                ingredient['unit_price'] = None # 見つからない場合はNone

    # recipe_dataは辞書なので、テンプレートに渡す前にオブジェクトのようにアクセスできるようにする
    class RecipeData:
        def __init__(self, data):
            self.__dict__ = data
    
    recipe_obj = RecipeData(recipe_data)

    return render_template('edit_recipe_ingredients.html', 
                           user_id=user_id, 
                           recipe_data=recipe_obj,
                           error_message=request.args.get('error_message'),
                           success_message=request.args.get('success_message'))


@app.route("/admin/clear", methods=['POST'])
def admin_clear():
    """データベース内容のクリア（選択式）"""
    try:
        data = request.get_json() or {}
        clear_cost_master = data.get('clear_cost_master', False)
        clear_recipes = data.get('clear_recipes', False)
        
        deleted_items = []
        
        if clear_recipes:
            # 外部キー制約のため、子テーブル（ingredients）から先に削除する
            supabase.table('ingredients').delete().neq('ingredient_name', '').execute()
            supabase.table('recipes').delete().neq('recipe_name', '').execute()
            deleted_items.append('保存レシピ')
        
        if clear_cost_master:
            # 原価マスターのクリア
            supabase.table('cost_master').delete().neq('ingredient_name', '').execute()
            deleted_items.append('登録材料')
        
        if not deleted_items:
            return jsonify({"error": "削除するデータが選択されていません"}), 400
        
        message = f"データをクリアしました: {', '.join(deleted_items)}"
        return jsonify({"success": True, "message": message})
    
    except Exception as e:
            print(f"クリアエラー: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": f"データのクリアに失敗しました: {str(e)}"}), 500


# ==================== 材料フォーム関連 ====================

@app.route("/ingredient/form")
def ingredient_form():
    """材料追加・修正フォームの表示"""
    try:
        # URLパラメータから材料IDを取得（修正モードの場合）
        ingredient_id = request.args.get('id')
        is_edit = bool(ingredient_id)
        ingredient_data = None
        
        if is_edit and ingredient_id:
            # 既存データを取得
            response = supabase.table('cost_master').select('*').eq('id', ingredient_id).execute()
            if response.data:
                ingredient_data = response.data[0]
                # 取引先情報も取得
                if ingredient_data.get('supplier_id'):
                    supplier_response = supabase.table('suppliers').select('name').eq('id', ingredient_data['supplier_id']).execute()
                    if supplier_response.data:
                        ingredient_data['suppliers'] = supplier_response.data[0]
        
        return render_template('ingredient_form.html', 
                             is_edit=is_edit, 
                             ingredient_data=ingredient_data,
                             csrf_token=csrf.generate_csrf if csrf else None)
        
    except Exception as e:
        print(f"フォーム表示エラー: {e}")
        import traceback
        traceback.print_exc()
        return render_template('ingredient_form.html', 
                             is_edit=False, 
                             ingredient_data=None,
                             error_message="フォームの読み込みに失敗しました",
                             csrf_token=csrf.generate_csrf if csrf else None)


@app.route("/ingredient/submit", methods=['POST'])
def submit_ingredient_form():
    """材料フォームの送信処理"""
    try:
        # フォームデータを取得
        ingredient_name = request.form.get('ingredient_name', '').strip()
        supplier_name = request.form.get('supplier', '').strip()
        capacity = request.form.get('capacity', '')
        unit = request.form.get('unit', '')
        unit_column = request.form.get('unit_column', '').strip()
        spec = request.form.get('spec', '').strip()
        unit_price = request.form.get('unit_price', '')
        is_edit = request.form.get('is_edit') == 'True'
        ingredient_id = request.form.get('ingredient_id')
        
        # バリデーション
        if not ingredient_name:
            return render_template('ingredient_form.html',
                                 is_edit=is_edit,
                                 ingredient_data=None,
                                 error_message="材料名は必須です",
                                 csrf_token=csrf.generate_csrf if csrf else None)
        
        if not unit_price:
            return render_template('ingredient_form.html',
                                 is_edit=is_edit,
                                 ingredient_data=None,
                                 error_message="単価は必須です",
                                 csrf_token=csrf.generate_csrf if csrf else None)
        
        try:
            capacity = float(capacity) if capacity else 1.0
            unit_price = float(unit_price)
        except ValueError:
            return render_template('ingredient_form.html',
                                 is_edit=is_edit,
                                 ingredient_data=None,
                                 error_message="容量または単価の値が不正です",
                                 csrf_token=csrf.generate_csrf if csrf else None)
        
        # 取引先の処理
        supplier_id = None
        if supplier_name:
            # 取引先が存在するかチェック
            supplier_response = supabase.table('suppliers').select('id').eq('name', supplier_name).execute()
            if supplier_response.data:
                supplier_id = supplier_response.data[0]['id']
            else:
                # 新規取引先を作成
                new_supplier = supabase.table('suppliers').insert({
                    'name': supplier_name,
                    'created_at': datetime.now().isoformat()
                }).execute()
                supplier_id = new_supplier.data[0]['id']
        
        # データベースに保存
        data = {
            'ingredient_name': ingredient_name,
            'capacity': capacity,
            'unit': unit,
            'unit_column': unit_column,
            'spec': spec,
            'unit_price': unit_price,
            'supplier_id': supplier_id,
            'updated_at': datetime.now().isoformat()
        }
        
        if is_edit and ingredient_id:
            # 更新
            result = supabase.table('cost_master').update(data).eq('id', ingredient_id).execute()
            success_message = f"「{ingredient_name}」の情報を更新しました"
        else:
            # 新規作成
            data['created_at'] = datetime.now().isoformat()
            result = supabase.table('cost_master').insert(data).execute()
            success_message = f"「{ingredient_name}」を追加しました"
        
        return render_template('ingredient_form.html',
                             is_edit=False,
                             ingredient_data=None,
                             success_message=success_message,
                             csrf_token=csrf.generate_csrf if csrf else None)
        
    except Exception as e:
        print(f"フォーム送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return render_template('ingredient_form.html',
                             is_edit=is_edit if 'is_edit' in locals() else False,
                             ingredient_data=None,
                             error_message="データの保存に失敗しました",
                             csrf_token=csrf.generate_csrf if csrf else None)

@app.route("/health", methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント（Render用）"""
    return "OK", 200


@app.route("/callback", methods=['POST'])
def callback():
    """LINE Webhook コールバック"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    
    return 'OK'


@handler.add(MessageEvent, message=ImageMessageContent)


def handle_image_message(event):


    """画像メッセージの処理"""


    try:


        # 画像の取得
        message_id = event.message.id
        print(f"🔍 画像メッセージID: {message_id}")
        
        # LINE Bot SDK v3では get_message_content が直接bytesを返す
        image_bytes = line_bot_blob_api.get_message_content(message_id)
        print(f"🔍 取得データ型: {type(image_bytes)}")
        
        # bytesでない場合の処理
        if not isinstance(image_bytes, bytes):
            print(f"⚠️ 予期しないデータ型です。変換を試みます...")
            try:
                # iter_contentメソッドがある場合
                if hasattr(image_bytes, 'iter_content'):
                    print("📥 ストリーミング方式で取得します...")
                    temp_bytes = b''
                    for chunk in image_bytes.iter_content(chunk_size=8192):
                        if chunk:
                            temp_bytes += chunk
                    image_bytes = temp_bytes
                    print(f"✅ ストリーミング取得成功: {len(image_bytes)} bytes")
                # contentプロパティがある場合
                elif hasattr(image_bytes, 'content'):
                    print("📥 contentプロパティから取得します...")
                    image_bytes = image_bytes.content
                    print(f"✅ content取得成功: {len(image_bytes)} bytes")
                # read()メソッドがある場合
                elif hasattr(image_bytes, 'read'):
                    print("📥 read()メソッドで取得します...")
                    image_bytes = image_bytes.read()
                    print(f"✅ read()取得成功: {len(image_bytes)} bytes")
                else:
                    print(f"❌ 画像データの変換方法が見つかりません")
                    print(f"利用可能なメソッド: {[m for m in dir(image_bytes) if not m.startswith('_')]}")
                    line_bot_api.reply_message(ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="画像の取得に失敗しました。データ形式が不正です。")]
                    ))
                    return
            except Exception as e:
                print(f"❌ 画像データ変換エラー: {e}")
                import traceback
                traceback.print_exc()
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="画像の取得に失敗しました。")]
                ))
                return
        
        # 画像データの検証
        if not image_bytes or len(image_bytes) == 0:
            print(f"❌ 画像データが空です")
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="画像データが空です。")]
            ))
            return
            
        print(f"✅ 画像データ取得成功: {len(image_bytes)} bytes")


        


        # ステップ1: Azure Visionで画像解析


        reply_message = "画像を受け取りました。解析中です..."


        line_bot_api.reply_message(ReplyMessageRequest(


            reply_token=event.reply_token,


            messages=[TextMessage(text=reply_message)]


        ))


        


        try:
            print(f"🔍 Azure Vision API呼び出し開始: {len(image_bytes)} bytes")
            ocr_text, detected_language = azure_analyzer.analyze_image_from_bytes(image_bytes)
            print(f"✅ Azure Vision API呼び出し成功")
        except Exception as e:
            print(f"❌ Azure Vision API呼び出しエラー: {e}")
            import traceback
            traceback.print_exc()
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="画像解析に失敗しました。")]
            ))
            return


        


        if not ocr_text:


            line_bot_api.push_message(PushMessageRequest(


                to=event.source.user_id,


                messages=[TextMessage(text="画像からテキストを抽出できませんでした。" )]


            ))


            return


        


        print(f"OCR結果 (言語: {detected_language}):\n{ocr_text}")





        # 日本語以外の場合は翻訳


        if detected_language != 'ja':


            print(f"翻訳を実行します: {detected_language} -> ja")


            translated_text = groq_parser.translate_text(ocr_text)


            if not translated_text:


                line_bot_api.push_message(PushMessageRequest(


                    to=event.source.user_id,


                    messages=[TextMessage(text="テキストの翻訳に失敗しました。" )]


                ))


                return


            print(f"翻訳結果:\n{translated_text}")


            ocr_text = translated_text # 解析には翻訳後のテキストを使用





        # ステップ2: Groqでレシピ構造化
        print(f"🔍 Groq解析開始...")
        print(f"📄 OCRテキスト (全{len(ocr_text)}文字):\n{repr(ocr_text)}")
        
        # OCRテキストの前処理（余分な文字を除去）
        print(f"🔧 前処理開始...")
        cleaned_ocr_text = ocr_text.strip()
        print(f"📝 元のOCRテキスト長: {len(cleaned_ocr_text)}")
        
        # 強制的に余分な文字を除去
        if '料理を楽しむにあたって' in cleaned_ocr_text:
            cleaned_ocr_text = cleaned_ocr_text.split('料理を楽しむにあたって')[0].strip()
            print(f"✅ '料理を楽しむにあたって' を除去")
        
        # 末尾の数字のみを除去（材料の分量は保持）
        if '\n6' in cleaned_ocr_text and cleaned_ocr_text.endswith('\n6料理を楽しむにあたって'):
            cleaned_ocr_text = cleaned_ocr_text.split('\n6')[0].strip()
            print(f"✅ 末尾の余分な文字 '\\n6料理を楽しむにあたって' を除去")
        elif cleaned_ocr_text.endswith('6料理を楽しむにあたって'):
            cleaned_ocr_text = cleaned_ocr_text.replace('6料理を楽しむにあたって', '').strip()
            print(f"✅ 末尾の余分な文字 '6料理を楽しむにあたって' を除去")
        
        # 連続する改行を単一の改行に統一
        lines = [line.strip() for line in cleaned_ocr_text.split('\n') if line.strip()]
        cleaned_ocr_text = '\n'.join(lines)
        print(f"✅ 改行を正規化: {len(lines)}行")
        
        print(f"🧹 前処理完了: {len(cleaned_ocr_text)}文字")
        print(f"📄 前処理後のOCRテキスト:\n{repr(cleaned_ocr_text)}")
        
        recipe_data = groq_parser.parse_recipe_text(cleaned_ocr_text)
        
        if not recipe_data:
            print(f"❌ Groq解析失敗: recipe_dataがNone")
            print(f"🔍 失敗したOCRテキスト (全{len(ocr_text)}文字):\n{repr(ocr_text)}")
            # OCRテキストを整形して表示
            formatted_text = _format_ocr_text_for_display(ocr_text)
            line_bot_api.push_message(PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text=f"レシピ情報を解析できませんでした。\n\n📄 抽出されたテキスト:\n{formatted_text}") ]
            ))
            return

        # 解析成功時は選択肢を表示
        print(f"✅ Groq解析成功: {recipe_data}")
        create_recipe_review_flex_message(recipe_data, event.source.user_id)
        return


        


        print(f"解析されたレシピ: {recipe_data}")


        


        # ステップ3: 原価計算


        cost_result = cost_calculator.calculate_recipe_cost(recipe_data['ingredients'])


        


        # ステップ4: Supabaseに保存


        recipe_id = save_recipe_to_supabase(


            recipe_data['recipe_name'],


            recipe_data['servings'],


            cost_result['total_cost'],


            cost_result['ingredients_with_cost']


        )


        


        # 会話状態を保存


        user_id = event.source.user_id


        new_state = {


            'last_action': 'recipe_analysis',


            'recipe_name': recipe_data['recipe_name'],


            'servings': recipe_data['servings'],


            'cost_result': cost_result,


            'timestamp': datetime.now().isoformat()


        }


        set_user_state(user_id, new_state)





        # ステップ5: LINEで結果を返信


        response_message = format_cost_response(


            recipe_data['recipe_name'],


            recipe_data['servings'],


            cost_result['ingredients_with_cost'],


            cost_result['total_cost'],


            cost_result['missing_ingredients']


        )


        


        line_bot_api.push_message(PushMessageRequest(


            to=event.source.user_id,


            messages=[TextMessage(text=response_message)]


        ))


        


    except Exception as e:


        print(f"エラー: {e}")


        line_bot_api.push_message(PushMessageRequest(


            to=event.source.user_id,


            messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]


        ))


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """テキストメッセージの処理"""
    text = event.message.text.strip()
    user_id = event.source.user_id

    # まず、フォローアップ質問かどうかを判定
    follow_up_answer = handle_follow_up_question(user_id, text)
    if follow_up_answer:
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=follow_up_answer)]))
        return

    # フォローアップでない場合は、通常のコマンド処理を続ける
    # ヘルプコマンド
    if text == "ヘルプ" or text.lower() == "help":
        help_message = """【レシピ原価計算Bot】

📸 レシピ解析:
レシピの画像を送信してください
→ 自動的に解析し、原価を計算します

🔍 材料検索:
材料名を入力するだけで検索
  例: 「トマト」「豚肉」「牛乳」
→ 単価・容量・取引先を表示

💰 原価表の管理:
・追加: 「追加 材料名 価格/単位」
  例: 「追加 トマト 100円/個」
  例: 「追加 豚肉 300円/100g」
  例: 「追加 牛乳 1L 200円」
  例: 「追加 米 5kg 2000円」
・確認: 「確認 材料名」
  例: 「確認 トマト」
・削除: 「削除 材料名」
  例: 「削除 トマト」
・一覧: 「原価一覧」

🎯 UI機能:
・「材料追加」→ ボタンで簡単に材料を追加
・「材料を追加」→ 同上

※原価表に登録されていない材料は計算されません"""
        
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=help_message)]
        ))
        return
    
    # 原価追加コマンド
    if text.startswith("追加 ") or text.startswith("追加　"):
        handle_add_cost_command(event, text)
        return
    
    # 原価確認コマンド
    if text.startswith("確認 ") or text.startswith("確認　"):
        handle_check_cost_command(event, text)
        return
    
    # 原価削除コマンド
    if text.startswith("削除 ") or text.startswith("削除　"):
        handle_delete_cost_command(event, text)
        return
    
    # 原価一覧コマンド
    if text == "原価一覧" or text == "一覧":
        handle_list_cost_command(event)
        return
    
    # 材料追加UIコマンド（LINE UI機能が利用可能な場合のみ）
    if text == "材料追加" or text == "材料を追加":
        if LINE_UI_AVAILABLE:
            send_ingredient_add_menu(event)
            return
        else:
            reply_text = "材料追加機能は現在利用できません。代わりに以下の形式で追加してください：\n\n「追加 材料名 価格」\n例: 「追加 トマト 100円/個」"
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            ))
            return
    
    # 材料名検索（その他のテキスト）
    # コマンド以外のテキストは直接材料名として検索
    if len(text) >= 2 and not text.startswith('/'):
        print(f"🔍 材料検索処理開始: '{text}'")
        handle_search_ingredient(event, text)
    else:
        print(f"⚠️ 材料検索スキップ: '{text}' (長さ: {len(text)})")



def create_add_ingredient_flex_message(search_term):
    """新規材料追加用のFlex Messageを作成"""
    try:
        # コンテンツを構築
        contents = []
        
        # タイトル
        contents.append({
            "type": "text",
            "text": "➕ 新規材料追加",
            "weight": "bold",
            "size": "lg",
            "color": "#FF6B6B"
        })
        
        # 材料名
        contents.append({
            "type": "text",
            "text": f"材料名: {search_term}",
            "size": "md",
            "color": "#333333",
            "margin": "md"
        })
        
        # 説明
        contents.append({
            "type": "text",
            "text": "この材料は原価表に登録されていません。\nボタンをタップしてフォームで追加してください。",
            "size": "sm",
            "color": "#666666",
            "margin": "md",
            "wrap": True
        })
        
        # フッター（入力フォーム用ボタン）
        add_form_url = "https://recipe-management-nd00.onrender.com/ingredient/form"
        footer_contents = [{
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "uri",
                "label": "📝 材料を追加",
                "uri": add_form_url
            }
        }]
        
        # Flex Messageを構築
        flex_container = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents,
                "paddingAll": "16px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": footer_contents,
                "paddingAll": "8px"
            }
        }
        
        return flex_container
        
    except Exception as e:
        print(f"新規追加Flex Message作成エラー: {e}")
        return None

def create_ingredient_flex_message(cost, is_single=True):
    """材料情報のFlex Messageを作成"""
    try:
        # データを取得
        ingredient_name = cost['ingredient_name']
        capacity = cost.get('capacity', 1.0)
        unit = cost.get('unit', '個')
        unit_column = cost.get('unit_column', '')
        spec = cost.get('spec', '')
        unit_price = cost.get('unit_price', 0)
        supplier_name = cost.get('suppliers', {}).get('name', '') if cost.get('suppliers') else ''
        
        # 容量表示の調整
        if capacity == 0 or capacity == 1 or capacity == 1.0:
            capacity_str = ""
        else:
            capacity_str = str(int(capacity)) if capacity == int(capacity) else str(capacity)
        
        # 単位表示
        if unit_column is not None:
            unit_display = unit_column if unit_column else "個"
        else:
            unit_display = unit
        
        # 単価表示
        unit_price = int(unit_price) if unit_price == int(unit_price) else unit_price
        
        # コンテンツを構築
        contents = []
        
        # 材料名
        contents.append({
            "type": "text",
            "text": ingredient_name,
            "weight": "bold",
            "size": "lg",
            "color": "#1DB446"
        })
        
        # 詳細情報
        details = []
        if capacity_str:
            details.append(f"容量: {capacity_str}")
        details.append(f"単位: {unit_display}")
        details.append(f"単価: ¥{unit_price}")
        
        if supplier_name:
            details.append(f"取引先: {supplier_name}")
        
        if spec:
            details.append(f"規格: {spec}")
        
        contents.append({
            "type": "text",
            "text": "\n".join(details),
            "size": "sm",
            "color": "#666666",
            "wrap": True
        })
        
        # フッター（修正ボタン）
        form_url = f"https://recipe-management-nd00.onrender.com/ingredient/form?id={cost['id']}"
        footer_contents = [{
            "type": "button",
            "style": "primary",
            "height": "sm",
            "action": {
                "type": "uri",
                "label": "📝 修正",
                "uri": form_url
            }
        }]
        
        # Flex Messageを構築
        flex_container = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": contents,
                "paddingAll": "16px"
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": footer_contents,
                "paddingAll": "8px"
            }
        }
        
        return flex_container
        
    except Exception as e:
        print(f"Flex Message作成エラー: {e}")
        return None

def handle_search_ingredient(event, search_term: str):
    """
    材料名検索の処理
    例: 「トマト」と入力すると関連する材料を検索
    """
    try:
        print(f"🔍 材料検索開始: '{search_term}'")
        
        # 検索キーワードが短すぎる場合はスキップ
        if len(search_term) < 2:
            print(f"⚠️ 検索キーワードが短すぎます: '{search_term}'")
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="レシピの画像を送信するか、「ヘルプ」と入力してください。")]
            ))
            return
        
        # 材料名で検索
        print(f"🔍 データベース検索実行: '{search_term}'")
        results = cost_master_manager.search_costs(search_term, limit=5)
        print(f"📊 検索結果: {len(results) if results else 0}件")
        
        if not results:
            # 材料が見つからない場合のFlex Messageを作成
            add_flex_container = create_add_ingredient_flex_message(search_term)
            
            if add_flex_container:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text=f"「{search_term}」の新規追加",
                        contents=FlexContainer.from_dict(add_flex_container)
                    )]
                ))
            else:
                # Flex Message作成に失敗した場合はテキストで返信
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"""「{search_term}」に一致する材料が見つかりませんでした。

原価表に登録するには：

✅ 推奨形式：
・「追加 {search_term} 100円/個」
・「追加 {search_term} 200円/kg」

💡 簡単形式（円は省略可）：
・「追加 {search_term} 100 個」
・「追加 {search_term} 200 kg」""")]
                ))
            return
        
        # 結果をFlex Messageで送信
        if len(results) == 1:
            # 完全一致または1件のみの場合
            cost = results[0]
            
            # Flex Messageを作成
            flex_container = create_ingredient_flex_message(cost, is_single=True)
            
            if flex_container:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(
                        alt_text=f"「{search_term}」の検索結果",
                        contents=FlexContainer.from_dict(flex_container)
                    )]
                ))
            else:
                # Flex Message作成に失敗した場合はテキストで返信
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"「{search_term}」の検索結果を取得しましたが、表示に失敗しました。")]
                ))
        else:
            # 複数候補がある場合もFlex Messageで統一表示
            # 検索結果の件数を最初に送信
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"🔍 「{search_term}」の検索結果（{len(results)}件）")]
            ))
            
            # 各材料をFlex Messageで送信（最大5件まで）
            for i, cost in enumerate(results[:5], 1):
                flex_container = create_ingredient_flex_message(cost, is_single=False)
                
                if flex_container:
                    line_bot_api.push_message(PushMessageRequest(
                        to=event.source.user_id,
                        messages=[FlexMessage(
                            alt_text=f"「{search_term}」の検索結果 {i}",
                            contents=FlexContainer.from_dict(flex_container)
                        )]
                    ))
            
            # 6件以上ある場合は追加情報を送信
            if len(results) > 5:
                line_bot_api.push_message(PushMessageRequest(
                    to=event.source.user_id,
                    messages=[TextMessage(text=f"... 他{len(results) - 5}件あります。より具体的な材料名で検索してください。")]
                ))
        
    except Exception as e:
        print(f"❌ 材料検索エラー: {e}")
        import traceback
        traceback.print_exc()
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"検索中にエラーが発生しました: {str(e)}")]
        ))



def handle_add_cost_command(event, text: str):
    """
    原価追加コマンドの処理
    例: 「追加 トマト 100円/個」
    """
    try:
        # 「追加 」を除去
        cost_text = text.replace("追加 ", "").replace("追加　", "").strip()
        
        if not cost_text:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="原価情報を入力してください。\n例: 「追加 トマト 100円/個」")]
            ))
            return
        
        # Groqで解析
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="原価情報を解析中です...")]
        ))
        
        cost_data = cost_master_manager.parse_cost_text(cost_text)
        
        if not cost_data:
            line_bot_api.push_message(PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text="""原価情報の解析に失敗しました。

以下の形式で入力してください：

✅ 正しい例：
・「追加 みかん 100円/個」
・「追加 みかん 100 個」（円は省略可）
・「追加 トマト 200円/kg」
・「追加 玉ねぎ 150円/500g」

❌ 避けるべき例：
・「追加 みかん 100 個」（価格と単位が不明確）
・「追加 みかん 個 100」（順序が逆）""")]
            ))
            return
        
        # 原価表に追加
        success = cost_master_manager.add_or_update_cost(
            cost_data['ingredient_name'],
            cost_data['capacity'],
            cost_data['unit'],
            cost_data['unit_price'],
            ""  # unit_columnは空文字列（LINEからの追加では使用しない）
        )
        
        if success:
            # 原価計算機のキャッシュも更新
            try:
                cost_calculator.load_cost_master()
            except:
                pass
            
            response = f"""✅ 原価表に登録しました

【材料名】{cost_data['ingredient_name']}
【容量】{cost_data['capacity']}{cost_data['unit']}
【単価】¥{cost_data['unit_price']:.2f}"""
            
            line_bot_api.push_message(PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text=response)]
            ))
        else:
            line_bot_api.push_message(PushMessageRequest(
                to=event.source.user_id,
                messages=[TextMessage(text="原価表への登録に失敗しました。")]
            ))
            
    except Exception as e:
        print(f"原価追加エラー: {e}")
        line_bot_api.push_message(PushMessageRequest(
            to=event.source.user_id,
            messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]
        ))



def handle_check_cost_command(event, text: str):
    """
    原価確認コマンドの処理
    例: 「確認 トマト」
    """
    try:
        # 「確認 」を除去
        ingredient_name = text.replace("確認 ", "").replace("確認　", "").strip()
        
        if not ingredient_name:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="材料名を入力してください。\n例: 「確認 トマト」")]
            ))
            return
        
        # 原価表から取得
        cost_info = cost_master_manager.get_cost_info(ingredient_name)
        
        if cost_info:
            response = f"""📋 原価情報

【材料名】{cost_info['ingredient_name']}
【容量】{cost_info['capacity']}{cost_info['unit']}
【単価】¥{cost_info['unit_price']:.2f}
【更新日】{cost_info.get('updated_at', 'N/A')}"""
            
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=response)]
            ))
        else:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"「{ingredient_name}」は原価表に登録されていません。")]
            ))
            
    except Exception as e:
        print(f"原価確認エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]
        ))


def handle_delete_cost_command(event, text: str):
    """
    原価削除コマンドの処理
    例: 「削除 トマト」
    """
    try:
        # 「削除 」を除去
        ingredient_name = text.replace("削除 ", "").replace("削除　", "").strip()
        
        if not ingredient_name:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="材料名を入力してください。\n例: 「削除 トマト」")]
            ))
            return
        
        # 削除前に確認
        cost_info = cost_master_manager.get_cost_info(ingredient_name)
        
        if not cost_info:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"「{ingredient_name}」は原価表に登録されていません。")]
            ))
            return
        
        # 削除実行
        success = cost_master_manager.delete_cost(ingredient_name)
        
        if success:
            # 原価計算機のキャッシュも更新
            try:
                cost_calculator.load_cost_master()
            except:
                pass
            
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"✅ 「{ingredient_name}」を原価表から削除しました。")]
            ))
        else:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="削除に失敗しました。")]
            ))
            
    except Exception as e:
        print(f"原価削除エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]
        ))


def handle_list_cost_command(event):
    """
    原価一覧コマンドの処理
    """
    try:
        costs = cost_master_manager.list_all_costs(limit=30)
        
        if not costs:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="原価表に登録されている材料はありません。")]
            ))
            return
        
        # 一覧をフォーマット
        response = f"📋 原価一覧（{len(costs)}件）\n\n"
        
        for i, cost in enumerate(costs, 1):
            # 単位情報の表示
            unit_column = cost.get('unit_column', '')
            capacity = cost.get('capacity', 1)
            unit = cost.get('unit', '個')
            
            # 容量の表示（0または1の場合は表示しない、整数で表示）
            if capacity == 0 or capacity == 1 or capacity == 1.0:
                capacity_str = ""
            else:
                capacity_str = str(int(capacity)) if capacity == int(capacity) else str(capacity)
            
            # 単位列を必ず表示（単位のみ）
            if unit_column:
                unit_display = unit_column
            else:
                unit_display = unit
            
            # 単価は整数で表示
            unit_price = int(cost['unit_price']) if cost['unit_price'] == int(cost['unit_price']) else cost['unit_price']
            
            response += f"{i}. {cost['ingredient_name']}\n"
            response += f"   {unit_display} = ¥{unit_price}\n"
            
            if i >= 20:  # LINEメッセージの長さ制限対策
                response += f"\n... 他{len(costs) - 20}件"
                break
        
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=response)]
        ))
        
    except Exception as e:
        print(f"原価一覧エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"エラーが発生しました: {str(e)}")]
        ))


def save_recipe_to_supabase(recipe_name: str, servings: int, total_cost: float, ingredients: list, recipe_id: Optional[str] = None) -> str:
    """
    レシピをSupabaseに保存または更新
    
    Args:
        recipe_name: 料理名
        servings: 何人前
        total_cost: 合計原価
        ingredients: 材料リスト（原価付き）
        recipe_id: 更新対象のレシピID（オプション）
        
    Returns:
        保存または更新されたレシピのID
    """
    recipe_data_to_save = {
        'recipe_name': recipe_name,
        'servings': servings,
        'total_cost': total_cost
    }
    
    if recipe_id:
        # 既存レシピを更新
        supabase.table('recipes').update(recipe_data_to_save).eq('id', recipe_id).execute()
        print(f"レシピを更新しました: {recipe_id}")
        # 既存の材料を削除してから再挿入（シンプルにするため）
        supabase.table('ingredients').delete().eq('recipe_id', recipe_id).execute()
    else:
        # 新規レシピを挿入
        recipe_response = supabase.table('recipes').insert(recipe_data_to_save).execute()
        recipe_id = recipe_response.data[0]['id']
        print(f"レシピを保存しました: {recipe_id}")
    
    # 材料テーブルに保存
    for ingredient in ingredients:
        ingredient_data = {
            'recipe_id': recipe_id,
            'ingredient_name': ingredient['name'],
            'quantity': ingredient['quantity'],
            'unit': ingredient['unit'],
            'cost': ingredient.get('cost'), # costはcalculate_recipe_costで設定される
            'capacity': ingredient.get('capacity', 1),
            'capacity_unit': ingredient.get('capacity_unit', '個')
        }
        supabase.table('ingredients').insert(ingredient_data).execute()
    
    return recipe_id


def create_recipe_review_flex_message(recipe_data, user_id):
    """レシピ確認用のFlexMessageを作成"""
    try:
        # 材料リストを整形
        ingredients_text = ""
        for i, ingredient in enumerate(recipe_data.get('ingredients', []), 1):
            name = ingredient.get('name', '')
            quantity = ingredient.get('quantity', 0)
            unit = ingredient.get('unit', '')
            ingredients_text += f"{i}. {name} {quantity}{unit}\n"
        
        # FlexMessageのコンテナを作成
        flex_container = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📋 レシピ解析結果",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#1DB446"
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": f"料理名: {recipe_data.get('recipe_name', 'カスタムレシピ')}",
                                "weight": "bold",
                                "size": "md"
                            },
                            {
                                "type": "text",
                                "text": f"人数: {recipe_data.get('servings', 2)}人前",
                                "size": "sm",
                                "color": "#666666"
                            }
                        ]
                    },
                    {
                        "type": "separator",
                        "margin": "md"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "md",
                        "contents": [
                            {
                                "type": "text",
                                "text": "材料リスト:",
                                "weight": "bold",
                                "size": "sm"
                            },
                            {
                                "type": "text",
                                "text": ingredients_text.strip(),
                                "size": "sm",
                                "wrap": True,
                                "margin": "sm"
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "💰 原価計算する",
                            "data": f"calculate_cost:{user_id}"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "✏️ 材料を修正",
                            "data": f"edit_recipe:{user_id}"
                        }
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "postback",
                            "label": "💾 そのまま登録",
                            "data": f"save_recipe:{user_id}"
                        }
                    }
                ]
            }
        }
        
        # レシピデータを一時保存
        set_user_state(user_id, {
            'last_action': 'recipe_analysis',
            'recipe_data': recipe_data,
            'timestamp': datetime.now().isoformat()
        })
        
        # FlexMessageを送信
        line_bot_api.push_message(PushMessageRequest(
            to=user_id,
            messages=[FlexMessage(
                alt_text="レシピ解析結果の確認",
                contents=FlexContainer.from_dict(flex_container)
            )]
        ))
        
    except Exception as e:
        print(f"❌ FlexMessage作成エラー: {e}")
        import traceback
        traceback.print_exc()
        
        # エラー時は通常のテキストメッセージ
        line_bot_api.push_message(PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=f"レシピ解析が完了しました！\n\n料理名: {recipe_data.get('recipe_name', 'カスタムレシピ')}\n人数: {recipe_data.get('servings', 2)}人前\n\n材料:\n{ingredients_text}")]
        ))


def _format_ocr_text_for_display(ocr_text):
    """OCRテキストを見やすく整形して、材料名と分量を正しく関連付ける"""
    if not ocr_text:
        return "テキストが抽出されませんでした"
    
    # 改行で分割して、空行を削除
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    formatted_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 材料名の可能性をチェック（点で終わる、または文字が多く数字が少ない）
        is_ingredient_line = (
            (line.endswith('.') and not any(char.isdigit() for char in line) and len(line) > 2) or
            (not any(char.isdigit() for char in line) and 
             not line.startswith('.') and 
             len(line) > 1 and
             not any(unit in line for unit in ['cc', 'g', 'ml', '個', '本', '玉', '丁', '袋', '大さじ', '小さじ', 'カップ', '適量']))
        )
        
        if is_ingredient_line:
            # 材料名として認識（末尾の点を除去）
            ingredient = line.rstrip('.')
            
            # 次の行をチェックして分量を探す
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                
                # 分量の可能性をチェック
                is_quantity_line = (
                    next_line.startswith('.') or 
                    any(char.isdigit() for char in next_line) or
                    any(unit in next_line for unit in ['cc', 'g', 'ml', '個', '本', '玉', '丁', '袋', '大さじ', '小さじ', 'カップ', '適量'])
                )
                
                if is_quantity_line:
                    # 分量として認識（先頭の点を除去）
                    quantity = next_line.lstrip('.')
                    
                    # 一行で表示
                    formatted_lines.append(f"• {ingredient}: {quantity}")
                    i += 2  # 材料名と分量の両方を処理
                else:
                    # 分量が見つからない場合は材料名のみ
                    formatted_lines.append(f"• {ingredient}")
                    i += 1
            else:
                # 次の行がない場合は材料名のみ
                formatted_lines.append(f"• {ingredient}")
                i += 1
                
        # 材料名と分量が既に結合されている行
        elif ':' in line and (any(char.isdigit() for char in line) or '適量' in line):
            formatted_lines.append(f"• {line}")
            i += 1
            
        # 分量だけの行（点で始まる）
        elif line.startswith('.') and (any(char.isdigit() for char in line) or '適量' in line):
            quantity = line.lstrip('.')
            formatted_lines.append(f"• 分量不明: {quantity}")
            i += 1
            
        # その他の行
        else:
            formatted_lines.append(f"• {line}")
            i += 1
    
    # すべての行を表示
    result = '\n'.join(formatted_lines)
    
    return result


def format_cost_response(recipe_name: str, servings: int, ingredients: list, total_cost: float, missing: list) -> str:
    """
    原価計算結果をLINEメッセージ形式にフォーマット
    
    Args:
        recipe_name: 料理名
        servings: 何人前
        ingredients: 材料リスト（原価付き）
        total_cost: 合計原価
        missing: 未登録材料リスト
        
    Returns:
        フォーマットされたメッセージ
    """
    message = f"【{recipe_name}】\n"
    message += f"({servings}人前)\n\n"
    message += "【材料と原価】\n"
    
    for ing in ingredients:
        cost_str = f"¥{ing['cost']:.2f}" if ing['cost'] is not None else "未登録"
        message += f"・{ing['name']} {ing['quantity']}{ing['unit']} - {cost_str}\n"
    
    message += f"\n【合計原価】¥{total_cost:.2f}\n"
    message += f"【1人前原価】¥{total_cost/servings:.2f}\n"
    
    if missing:
        message += f"\n※未登録材料: {', '.join(missing)}"
    
    return message


def handle_follow_up_question(user_id, text):
    """文脈を考慮したフォローアップ質問を処理する"""
    state = get_user_state(user_id)

    if not state or state.get('last_action') != 'recipe_analysis':
        return None # フォローアップ対象外

    # タイムスタンプをチェック（5分以内）
    from dateutil.parser import isoparse
    try:
        timestamp_str = state.get('timestamp')
        if timestamp_str:
            timestamp = isoparse(timestamp_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=None)
            current_time = datetime.now()
            if current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)
            time_diff = current_time - timestamp
            if time_diff.total_seconds() > 300:
                return None
    except Exception as e:
        print(f"タイムスタンプ処理エラー: {e}")
        return None

    # LLMでユーザーの質問の意図を解釈
    intent = interpret_follow_up(text, state.get('recipe_name', ''))

    if intent and intent != 'other':
        # 意図に基づいて回答を生成
        return answer_follow_up(intent, state)
    
    return None

def interpret_follow_up(user_text, recipe_name):
    """Groq LLMを使って、ユーザーの質問の意図を解釈する"""
    try:
        prompt = f"""ユーザーは直前に「{recipe_name}」というレシピを解析しました。
ユーザーの次の質問「{user_text}」が、直前のレシピについて何を尋ねているか分類してください。

分類カテゴリ:
- 'total_cost': 合計原価について
- 'servings_cost': 1人前の原価について
- 'ingredients_list': 材料の一覧や内容について
- 'servings_number': 何人前かについて
- 'missing_ingredients': 原価計算できなかった材料について
- 'other': 上記以外、または無関係な質問

必ずカテゴリ名のみを小文字で回答してください。"""
        
        response = groq_parser.groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
        )
        intent = response.choices[0].message.content.strip().lower()
        print(f"フォローアップ意図解釈: {intent}")
        return intent
    except Exception as e:
        print(f"意図解釈エラー: {e}")
        return 'other'

def answer_follow_up(intent, state):
    """解釈された意図に基づいて回答を生成する"""
    recipe_name = state.get('recipe_name', 'そのレシピ')
    cost_result = state.get('cost_result', {})
    servings = state.get('servings', 1)
    servings = servings if servings > 0 else 1

    if intent == 'total_cost':
        total_cost = cost_result.get('total_cost', 0)
        return f"「{recipe_name}」の合計原価は、約{total_cost:.2f}円です。"

    elif intent == 'servings_cost':
        total_cost = cost_result.get('total_cost', 0)
        servings_cost = total_cost / servings
        return f"「{recipe_name}」の1人前の原価は、約{servings_cost:.2f}円です。"

    elif intent == 'ingredients_list':
        ingredients = cost_result.get('ingredients_with_cost', [])
        if not ingredients:
            return f"「{recipe_name}」の材料情報が見つかりませんでした。"
        
        message = f"【{recipe_name}の材料】\n"
        for ing in ingredients:
            cost_str = f"¥{ing['cost']:.2f}" if ing['cost'] is not None else "(未登録)"
            message += f"・{ing['name']} {ing['quantity']}{ing['unit']} - {cost_str}\n"
        return message

    elif intent == 'servings_number':
        return f"「{recipe_name}」は、{servings}人前のレシピとして解析されました。"

    elif intent == 'missing_ingredients':
        missing = cost_result.get('missing_ingredients', [])
        if not missing:
            return f"「{recipe_name}」の計算では、原価が不明な材料はありませんでした。"
        else:
            return f"「{recipe_name}」の計算で原価が不明だった材料は次の通りです：\n・{', '.join(missing)}"

    return None # No answer for this intent

# ===== LINE UI機能（条件付き） =====

def send_ingredient_add_menu(event):
    """材料追加メニューを送信（UI機能無効化中）"""
    reply_text = "材料追加機能は現在利用できません。代わりに以下の形式で追加してください：\n\n「追加 材料名 価格」\n例: 「追加 トマト 100円/個」"
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=reply_text)]
    ))

def send_ingredient_name_input(event):
    """材料名入力画面を送信（UI機能無効化中）"""
    reply_text = "材料名を直接入力してください\n例: トマト、玉ねぎ、豚肉など"
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=reply_text)]
    ))

def send_price_input(event, ingredient_name):
    """価格入力画面を送信（UI機能無効化中）"""
    reply_text = f"{ingredient_name}の価格を入力してください\n例: 100円/個、300円/100g、150円/1kgなど"
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=reply_text)]
    ))

def send_confirmation(event, ingredient_name, price):
    """確認画面を送信（UI機能無効化中）"""
    reply_text = f"以下の内容で材料を追加しますか？\n\n材料名: {ingredient_name}\n価格: {price}\n\n「はい」または「いいえ」で返信してください"
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[TextMessage(text=reply_text)]
    ))

@handler.add(PostbackEvent)
def handle_postback_event(event):
    """Postbackイベントの処理（レシピ確認・修正用）"""
    try:
        print(f"📱 Postbackイベント受信: {event.postback.data}")
        
        data = event.postback.data
        user_id = event.source.user_id
        
        if data.startswith("calculate_cost:"):
            # 原価計算を実行
            handle_calculate_cost_postback(event, user_id)
        elif data.startswith("edit_recipe:"):
            # 材料修正フォームを表示
            handle_edit_recipe_postback(event, user_id)
        elif data.startswith("save_recipe:"):
            # レシピをそのまま保存
            handle_save_recipe_postback(event, user_id)
        else:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="未対応の操作です。")]
            ))
        
    except Exception as e:
        print(f"❌ Postbackイベント処理エラー: {e}")
        import traceback
        traceback.print_exc()


def handle_calculate_cost_postback(event, user_id):
    """原価計算を実行するPostbackハンドラー"""
    try:
        # ユーザー状態からレシピデータを取得
        user_state = get_user_state(user_id)
        recipe_data = user_state.get('recipe_data')
        
        if not recipe_data:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="レシピデータが見つかりません。再度画像を送信してください。")]
            ))
            return
        
        # 原価計算を実行
        print(f"🔍 原価計算開始: {len(recipe_data['ingredients'])}個の材料")
        for i, ingredient in enumerate(recipe_data['ingredients']):
            print(f"  材料 {i}: {ingredient['name']} {ingredient['quantity']}{ingredient['unit']} (単価: {ingredient.get('unit_price', 'なし')})")
        
        cost_result = cost_calculator.calculate_recipe_cost(recipe_data['ingredients'])
        print(f"🔍 原価計算結果: 合計 {cost_result['total_cost']:.2f}円")
        
        # レシピをデータベースに保存または更新
        # user_stateにrecipe_idがあれば更新、なければ新規保存
        current_recipe_id = user_state.get('recipe_id')
        recipe_id = save_recipe_to_supabase(
            recipe_data['recipe_name'],
            recipe_data['servings'],
            cost_result['total_cost'],
            cost_result['ingredients_with_cost'], # cost_resultから材料リストを取得
            recipe_id=current_recipe_id
        )

        # 会話状態を更新
        new_state = {
            'last_action': 'cost_calculated',
            'recipe_data': recipe_data, # recipe_dataは更新されたもの
            'cost_result': cost_result,
            'recipe_id': recipe_id, # recipe_idを保存
            'timestamp': datetime.now().isoformat()
        }
        set_user_state(user_id, new_state)
        
        # 結果を表示
        response_message = format_cost_response(
            recipe_data['recipe_name'],
            recipe_data['servings'],
            cost_result['ingredients_with_cost'],
            cost_result['total_cost'],
            cost_result['missing_ingredients']
        )
        
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=response_message)]
        ))
        
    except Exception as e:
        print(f"❌ 原価計算エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="原価計算中にエラーが発生しました。")]
        ))


def handle_edit_recipe_postback(event, user_id):
    """材料修正フォームを表示するPostbackハンドラー"""
    try:
        # ユーザー状態からレシピデータを取得
        user_state = get_user_state(user_id)
        recipe_data = user_state.get('recipe_data')
        
        if not recipe_data:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="レシピデータが見つかりません。再度画像を送信してください。")]
            ))
            return
        
        # 修正用のフォームURLを生成
        form_url = url_for('edit_recipe_ingredients', user_id=user_id, _external=True)
        
        # 修正フォームへのリンクを送信
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"材料を修正するには、以下のリンクからフォームにアクセスしてください：\n\n{form_url}\n\nフォームで材料を修正後、LINEに戻ってレシピを登録できます。")]
        ))
        
    except Exception as e:
        print(f"❌ 修正フォーム表示エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="修正フォームの表示中にエラーが発生しました。")]
        ))


def handle_save_recipe_postback(event, user_id):
    """レシピをそのまま保存するPostbackハンドラー"""
    try:
        # ユーザー状態からレシピデータを取得
        user_state = get_user_state(user_id)
        recipe_data = user_state.get('recipe_data')
        
        if not recipe_data:
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="レシピデータが見つかりません。再度画像を送信してください。")]
            ))
            return
        
        # レシピをデータベースに保存
        current_recipe_id = user_state.get('recipe_id')
        recipe_id = save_recipe_to_supabase(
            recipe_data['recipe_name'],
            recipe_data['servings'],
            0,  # 原価計算なしの場合は0
            recipe_data['ingredients'],
            recipe_id=current_recipe_id
        )
        
        # 会話状態をクリア
        clear_user_state(user_id)
        
        # 保存完了メッセージ
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=f"✅ レシピを保存しました！\n\n料理名: {recipe_data['recipe_name']}\n人数: {recipe_data['servings']}人前\n\n材料数: {len(recipe_data['ingredients'])}種類\n\nレシピID: {recipe_id}")]
        ))
        
    except Exception as e:
        print(f"❌ レシピ保存エラー: {e}")
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="レシピの保存中にエラーが発生しました。")]
        ))


@app.route("/recipe/save_edited_ingredients", methods=['POST'])
def save_edited_ingredients():
    user_id = request.form.get('user_id')
    if not user_id:
        return "User ID not provided", 400

    user_state = get_user_state(user_id)
    if not user_state or 'recipe_data' not in user_state:
        return "Recipe data not found in session. Please send an image again.", 404

    try:
        # フォームから送信されたデータを取得
        print(f"🔍 フォームデータ受信開始...")
        edited_recipe_name = request.form.get('recipe_name', '')
        edited_servings = int(request.form.get('servings', 1))
        print(f"📝 レシピ名: {edited_recipe_name}, 人数: {edited_servings}")
        
        edited_ingredients = []
        # フォームデータは 'ingredients[0][name]', 'ingredients[0][quantity]' の形式で来る
        # これをパースしてリストに変換する
        i = 0
        while True:
            name_key = f'ingredients[{i}][name]'
            if name_key not in request.form:
                break
            
            try:
                name = request.form.get(name_key, '')
                quantity = float(request.form.get(f'ingredients[{i}][quantity]', 0))
                unit = request.form.get(f'ingredients[{i}][unit]', '')
                capacity = float(request.form.get(f'ingredients[{i}][capacity]', 1))
                capacity_unit = request.form.get(f'ingredients[{i}][capacity_unit]', '個')
                unit_price_str = request.form.get(f'ingredients[{i}][unit_price]', '')
                print(f"🔍 材料 {i}: unit_price_str = '{unit_price_str}'")
            except Exception as e:
                print(f"❌ 材料 {i} のフォームデータ取得エラー: {e}")
                i += 1
                continue
            
            unit_price = None
            if unit_price_str and unit_price_str.strip():
                try:
                    unit_price = float(unit_price_str.strip())
                    print(f"✅ 材料 {i}: unit_price = {unit_price}")
                except ValueError as e:
                    print(f"⚠️ 材料 {i}: 無効な単価 '{unit_price_str}' - {e}")
                    pass # 無効な単価は無視

            if name:
                edited_ingredients.append({
                    'name': name,
                    'quantity': quantity,
                    'unit': unit,
                    'capacity': capacity,
                    'capacity_unit': capacity_unit,
                    'unit_price': unit_price # 単価も追加
                })

                # 単価が入力されている場合、cost_masterを更新または登録
                if unit_price is not None:
                    cost_master_manager.add_or_update_cost(
                        ingredient_name=name,
                        capacity=capacity,
                        unit=unit,
                        unit_price=unit_price,
                        unit_column="" # フォームからの追加では使用しない
                    )
            i += 1

        # ユーザーセッションのレシピデータを更新
        user_state['recipe_data']['recipe_name'] = edited_recipe_name
        user_state['recipe_data']['servings'] = edited_servings
        user_state['recipe_data']['ingredients'] = edited_ingredients
        set_user_state(user_id, user_state)

        # 更新されたレシピデータでFlexMessageを作成してLINEに送信
        try:
            # 更新されたレシピデータを取得
            updated_recipe_data = user_state['recipe_data']
            
            # 更新されたFlexMessageを送信
            create_recipe_review_flex_message(updated_recipe_data, user_id)
            
            # 追加でテキストメッセージも送信
            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text="✅ レシピ材料を更新しました！更新された内容を確認してください。")]
            ))
        except Exception as line_e:
            print(f"❌ LINEプッシュメッセージ送信エラー: {line_e}")
            # LINEメッセージ送信失敗時でも、Webページは成功と表示
        
        # 成功メッセージを表示するシンプルなページをレンダリング
        return render_template('edit_success.html', user_id=user_id, success_message="レシピ材料を更新しました！LINEに戻って操作を続けてください。")

    except Exception as e:
        print(f"❌ 材料保存エラー: {e}")
        import traceback
        traceback.print_exc()
        return redirect(url_for('edit_recipe_ingredients', user_id=user_id, error_message=f"材料の保存中にエラーが発生しました: {str(e)}"))


@app.route("/recipes", methods=['GET'])
def view_recipes():
    try:
        # Supabaseからすべてのレシピを取得
        recipes_response = supabase.table('recipes').select('*').order('created_at', desc=True).execute()
        recipes_data = recipes_response.data

        # 各レシピの材料を取得
        for recipe in recipes_data:
            ingredients_response = supabase.table('ingredients').select('*').eq('recipe_id', recipe['id']).execute()
            recipe['ingredients'] = ingredients_response.data

        return render_template('view_recipes.html', recipes=recipes_data)

    except Exception as e:
        print(f"❌ レシピ一覧表示エラー: {e}")
        import traceback
        traceback.print_exc()
        return render_template('view_recipes.html', recipes=[], error_message=f"レシピの取得中にエラーが発生しました: {str(e)}")


@app.route("/recipe/<recipe_id>", methods=['GET'])
def view_recipe_detail(recipe_id):
    """レシピ詳細を表示"""
    try:
        # レシピ情報を取得
        recipe_response = supabase.table('recipes').select('*').eq('id', recipe_id).execute()
        
        if not recipe_response.data:
            return "レシピが見つかりません", 404
            
        recipe = recipe_response.data[0]
        
        # 材料情報を取得
        ingredients_response = supabase.table('ingredients').select('*').eq('recipe_id', recipe_id).order('ingredient_name').execute()
        ingredients = ingredients_response.data if ingredients_response.data else []
        
        return render_template('recipe_detail.html', recipe=recipe, ingredients=ingredients)

    except Exception as e:
        print(f"❌ レシピ詳細取得エラー: {e}")
        import traceback
        traceback.print_exc()
        return "レシピの取得に失敗しました", 500


@app.route("/api/update-ingredient-cost", methods=['POST'])
def update_ingredient_cost():
    """材料の原価を更新するAPI"""
    try:
        data = request.get_json()
        
        ingredient_id = data.get('ingredient_id')
        unit_price = data.get('unit_price')
        capacity = data.get('capacity', 1)
        capacity_unit = data.get('capacity_unit', '個')
        ingredient_name = data.get('ingredient_name')
        quantity = data.get('quantity')  # 新しい分量
        unit = data.get('unit')  # 新しい単位
        new_ingredient_name = data.get('ingredient_name')  # 新しい材料名
        
        # デバッグログ
        print(f"🔍 受信データ: quantity={quantity}, unit={unit}, unit_price={unit_price}, capacity={capacity}")
        
        if not ingredient_id or not unit_price or not ingredient_name:
            return jsonify({"success": False, "error": "必要なパラメータが不足しています"}), 400
        
        # ユーザー入力がない場合のみ既存の値を取得（空文字列も有効な入力として扱う）
        if quantity is None:
            ingredient_response = supabase.table('ingredients').select('quantity, unit').eq('id', ingredient_id).execute()
            
            if not ingredient_response.data:
                return jsonify({"success": False, "error": "材料が見つかりません"}), 404
            
            ingredient_data = ingredient_response.data[0]
            quantity = ingredient_data['quantity']
        
        if unit is None:
            if 'ingredient_response' not in locals():
                ingredient_response = supabase.table('ingredients').select('quantity, unit').eq('id', ingredient_id).execute()
                if ingredient_response.data:
                    ingredient_data = ingredient_response.data[0]
            unit = ingredient_data.get('unit', '')
        
        # 数値の検証（分量は文字列のまま保持、計算用にのみ数値変換）
        try:
            # 分量から数値と単位を抽出（より厳密な正規表現）
            quantity_match = re.match(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]*)$', str(quantity))
            if not quantity_match:
                return jsonify({"success": False, "error": "分量の形式が正しくありません"}), 400
            
            quantity_value = float(quantity_match.group(1))  # 計算用の数値
            quantity_unit = quantity_match.group(2) or unit  # 単位
            
            # デバッグログ
            print(f"🔍 正規表現解析: '{quantity}' → 数値:{quantity_value}, 単位:'{quantity_unit}'")
            
            unit_price = float(unit_price)
            capacity = float(capacity)
            
            # デバッグログ
            print(f"🔍 解析後: quantity_value={quantity_value}, quantity_unit={quantity_unit}")
            print(f"🔍 計算用: unit_price={unit_price}, capacity={capacity}")
        except (ValueError, TypeError) as e:
            print(f"❌ 数値変換エラー: {e}")
            return jsonify({"success": False, "error": f"数値の形式が正しくありません: {str(e)}"}), 400
        
        # 原価を計算 (単価 × 分量の数値 / 容量)
        cost = unit_price * quantity_value / capacity
        
        # 材料の原価、分量、単位、材料名を更新（ユーザー入力の値をそのまま使用）
        update_data = {
            'cost': cost,
            'quantity': quantity_value,  # 計算用の数値
            'unit': quantity_unit        # 抽出した単位
        }
        
        # 材料名が変更されている場合は更新
        if new_ingredient_name and new_ingredient_name != ingredient_name:
            update_data['ingredient_name'] = new_ingredient_name
            ingredient_name = new_ingredient_name
        
        supabase.table('ingredients').update(update_data).eq('id', ingredient_id).execute()
        
        # cost_masterに材料情報を追加/更新（ユーザー入力の値をそのまま使用）
        try:
            cost_master_manager.add_or_update_cost(
                ingredient_name=ingredient_name,
                capacity=capacity,
                unit=quantity_unit,
                unit_price=unit_price,
                unit_column=quantity_unit
            )
            print(f"✅ cost_masterに材料を追加/更新: {ingredient_name} ({quantity_value}{quantity_unit})")
        except Exception as e:
            print(f"⚠️ cost_master更新エラー: {e}")
            # cost_masterの更新に失敗しても材料の原価更新は続行
        
        # レシピの合計原価を再計算
        try:
            recipe_response = supabase.table('ingredients').select('recipe_id').eq('id', ingredient_id).execute()
            if recipe_response.data:
                recipe_id = recipe_response.data[0]['recipe_id']
                
                # レシピの全材料の原価を合計
                ingredients_response = supabase.table('ingredients').select('cost').eq('recipe_id', recipe_id).execute()
                total_cost = sum(float(ingredient.get('cost', 0)) if ingredient.get('cost') is not None else 0 for ingredient in ingredients_response.data)
                
                # レシピの合計原価を更新
                supabase.table('recipes').update({
                    'total_cost': total_cost
                }).eq('id', recipe_id).execute()
                
                print(f"✅ レシピの合計原価を更新: ¥{total_cost:.2f}")
        except Exception as e:
            print(f"⚠️ 合計原価計算エラー: {e}")
            # 合計原価計算に失敗しても材料更新は成功とする
        
        return jsonify({
            "success": True,
            "message": "原価を更新しました",
            "cost": cost,
            "quantity": quantity_value,
            "unit": quantity_unit
        })
        
    except Exception as e:
        print(f"❌ 原価更新エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"サーバーエラー: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Restart trigger

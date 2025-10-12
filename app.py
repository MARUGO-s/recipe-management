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
from flask import Flask, request, abort, render_template, jsonify, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage,
    TextSendMessage
)
from dotenv import load_dotenv
from azure_vision import AzureVisionAnalyzer
from groq_parser import GroqRecipeParser
from cost_calculator import CostCalculator
from cost_master_manager import CostMasterManager
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)

# LINE Bot設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Supabase設定
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# 各種サービスの初期化
azure_analyzer = AzureVisionAnalyzer()
groq_parser = GroqRecipeParser()
cost_calculator = CostCalculator()
cost_master_manager = CostMasterManager()

# 原価表の事前読み込み
try:
    cost_calculator.load_cost_master_from_storage()
except Exception as e:
    print(f"原価表の初期読み込みエラー: {e}")
    try:
        cost_calculator._load_cost_master_from_db()
    except Exception as e2:
        print(f"DBからの原価表読み込みもエラー: {e2}")


def extract_capacity_from_spec(spec_text, product_name=""):
    """
    規格や商品名から容量を抽出する関数
    
    Args:
        spec_text: 規格テキスト
        product_name: 商品名
    
    Returns:
        tuple: (capacity, unit)
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
        (r'(\d+(?:\.\d+)?)\s*個', lambda m: (float(m.group(1)), '個')),
        (r'(\d+(?:\.\d+)?)\s*本', lambda m: (float(m.group(1)), '個')),
        (r'(\d+(?:\.\d+)?)\s*枚', lambda m: (float(m.group(1)), '個')),
        # パック系
        (r'(\d+(?:\.\d+)?)\s*p', lambda m: (float(m.group(1)), '個')),
    ]
    
    # 規格から容量を抽出
    for pattern, converter in patterns:
        match = re.search(pattern, spec_cleaned, re.IGNORECASE)
        if match:
            return converter(match)
    
    # 商品名から容量を抽出（規格で見つからない場合）
    if product_name:
        for pattern, converter in patterns:
            match = re.search(pattern, product_name, re.IGNORECASE)
            if match:
                return converter(match)
    
    # デフォルト値
    return (1, '個')


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
        
        # CSVファイルの読み込みとデータベースへの保存
        csv_data = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        count = 0
        for row in csv_reader:
            try:
                # データの検証と変換
                ingredient_name = row.get('ingredient_name', '').strip()
                unit_price = row.get('unit_price', '').strip()
                
                if not ingredient_name or not unit_price:
                    continue
                
                # Supabaseにデータを挿入
                data = {
                    'ingredient_name': ingredient_name,
                    'capacity': float(row.get('capacity', 1)),
                    'unit': row.get('unit', '個').strip(),
                    'unit_price': float(unit_price),
                    'updated_at': datetime.now().isoformat()
                }
                supabase.table('cost_master').upsert(data).execute()
                count += 1
            except (ValueError, KeyError) as e:
                continue
        
        return jsonify({"success": True, "count": count})
    
    except Exception as e:
        return jsonify({"error": "アップロードに失敗しました"}), 500


@app.route("/admin/upload-transaction", methods=['POST'])
def admin_upload_transaction():
    """取引データCSVファイルのアップロード（材料情報抽出）"""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "ファイルが選択されていません"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "ファイルが選択されていません"}), 400
        
        if not file.filename.lower().endswith('.csv'):
            return jsonify({"error": "CSVファイルのみアップロード可能です"}), 400
        
        # CSVファイルの読み込み
        csv_data = file.read().decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # 列マッピング（デフォルト）
        column_mapping = {
            'supplier': '取引先名',
            'product': '商品名', 
            'price': '単価',
            'unit': '単位',
            'spec': '規格'
        }
        
        # 実際の列名を検出
        if csv_reader.fieldnames:
            detected_columns = {}
            for key, expected_name in column_mapping.items():
                for field in csv_reader.fieldnames:
                    if expected_name in field:
                        detected_columns[key] = field
                        break
            
            # 列が見つからない場合はフィールド名から推測
            if not detected_columns.get('supplier'):
                for field in csv_reader.fieldnames:
                    if '取引先' in field or '仕入先' in field:
                        detected_columns['supplier'] = field
                        break
            
            if not detected_columns.get('product'):
                for field in csv_reader.fieldnames:
                    if '商品名' in field or '品名' in field:
                        detected_columns['product'] = field
                        break
                        
            if not detected_columns.get('price'):
                for field in csv_reader.fieldnames:
                    if '単価' in field or '価格' in field:
                        detected_columns['price'] = field
                        break
                        
            if not detected_columns.get('unit'):
                for field in csv_reader.fieldnames:
                    if '単位' in field:
                        detected_columns['unit'] = field
                        break
            
            if not detected_columns.get('spec'):
                for field in csv_reader.fieldnames:
                    if '規格' in field:
                        detected_columns['spec'] = field
                        break
            
            column_mapping = detected_columns
        
        # データの抽出と変換
        extracted_materials = {}
        count = 0
        
        for row in csv_reader:
            try:
                # 必要な列が存在するかチェック
                if not all(key in column_mapping and column_mapping[key] in row for key in ['supplier', 'product', 'price']):
                    continue
                
                supplier = row[column_mapping['supplier']].strip()
                product = row[column_mapping['product']].strip()
                price_str = row[column_mapping['price']].strip()
                unit = row.get(column_mapping.get('unit', ''), '').strip() if column_mapping.get('unit') else '個'
                spec = row.get(column_mapping.get('spec', ''), '').strip() if column_mapping.get('spec') else ''
                
                if not product or not price_str:
                    continue
                
                # 単価を数値に変換
                try:
                    price = float(price_str.replace(',', ''))
                except ValueError:
                    continue
                
                # 材料名の正規化（取引先名を含める場合）
                material_name = f"{product}"
                if supplier and supplier != product:
                    material_name = f"{product}（{supplier}）"
                
                # 規格と商品名から容量を抽出
                extracted_capacity, extracted_unit = extract_capacity_from_spec(spec, product)
                
                # 抽出できた場合はそれを使用、できなかった場合は単位から推定
                if extracted_capacity > 1 or extracted_unit != '個':
                    capacity = extracted_capacity
                    unit = extracted_unit
                else:
                    # 従来の単位からの推定
                    capacity = 1
                    if unit:
                        if 'kg' in unit:
                            capacity = 1000
                            unit = 'g'
                        elif 'g' in unit:
                            capacity = 1
                        elif 'L' in unit or 'l' in unit:
                            capacity = 1000
                            unit = 'ml'
                        elif 'ml' in unit:
                            capacity = 1
                        elif '個' in unit or '本' in unit or '枚' in unit:
                            capacity = 1
                            unit = '個'
                
                # 重複チェック
                if material_name in extracted_materials:
                    # より安い価格で更新
                    if price < extracted_materials[material_name]['price']:
                        extracted_materials[material_name] = {
                            'name': material_name,
                            'capacity': capacity,
                            'unit': unit,
                            'price': price,
                            'supplier': supplier
                        }
                else:
                    extracted_materials[material_name] = {
                        'name': material_name,
                        'capacity': capacity,
                        'unit': unit,
                        'price': price,
                        'supplier': supplier
                    }
                
                count += 1
                
            except Exception as e:
                print(f"行処理エラー: {e}")
                continue
        
        # データベースに保存
        saved_count = 0
        for material_data in extracted_materials.values():
            try:
                result = supabase.table('cost_master').upsert({
                    'ingredient_name': material_data['name'],
                    'capacity': material_data['capacity'],
                    'unit': material_data['unit'],
                    'unit_price': material_data['price'],
                    'updated_at': datetime.now().isoformat()
                }).execute()
                saved_count += 1
            except Exception as e:
                print(f"保存エラー: {e}")
                continue
        
        return jsonify({
            "success": True, 
            "processed": count,
            "extracted": len(extracted_materials),
            "saved": saved_count,
            "column_mapping": column_mapping
        })
    
    except Exception as e:
        print(f"取引データアップロードエラー: {e}")
        return jsonify({"error": "取引データのアップロードに失敗しました"}), 500

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
                '単位': '個',
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
        cost_master_result = supabase.table('cost_master').select('*').order('ingredient_name').execute()
        
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

@app.route("/admin/clear", methods=['POST'])
def admin_clear():
    """データベース内容のクリア"""
    try:
        # 原価マスターのクリア
        supabase.table('cost_master').delete().neq('ingredient_name', '').execute()
        
        # レシピのクリア
        supabase.table('recipes').delete().neq('dish_name', '').execute()
        
        # 材料のクリア
        supabase.table('ingredients').delete().neq('ingredient_name', '').execute()
        
        return jsonify({"success": True, "message": "データベースをクリアしました"})
    
    except Exception as e:
        print(f"クリアエラー: {e}")
        return jsonify({"error": "データのクリアに失敗しました"}), 500

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


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """画像メッセージの処理"""
    try:
        # 画像の取得
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        
        # 画像データを取得
        image_bytes = b''
        for chunk in message_content.iter_content():
            image_bytes += chunk
        
        # ステップ1: Azure Visionで画像解析
        reply_message = "画像を受け取りました。解析中です..."
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message)
        )
        
        ocr_text = azure_analyzer.analyze_image_from_bytes(image_bytes)
        
        if not ocr_text:
            line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text="画像からテキストを抽出できませんでした。")
            )
            return
        
        print(f"OCR結果: {ocr_text}")
        
        # ステップ2: Groqでレシピ構造化
        recipe_data = groq_parser.parse_recipe_text(ocr_text)
        
        if not recipe_data:
            line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text="レシピ情報を解析できませんでした。")
            )
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
        
        # ステップ5: LINEで結果を返信
        response_message = format_cost_response(
            recipe_data['recipe_name'],
            recipe_data['servings'],
            cost_result['ingredients_with_cost'],
            cost_result['total_cost'],
            cost_result['missing_ingredients']
        )
        
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=response_message)
        )
        
    except Exception as e:
        print(f"エラー: {e}")
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=f"エラーが発生しました: {str(e)}")
        )


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    text = event.message.text.strip()
    
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

※原価表に登録されていない材料は計算されません"""
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=help_message)
        )
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
    
    # 材料名検索（その他のテキスト）
    # コマンド以外のテキストは材料名として検索
    handle_search_ingredient(event, text)


def handle_search_ingredient(event, search_term: str):
    """
    材料名検索の処理
    例: 「トマト」と入力すると関連する材料を検索
    """
    try:
        # 検索キーワードが短すぎる場合はスキップ
        if len(search_term) < 2:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="レシピの画像を送信するか、「ヘルプ」と入力してください。")
            )
            return
        
        # 材料名で検索
        results = cost_master_manager.search_costs(search_term, limit=5)
        
        if not results:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"「{search_term}」に一致する材料が見つかりませんでした。\n\n原価表に登録するには:\n「追加 {search_term} 価格/単位」と入力してください。")
            )
            return
        
        # 結果をフォーマット
        if len(results) == 1:
            # 完全一致または1件のみの場合
            cost = results[0]
            
            # 取引先名を抽出（材料名に「（取引先名）」が含まれている場合）
            ingredient_name = cost['ingredient_name']
            supplier = ""
            if "（" in ingredient_name and "）" in ingredient_name:
                parts = ingredient_name.split("（")
                ingredient_name = parts[0]
                supplier = parts[1].replace("）", "")
            
            response = f"""📋 {ingredient_name}

【容量】{cost['capacity']}{cost['unit']}
【単価】¥{cost['unit_price']:.2f}"""
            
            if supplier:
                response += f"\n【取引先】{supplier}"
            
            if cost.get('updated_at'):
                response += f"\n【更新日】{cost['updated_at'][:10]}"
        else:
            # 複数候補がある場合
            response = f"🔍 「{search_term}」の検索結果（{len(results)}件）\n\n"
            
            for i, cost in enumerate(results, 1):
                ingredient_name = cost['ingredient_name']
                supplier = ""
                if "（" in ingredient_name and "）" in ingredient_name:
                    parts = ingredient_name.split("（")
                    ingredient_name = parts[0]
                    supplier = f" ({parts[1].replace('）', '')})"
                
                response += f"{i}. {ingredient_name}{supplier}\n"
                response += f"   {cost['capacity']}{cost['unit']} = ¥{cost['unit_price']:.0f}\n\n"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
        
    except Exception as e:
        print(f"材料検索エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"検索中にエラーが発生しました: {str(e)}")
        )


def handle_add_cost_command(event, text: str):
    """
    原価追加コマンドの処理
    例: 「追加 トマト 100円/個」
    """
    try:
        # 「追加 」を除去
        cost_text = text.replace("追加 ", "").replace("追加　", "").strip()
        
        if not cost_text:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="原価情報を入力してください。\n例: 「追加 トマト 100円/個」")
            )
            return
        
        # Groqで解析
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="原価情報を解析中です...")
        )
        
        cost_data = cost_master_manager.parse_cost_text(cost_text)
        
        if not cost_data:
            line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text="原価情報の解析に失敗しました。\n形式を確認してください。\n例: 「トマト 100円/個」")
            )
            return
        
        # 原価表に追加
        success = cost_master_manager.add_or_update_cost(
            cost_data['ingredient_name'],
            cost_data['capacity'],
            cost_data['unit'],
            cost_data['unit_price']
        )
        
        if success:
            # 原価計算機のキャッシュも更新
            try:
                cost_calculator._load_cost_master_from_db()
            except:
                pass
            
            response = f"""✅ 原価表に登録しました

【材料名】{cost_data['ingredient_name']}
【容量】{cost_data['capacity']}{cost_data['unit']}
【単価】¥{cost_data['unit_price']:.2f}"""
            
            line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text=response)
            )
        else:
            line_bot_api.push_message(
                event.source.user_id,
                TextSendMessage(text="原価表への登録に失敗しました。")
            )
            
    except Exception as e:
        print(f"原価追加エラー: {e}")
        line_bot_api.push_message(
            event.source.user_id,
            TextSendMessage(text=f"エラーが発生しました: {str(e)}")
        )


def handle_check_cost_command(event, text: str):
    """
    原価確認コマンドの処理
    例: 「確認 トマト」
    """
    try:
        # 「確認 」を除去
        ingredient_name = text.replace("確認 ", "").replace("確認　", "").strip()
        
        if not ingredient_name:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="材料名を入力してください。\n例: 「確認 トマト」")
            )
            return
        
        # 原価表から取得
        cost_info = cost_master_manager.get_cost_info(ingredient_name)
        
        if cost_info:
            response = f"""📋 原価情報

【材料名】{cost_info['ingredient_name']}
【容量】{cost_info['capacity']}{cost_info['unit']}
【単価】¥{cost_info['unit_price']:.2f}
【更新日】{cost_info.get('updated_at', 'N/A')}"""
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response)
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"「{ingredient_name}」は原価表に登録されていません。")
            )
            
    except Exception as e:
        print(f"原価確認エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"エラーが発生しました: {str(e)}")
        )


def handle_delete_cost_command(event, text: str):
    """
    原価削除コマンドの処理
    例: 「削除 トマト」
    """
    try:
        # 「削除 」を除去
        ingredient_name = text.replace("削除 ", "").replace("削除　", "").strip()
        
        if not ingredient_name:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="材料名を入力してください。\n例: 「削除 トマト」")
            )
            return
        
        # 削除前に確認
        cost_info = cost_master_manager.get_cost_info(ingredient_name)
        
        if not cost_info:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"「{ingredient_name}」は原価表に登録されていません。")
            )
            return
        
        # 削除実行
        success = cost_master_manager.delete_cost(ingredient_name)
        
        if success:
            # 原価計算機のキャッシュも更新
            try:
                cost_calculator._load_cost_master_from_db()
            except:
                pass
            
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ 「{ingredient_name}」を原価表から削除しました。")
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="削除に失敗しました。")
            )
            
    except Exception as e:
        print(f"原価削除エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"エラーが発生しました: {str(e)}")
        )


def handle_list_cost_command(event):
    """
    原価一覧コマンドの処理
    """
    try:
        costs = cost_master_manager.list_all_costs(limit=30)
        
        if not costs:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="原価表に登録されている材料はありません。")
            )
            return
        
        # 一覧をフォーマット
        response = f"📋 原価一覧（{len(costs)}件）\n\n"
        
        for i, cost in enumerate(costs, 1):
            response += f"{i}. {cost['ingredient_name']}\n"
            response += f"   {cost['capacity']}{cost['unit']} = ¥{cost['unit_price']:.0f}\n"
            
            if i >= 20:  # LINEメッセージの長さ制限対策
                response += f"\n... 他{len(costs) - 20}件"
                break
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=response)
        )
        
    except Exception as e:
        print(f"原価一覧エラー: {e}")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"エラーが発生しました: {str(e)}")
        )


def save_recipe_to_supabase(recipe_name: str, servings: int, total_cost: float, ingredients: list) -> str:
    """
    レシピをSupabaseに保存
    
    Args:
        recipe_name: 料理名
        servings: 何人前
        total_cost: 合計原価
        ingredients: 材料リスト（原価付き）
        
    Returns:
        保存されたレシピのID
    """
    # レシピテーブルに保存
    recipe_data = {
        'recipe_name': recipe_name,
        'servings': servings,
        'total_cost': total_cost
    }
    
    recipe_response = supabase.table('recipes').insert(recipe_data).execute()
    recipe_id = recipe_response.data[0]['id']
    
    # 材料テーブルに保存
    for ingredient in ingredients:
        ingredient_data = {
            'recipe_id': recipe_id,
            'ingredient_name': ingredient['name'],
            'quantity': ingredient['quantity'],
            'unit': ingredient['unit'],
            'cost': ingredient['cost'],
            'capacity': ingredient.get('capacity', 1),
            'capacity_unit': ingredient.get('capacity_unit', '個')
        }
        supabase.table('ingredients').insert(ingredient_data).execute()
    
    print(f"レシピを保存しました: {recipe_id}")
    return recipe_id


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


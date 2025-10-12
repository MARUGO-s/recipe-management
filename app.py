"""
LINE Bot メインアプリケーション（Render用）
LINE → Azure Vision → Groq → Supabase → LINE の一連のフロー
"""
import os
import requests
from flask import Flask, request, abort
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

💰 原価表の管理:
・追加: 「追加 材料名 価格/単位」
  例: 「追加 トマト 100円/個」
  例: 「追加 豚肉 300円/100g」
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
    
    # その他のテキスト
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="レシピの画像を送信するか、「ヘルプ」と入力してください。")
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
            cost_data['unit_price'],
            cost_data['reference_unit'],
            cost_data['reference_quantity']
        )
        
        if success:
            # 原価計算機のキャッシュも更新
            try:
                cost_calculator._load_cost_master_from_db()
            except:
                pass
            
            response = f"""✅ 原価表に登録しました

【材料名】{cost_data['ingredient_name']}
【単価】¥{cost_data['unit_price']:.2f}
【基準】{cost_data['reference_quantity']}{cost_data['reference_unit']}あたり"""
            
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
【単価】¥{cost_info['unit_price']:.2f}
【基準】{cost_info['reference_quantity']}{cost_info['reference_unit']}あたり
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
            response += f"   ¥{cost['unit_price']:.0f}/{cost['reference_quantity']}{cost['reference_unit']}\n"
            
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
            'cost': ingredient['cost']
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


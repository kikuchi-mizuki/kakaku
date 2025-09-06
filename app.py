from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, FlexSendMessage
import logging
import os
from datetime import datetime

from config import Config
from services.line_service import LineService
from services.ocr_service import OCRService
from services.bill_processor import BillProcessor
from services.plan_selector import PlanSelector
from services.cost_comparator import CostComparator
from utils.logger import setup_logger

app = Flask(__name__)
app.config.from_object(Config)

# ログ設定
logger = setup_logger(__name__)

# 設定の検証
config_valid = False
try:
    config_valid = Config.validate_required_config()
    if config_valid:
        logger.info("Configuration validation passed")
    else:
        logger.warning("Configuration validation failed - running in development mode")
except ValueError as e:
    logger.error(f"Configuration error: {str(e)}")
    raise

# LINE Bot API（設定が有効な場合のみ初期化）
if config_valid and Config.LINE_CHANNEL_ACCESS_TOKEN and Config.LINE_CHANNEL_SECRET:
    line_bot_api = LineBotApi(Config.LINE_CHANNEL_ACCESS_TOKEN)
    handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
else:
    # 開発環境用のダミー初期化
    line_bot_api = None
    handler = None
    logger.warning("LINE Bot API not initialized - missing configuration")

# サービス初期化
line_service = LineService(line_bot_api)
ocr_service = OCRService()
bill_processor = BillProcessor()
plan_selector = PlanSelector()
cost_comparator = CostComparator()

@app.route('/')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'kakaku-line-bot'
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    if not handler:
        logger.error("LINE Bot handler not initialized - check configuration")
        return jsonify({'error': 'Bot not configured'}), 500
    
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return jsonify({'error': 'Invalid signature'}), 400
    
    return jsonify({'status': 'OK'})

def handle_image_message(event):
    """画像メッセージの処理"""
    if not line_bot_api:
        logger.error("LINE Bot API not initialized - cannot process image")
        return
    
    try:
        logger.info(f"Received image message from user: {event.source.user_id}")
        
        # 画像をダウンロード
        message_content = line_bot_api.get_message_content(event.message.id)
        image_data = message_content.content
        
        # 一時的に画像を保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = f"temp_image_{timestamp}.jpg"
        
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        # 処理開始の応答
        line_service.send_processing_message(event.reply_token)
        
        # 非同期で処理を実行
        process_bill_async(event, image_path)
        
    except Exception as e:
        logger.error(f"Error handling image message: {str(e)}")
        line_service.send_error_message(event.reply_token)

def process_bill_async(event, image_path):
    """請求書の非同期処理"""
    try:
        # OCR実行
        ocr_result = ocr_service.extract_text(image_path)
        
        # 請求書解析
        bill_data = bill_processor.process_bill(ocr_result)
        
        # プラン選定
        recommended_plan = plan_selector.select_plan(bill_data)
        
        # 料金比較
        comparison_result = cost_comparator.compare_costs(
            current_cost=bill_data['total_cost'],
            recommended_plan=recommended_plan
        )
        
        # 結果をLINEで送信
        line_service.send_analysis_result(
            event.reply_token,
            bill_data,
            recommended_plan,
            comparison_result
        )
        
    except Exception as e:
        logger.error(f"Error processing bill: {str(e)}")
        line_service.send_error_message(event.reply_token)
    
    finally:
        # 一時ファイルを削除
        if os.path.exists(image_path):
            os.remove(image_path)

def handle_text_message(event):
    """テキストメッセージの処理"""
    if not line_service:
        logger.error("LINE service not initialized - cannot process text message")
        return
    
    text = event.message.text
    
    if text == "ヘルプ" or text == "help":
        help_message = """
📱 携帯料金診断Bot

使い方：
1. 携帯料金明細の画像を送信してください
2. 自動で回線費用を解析し、おすすめプランを提案します

対応形式：
- JPEG/PNG画像
- PDF（1-10ページ）

注意事項：
- 端末代金は除外されます
- 家族まとめ明細にも対応
- 個人情報は適切に保護されます
        """
        line_service.send_text_message(event.reply_token, help_message)
    else:
        line_service.send_text_message(
            event.reply_token,
            "画像を送信して携帯料金を診断してください。ヘルプが欲しい場合は「ヘルプ」と送信してください。"
        )

# ハンドラーの登録（設定が有効な場合のみ）
if handler:
    handler.add(MessageEvent, message=ImageMessage)(handle_image_message)
    handler.add(MessageEvent, message=TextMessage)(handle_text_message)

if __name__ == '__main__':
    # アップロードフォルダを作成
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    
    app.run(debug=Config.FLASK_ENV == 'development', host='0.0.0.0', port=5000)

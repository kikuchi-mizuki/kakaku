from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, FlexSendMessage, TextSendMessage
import logging
import os
from datetime import datetime
from functools import wraps

from config import Config
from services.line_service import LineService
from services.ocr_service import OCRService
from services.bill_processor import BillProcessor
from services.plan_selector import PlanSelector
from services.cost_comparator import CostComparator
from services.ai_diagnosis_service import AIDiagnosisService
from utils.logger import setup_logger

# 二重ゲート保険（下流処理にも信頼度チェック）
def require_reliable(fn):
    """信頼度チェックデコレータ"""
    @wraps(fn)
    def wrap(*args, **kw):
        analysis_data = kw.get("analysis_data") or (len(args) >= 1 and args[-1])
        if isinstance(analysis_data, dict) and (not analysis_data.get("reliable") or analysis_data.get("confidence", 0) < 0.8):
            raise RuntimeError("unreliable_result_blocked")
        return fn(*args, **kw)
    return wrap

app = Flask(__name__)
app.config.from_object(Config)

# ログ設定
logger = setup_logger(__name__)

# アプリケーション起動ログ
logger.info("=" * 50)
logger.info("🚀 LINE Bot Application Starting...")
logger.info(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info("=" * 50)

# 設定の検証
config_valid = False
try:
    config_valid = Config.validate_required_config()
    if config_valid:
        logger.info("✅ Configuration validation passed")
    else:
        logger.warning("⚠️ Configuration validation failed - running in development mode")
except ValueError as e:
    logger.error(f"❌ Configuration error: {str(e)}")
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
logger.info("🔧 Initializing services...")
line_service = LineService(line_bot_api)
logger.info("✅ LineService initialized")
ocr_service = OCRService()
logger.info("✅ OCRService initialized")
bill_processor = BillProcessor()
logger.info("✅ BillProcessor initialized")
plan_selector = PlanSelector()
logger.info("✅ PlanSelector initialized")
cost_comparator = CostComparator()
logger.info("✅ CostComparator initialized")
ai_diagnosis_service = AIDiagnosisService()
logger.info("✅ AIDiagnosisService initialized")
logger.info("🎉 All services initialized successfully!")

@app.route('/')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'kakaku-line-bot'
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("📨 Webhook request received")
    
    if not handler:
        logger.error("❌ LINE Bot handler not initialized - check configuration")
        return jsonify({'error': 'Bot not configured'}), 500
    
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    logger.info(f"📝 Request body length: {len(body)} characters")
    
    try:
        handler.handle(body, signature)
        logger.info("✅ Webhook handled successfully")
    except InvalidSignatureError:
        logger.error("❌ Invalid signature")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        logger.error(f"❌ Webhook error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
    return jsonify({'status': 'OK'})

@app.route('/callback', methods=['POST'])
def callback():
    """LINE Developers Console用のcallbackエンドポイント（/webhookと同じ処理）"""
    return webhook()

def handle_image_message(event):
    """画像メッセージの処理"""
    logger.info("🖼️ Image message received")
    
    if not line_bot_api:
        logger.error("❌ LINE Bot API not initialized - cannot process image")
        return
    
    try:
        user_id = event.source.user_id
        logger.info(f"👤 Processing image from user: {user_id}")
        
        # 画像をダウンロード
        logger.info("📥 Downloading image...")
        message_content = line_bot_api.get_message_content(event.message.id)
        image_data = message_content.content
        logger.info(f"📊 Image size: {len(image_data)} bytes")
        
        # 一時的に画像を保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        image_path = f"temp_image_{timestamp}.jpg"
        logger.info(f"💾 Saving image to: {image_path}")
        
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        logger.info("✅ Image saved successfully")
        
        # 非同期で処理を実行（reply_tokenは処理完了後に使用）
        logger.info("🚀 Starting async bill processing...")
        process_bill_async(event, image_path)
        
    except Exception as e:
        logger.error(f"❌ Error handling image message: {str(e)}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        # reply_tokenが既に使用されている可能性があるため、エラーログのみ
        logger.error("⚠️ Could not send error message - reply token may be invalid")

def process_bill_async(event, image_path):
    """請求書の非同期処理"""
    logger.info("🔄 Starting bill processing...")
    
    try:
        # 処理開始の応答
        logger.info("📤 Sending processing message...")
        line_service.send_processing_message(event.reply_token)
        
        # OCR実行
        logger.info("🔍 Running OCR...")
        ocr_result = ocr_service.extract_text(image_path)
        logger.info(f"📝 OCR completed: {len(ocr_result['text'])} characters extracted")
        
        # AI診断による詳細分析
        logger.info("🤖 Running AI diagnosis...")
        analysis_data = ai_diagnosis_service.analyze_bill_with_ai(ocr_text=ocr_result['text'], image_path=image_path)
        logger.info(f"🧠 AI diagnosis completed: {analysis_data.get('carrier', 'Unknown')} - ¥{analysis_data.get('line_cost', 0):,}")
        
        # 低信頼度の場合は後続処理をスキップし、案内のみ送信
        if not analysis_data.get('reliable', False):
            logger.warning("⛔ Analysis marked as unreliable. Skipping plan selection and cost comparison.")
            try:
                if line_bot_api:
                    details = analysis_data.get('analysis_details') or [
                        '【分析結果】',
                        '明細の合計が特定できませんでした。',
                        '',
                        '【推奨対応】',
                        '1. 画像の鮮明度を確認してください',
                        '2. 請求書全体が写るように撮影してください',
                        '3. 光の反射や影を避けて撮影してください',
                        '4. より鮮明な画像で再試行してください'
                    ]
                    line_bot_api.push_message(event.source.user_id, TextSendMessage(text="\n".join(details)))
                    logger.info("Sent low-confidence guidance message to user")
            except Exception as e:
                logger.error(f"Error sending low-confidence message: {str(e)}")
            return
        
        # 請求書解析（AI診断結果を使用）
        logger.info("📊 Processing bill data...")
        bill_data = bill_processor.process_bill(ocr_result)
        bill_data.update(analysis_data)  # AI診断結果を統合
        logger.info(f"💰 Bill data processed: Total cost ¥{bill_data.get('total_cost', 0):,}")
        
        # プラン選定
        logger.info("🎯 Selecting recommended plan...")
        recommended_plan = plan_selector.select_plan(bill_data)
        logger.info(f"📱 Recommended plan: {recommended_plan['name']} - ¥{recommended_plan['monthly_cost']:,}")
        
        # 料金比較（AI診断データを含む）
        logger.info("⚖️ Comparing costs...")
        comparison_result = cost_comparator.compare_costs(
            current_cost=bill_data['total_cost'],
            recommended_plan=recommended_plan,
            analysis_data=analysis_data
        )
        logger.info(f"💸 Monthly saving: ¥{comparison_result.get('monthly_saving', 0):,}")
        
        # 結果をLINEで送信（プッシュメッセージとして送信）
        logger.info("📨 Sending results to user...")
        send_push_message(event.source.user_id, bill_data, recommended_plan, comparison_result, analysis_data)
        logger.info("✅ Bill processing completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error processing bill: {str(e)}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        # プッシュメッセージでエラーを送信
        send_push_error_message(event.source.user_id)
    
    finally:
        # 一時ファイルを削除
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"🗑️ Cleaned up temporary file: {image_path}")

@require_reliable
def send_push_message(user_id: str, bill_data: dict, recommended_plan: dict, comparison_result: dict, analysis_data: dict = None):
    """プッシュメッセージで解析結果を送信（AI診断対応）"""
    try:
        if line_bot_api:
            # シンプルな結論メッセージ
            conclusion_message = line_service._create_simple_conclusion_message(bill_data, recommended_plan, comparison_result)
            
            # 詳細分析メッセージ（テキスト）
            detailed_analysis = line_service._create_detailed_analysis_message(bill_data, recommended_plan, comparison_result, analysis_data)
            
            # メイン結果のFlex Message
            main_result = line_service._create_enhanced_main_result_flex(bill_data, recommended_plan, comparison_result, analysis_data)
            
            # 詳細結果のFlex Message
            detail_result = line_service._create_enhanced_detail_result_flex(bill_data, recommended_plan, comparison_result, analysis_data)
            
            # プッシュメッセージを送信
            line_bot_api.push_message(user_id, [conclusion_message, detailed_analysis, main_result, detail_result])
            logger.info(f"Push message sent to user: {user_id}")
    except Exception as e:
        logger.error(f"Error sending push message: {str(e)}")

def send_push_error_message(user_id: str):
    """プッシュメッセージでエラーを送信"""
    try:
        if line_bot_api:
            message = TextSendMessage(
                text="❌ 申し訳ございません。\n\n明細の解析中にエラーが発生しました。\n\nもう一度画像を送信するか、ヘルプと送信してください。"
            )
            line_bot_api.push_message(user_id, message)
            logger.info(f"Push error message sent to user: {user_id}")
    except Exception as e:
        logger.error(f"Error sending push error message: {str(e)}")

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
    
    logger.info("🌐 Starting Flask application...")
    logger.info(f"🔧 Debug mode: {Config.FLASK_ENV == 'development'}")
    logger.info(f"🌍 Host: 0.0.0.0, Port: 8080")
    logger.info("🚀 Application is ready to receive requests!")
    
    app.run(debug=Config.FLASK_ENV == 'development', host='0.0.0.0', port=8080)

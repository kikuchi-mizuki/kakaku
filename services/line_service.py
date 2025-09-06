from linebot import LineBotApi
from linebot.models import TextSendMessage, FlexSendMessage, BubbleContainer, BoxComponent, TextComponent, ButtonComponent, URIAction
from linebot.exceptions import LineBotApiError
from config import Config
import logging

logger = logging.getLogger(__name__)

class LineService:
    def __init__(self, line_bot_api: LineBotApi):
        self.line_bot_api = line_bot_api
    
    def send_text_message(self, reply_token: str, text: str):
        """テキストメッセージを送信"""
        try:
            message = TextSendMessage(text=text)
            self.line_bot_api.reply_message(reply_token, message)
        except LineBotApiError as e:
            if "Invalid reply token" in str(e):
                logger.warning("Invalid reply token - message may have already been sent")
            else:
                logger.error(f"LINE Bot API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending text message: {str(e)}")
    
    def send_processing_message(self, reply_token: str):
        """処理中メッセージを送信"""
        try:
            message = TextSendMessage(
                text="📱 携帯料金明細を解析中です...\n\nしばらくお待ちください。"
            )
            self.line_bot_api.reply_message(reply_token, message)
        except LineBotApiError as e:
            if "Invalid reply token" in str(e):
                logger.warning("Invalid reply token - processing message may have already been sent")
            else:
                logger.error(f"LINE Bot API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending processing message: {str(e)}")
    
    def send_error_message(self, reply_token: str):
        """エラーメッセージを送信"""
        try:
            message = TextSendMessage(
                text="❌ 申し訳ございません。\n\n明細の解析中にエラーが発生しました。\n\nもう一度画像を送信するか、ヘルプと送信してください。"
            )
            self.line_bot_api.reply_message(reply_token, message)
        except LineBotApiError as e:
            if "Invalid reply token" in str(e):
                logger.warning("Invalid reply token - error message may have already been sent")
            else:
                logger.error(f"LINE Bot API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    
    def send_analysis_result(self, reply_token: str, bill_data: dict, recommended_plan: dict, comparison_result: dict):
        """解析結果をFlex Messageで送信"""
        try:
            # メイン結果のFlex Message
            main_result = self._create_main_result_flex(bill_data, recommended_plan, comparison_result)
            
            # 詳細結果のFlex Message
            detail_result = self._create_detail_result_flex(bill_data, recommended_plan, comparison_result)
            
            # メッセージを送信
            self.line_bot_api.reply_message(reply_token, [main_result, detail_result])
            
        except LineBotApiError as e:
            if "Invalid reply token" in str(e):
                logger.warning("Invalid reply token - analysis result may have already been sent")
            else:
                logger.error(f"LINE Bot API error: {str(e)}")
                self.send_error_message(reply_token)
        except Exception as e:
            logger.error(f"Error sending analysis result: {str(e)}")
            self.send_error_message(reply_token)
    
    def _create_main_result_flex(self, bill_data: dict, recommended_plan: dict, comparison_result: dict) -> FlexSendMessage:
        """メイン結果のFlex Messageを作成"""
        
        # 現在の費用
        current_cost = f"¥{bill_data['total_cost']:,}"
        
        # おすすめプラン
        plan_name = recommended_plan['name']
        plan_cost = f"¥{recommended_plan['monthly_cost']:,}"
        
        # 差額
        monthly_saving = comparison_result['monthly_saving']
        yearly_saving = comparison_result['yearly_saving']
        
        saving_text = f"月額¥{monthly_saving:,}節約"
        if monthly_saving > 0:
            saving_text += f"\n年間¥{yearly_saving:,}節約"
        else:
            saving_text = f"月額¥{abs(monthly_saving):,}増加"
        
        bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="📱 携帯料金診断結果",
                        weight="bold",
                        size="xl",
                        color="#1DB446"
                    ),
                    BoxComponent(
                        layout="vertical",
                        margin="lg",
                        spacing="sm",
                        contents=[
                            BoxComponent(
                                layout="baseline",
                                spacing="sm",
                                contents=[
                                    TextComponent(
                                        text="現在の回線費用",
                                        color="#666666",
                                        size="sm",
                                        flex=0
                                    ),
                                    TextComponent(
                                        text=current_cost,
                                        wrap=True,
                                        color="#666666",
                                        size="sm",
                                        align="end"
                                    )
                                ]
                            ),
                            BoxComponent(
                                layout="baseline",
                                spacing="sm",
                                contents=[
                                    TextComponent(
                                        text="おすすめプラン",
                                        color="#666666",
                                        size="sm",
                                        flex=0
                                    ),
                                    TextComponent(
                                        text=f"{plan_name} {plan_cost}",
                                        wrap=True,
                                        color="#666666",
                                        size="sm",
                                        align="end"
                                    )
                                ]
                            ),
                            BoxComponent(
                                layout="baseline",
                                spacing="sm",
                                contents=[
                                    TextComponent(
                                        text="差額",
                                        color="#666666",
                                        size="sm",
                                        flex=0
                                    ),
                                    TextComponent(
                                        text=saving_text,
                                        wrap=True,
                                        color="#1DB446" if monthly_saving > 0 else "#FF6B6B",
                                        size="sm",
                                        align="end",
                                        weight="bold"
                                    )
                                ]
                            )
                        ]
                    )
                ]
            ),
            footer=BoxComponent(
                layout="vertical",
                spacing="sm",
                contents=[
                    ButtonComponent(
                        style="primary",
                        color="#1DB446",
                        action=URIAction(
                            label="回線切り替えはこちら",
                            uri=Config.DMOBILE_SWITCH_URL
                        )
                    ),
                    ButtonComponent(
                        style="secondary",
                        action=URIAction(
                            label="回線を獲得したい方はこちら",
                            uri=Config.DMOBILE_ACQUIRE_URL
                        )
                    )
                ]
            )
        )
        
        return FlexSendMessage(alt_text="携帯料金診断結果", contents=bubble)
    
    def _create_detail_result_flex(self, bill_data: dict, recommended_plan: dict, comparison_result: dict) -> FlexSendMessage:
        """詳細結果のFlex Messageを作成"""
        
        # 50年累積損失
        total_50year = comparison_result['total_50year']
        total_50year_text = f"¥{abs(total_50year):,}" if total_50year < 0 else f"¥{total_50year:,}"
        
        # その金額でできること
        examples = comparison_result.get('examples', {})
        
        bubble = BubbleContainer(
            body=BoxComponent(
                layout="vertical",
                contents=[
                    TextComponent(
                        text="📊 詳細分析",
                        weight="bold",
                        size="xl",
                        color="#1DB446"
                    ),
                    BoxComponent(
                        layout="vertical",
                        margin="lg",
                        spacing="sm",
                        contents=[
                            BoxComponent(
                                layout="baseline",
                                spacing="sm",
                                contents=[
                                    TextComponent(
                                        text="50年累積差額",
                                        color="#666666",
                                        size="sm",
                                        flex=0
                                    ),
                                    TextComponent(
                                        text=total_50year_text,
                                        wrap=True,
                                        color="#FF6B6B" if total_50year < 0 else "#1DB446",
                                        size="sm",
                                        align="end",
                                        weight="bold"
                                    )
                                ]
                            )
                        ]
                    ),
                    BoxComponent(
                        layout="vertical",
                        margin="lg",
                        spacing="sm",
                        contents=[
                            TextComponent(
                                text="💰 その金額でできること",
                                weight="bold",
                                size="md",
                                color="#1DB446"
                            ),
                            TextComponent(
                                text=f"• 年間: {examples.get('yearly', 'N/A')}\n• 10年: {examples.get('10year', 'N/A')}\n• 50年: {examples.get('50year', 'N/A')}",
                                wrap=True,
                                color="#666666",
                                size="sm"
                            )
                        ]
                    ),
                    BoxComponent(
                        layout="vertical",
                        margin="lg",
                        spacing="sm",
                        contents=[
                            TextComponent(
                                text="✨ dモバイルのメリット",
                                weight="bold",
                                size="md",
                                color="#1DB446"
                            ),
                            TextComponent(
                                text="• docomo回線で安定した通信\n• 毎日リセット型容量\n• かけ放題オプション充実",
                                wrap=True,
                                color="#666666",
                                size="sm"
                            )
                        ]
                    )
                ]
            )
        )
        
        return FlexSendMessage(alt_text="詳細分析結果", contents=bubble)

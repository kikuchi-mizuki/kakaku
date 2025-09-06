import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    
    @classmethod
    def validate_required_config(cls):
        """必須設定の検証"""
        # 開発環境では警告のみ、本番環境ではエラー
        is_development = cls.FLASK_ENV == 'development'
        
        required_vars = {
            'LINE_CHANNEL_ACCESS_TOKEN': cls.LINE_CHANNEL_ACCESS_TOKEN,
            'LINE_CHANNEL_SECRET': cls.LINE_CHANNEL_SECRET,
        }
        
        missing_vars = []
        for var_name, var_value in required_vars.items():
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            if is_development:
                print(f"WARNING: {error_msg}")
                print("Please set these variables in your .env file")
                return False
            else:
                raise ValueError(error_msg)
        
        return True
    
    # Google Cloud Vision API
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # アプリケーション設定
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # dモバイルアフィリエイトリンク
    DMOBILE_SWITCH_URL = os.getenv('DMOBILE_SWITCH_URL', 'https://mypage.dmobile.jp/DJP249422?openExternalBrowser=1')
    DMOBILE_ACQUIRE_URL = os.getenv('DMOBILE_ACQUIRE_URL', 'https://mypage.dmobile.jp/CJP249422')
    
    # 画像保存設定
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    
    # ログ設定
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ENABLE_FILE_LOGGING = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
    
    # AI診断設定
    AI_DIAGNOSIS_ENABLED = os.getenv('AI_DIAGNOSIS_ENABLED', 'true').lower() == 'true'
    AI_CONFIDENCE_THRESHOLD = float(os.getenv('AI_CONFIDENCE_THRESHOLD', '0.7'))
    
    # OpenAI API設定（オプション）
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    USE_OPENAI_ANALYSIS = os.getenv('USE_OPENAI_ANALYSIS', 'false').lower() == 'true'
    
    # プラン選定設定
    EXCLUDE_S_PLAN = os.getenv('EXCLUDE_S_PLAN', 'true').lower() == 'true'
    ENABLE_24H_UNLIMITED = os.getenv('ENABLE_24H_UNLIMITED', 'true').lower() == 'true'
    
    # 料金比較設定
    SHOW_50YEAR_ANALYSIS = os.getenv('SHOW_50YEAR_ANALYSIS', 'true').lower() == 'true'
    SHOW_DMOBILE_BENEFITS = os.getenv('SHOW_DMOBILE_BENEFITS', 'true').lower() == 'true'

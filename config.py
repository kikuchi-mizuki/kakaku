import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    
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

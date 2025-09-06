import logging
import sys
import os
from datetime import datetime

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """ログ設定をセットアップ"""
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 既存のハンドラーをクリア
    logger.handlers.clear()
    
    # フォーマッター
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # ファイルハンドラー（本番環境用、環境変数で制御可能）
    enable_file_logging = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
    if level.upper() != "DEBUG" and enable_file_logging:
        try:
            # logsディレクトリが存在しない場合は作成
            logs_dir = 'logs'
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir, exist_ok=True)
            
            log_file_path = f'{logs_dir}/app_{datetime.now().strftime("%Y%m%d")}.log'
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # ファイルログが作成できない場合はコンソールログのみで続行
            logger.warning(f"Could not create file handler: {str(e)}")
    
    return logger

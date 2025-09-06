import os
import hashlib
import logging
import shutil
from datetime import datetime, timedelta
from typing import Optional, List
import re

logger = logging.getLogger(__name__)

class SecurityService:
    def __init__(self):
        self.temp_files = []
        self.cleanup_interval = 24  # 24時間でクリーンアップ
        self.max_file_age = 72  # 72時間で強制削除
    
    def mask_phone_number(self, phone_number: str) -> str:
        """電話番号をマスク"""
        if not phone_number:
            return phone_number
        
        # 携帯電話番号のパターン
        mobile_pattern = r'0([789])0-?(\d{4})-?(\d{4})'
        match = re.match(mobile_pattern, phone_number)
        
        if match:
            return f"0{match.group(1)}0-****-{match.group(3)}"
        
        # 固定電話のパターン
        landline_pattern = r'0(\d{1,4})-?(\d{1,4})-?(\d{4})'
        match = re.match(landline_pattern, phone_number)
        
        if match:
            return f"0{match.group(1)}-****-{match.group(3)}"
        
        # その他のパターン
        if len(phone_number) >= 8:
            return phone_number[:3] + "****" + phone_number[-4:]
        
        return phone_number
    
    def sanitize_text(self, text: str) -> str:
        """テキストから個人情報を除去"""
        if not text:
            return text
        
        # 電話番号をマスク
        text = re.sub(r'0[789]0-?\d{4}-?\d{4}', lambda m: self.mask_phone_number(m.group()), text)
        text = re.sub(r'0\d{1,4}-?\d{1,4}-?\d{4}', lambda m: self.mask_phone_number(m.group()), text)
        
        # メールアドレスをマスク
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '***@***.***', text)
        
        # クレジットカード番号をマスク
        text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '****-****-****-****', text)
        
        # 住所らしき文字列をマスク（簡易実装）
        address_patterns = [
            r'\d{3}-?\d{4}',  # 郵便番号
            r'[都道府県市区町村]',  # 住所
        ]
        
        for pattern in address_patterns:
            text = re.sub(pattern, '***', text)
        
        return text
    
    def secure_file_handling(self, file_path: str) -> str:
        """ファイルの安全な処理"""
        try:
            # ファイルの存在確認
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # ファイルサイズチェック
            file_size = os.path.getsize(file_path)
            max_size = 10 * 1024 * 1024  # 10MB
            if file_size > max_size:
                raise ValueError(f"File too large: {file_size} bytes")
            
            # ファイル拡張子チェック
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in allowed_extensions:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # 一時ファイルとして登録
            self.temp_files.append({
                'path': file_path,
                'created_at': datetime.now(),
                'access_count': 0
            })
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error in secure file handling: {str(e)}")
            raise
    
    def cleanup_temp_files(self):
        """一時ファイルのクリーンアップ"""
        try:
            current_time = datetime.now()
            files_to_remove = []
            
            for file_info in self.temp_files:
                file_age = current_time - file_info['created_at']
                
                # 72時間以上経過したファイルは強制削除
                if file_age > timedelta(hours=self.max_file_age):
                    files_to_remove.append(file_info)
                # 24時間以上経過でアクセス回数が0のファイルは削除
                elif file_age > timedelta(hours=self.cleanup_interval) and file_info['access_count'] == 0:
                    files_to_remove.append(file_info)
            
            # ファイルを削除
            for file_info in files_to_remove:
                try:
                    if os.path.exists(file_info['path']):
                        os.remove(file_info['path'])
                        logger.info(f"Cleaned up temp file: {file_info['path']}")
                except Exception as e:
                    logger.error(f"Error removing temp file {file_info['path']}: {str(e)}")
                
                self.temp_files.remove(file_info)
            
        except Exception as e:
            logger.error(f"Error in cleanup_temp_files: {str(e)}")
    
    def validate_image_file(self, file_path: str) -> bool:
        """画像ファイルの検証"""
        try:
            # ファイルの存在確認
            if not os.path.exists(file_path):
                return False
            
            # ファイルサイズチェック
            file_size = os.path.getsize(file_path)
            if file_size == 0 or file_size > 10 * 1024 * 1024:  # 10MB
                return False
            
            # ファイル拡張子チェック
            allowed_extensions = ['.jpg', '.jpeg', '.png']
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext not in allowed_extensions:
                return False
            
            # ファイルヘッダーのチェック（簡易実装）
            with open(file_path, 'rb') as f:
                header = f.read(10)
                
                # JPEG
                if header.startswith(b'\xff\xd8\xff'):
                    return True
                # PNG
                elif header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return True
                # その他は拒否
                else:
                    return False
            
        except Exception as e:
            logger.error(f"Error validating image file: {str(e)}")
            return False
    
    def create_secure_temp_file(self, prefix: str = "temp_", suffix: str = ".jpg") -> str:
        """安全な一時ファイルを作成"""
        try:
            # ランダムなファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_suffix = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
            filename = f"{prefix}{timestamp}_{random_suffix}{suffix}"
            
            # 一時ディレクトリに作成
            temp_dir = "temp"
            os.makedirs(temp_dir, exist_ok=True)
            file_path = os.path.join(temp_dir, filename)
            
            return file_path
            
        except Exception as e:
            logger.error(f"Error creating secure temp file: {str(e)}")
            raise
    
    def log_security_event(self, event_type: str, details: str, user_id: Optional[str] = None):
        """セキュリティイベントをログに記録"""
        try:
            security_log = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'details': details,
                'user_id_hash': hashlib.sha256(user_id.encode()).hexdigest()[:16] if user_id else None
            }
            
            # セキュリティログファイルに記録
            log_file = "logs/security.log"
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{security_log['timestamp']} - {event_type} - {details}\n")
            
            logger.warning(f"Security event: {event_type} - {details}")
            
        except Exception as e:
            logger.error(f"Error logging security event: {str(e)}")
    
    def check_rate_limit(self, user_id: str, limit: int = 10, window_minutes: int = 60) -> bool:
        """レート制限チェック"""
        try:
            # 簡易実装：ファイルベースのレート制限
            rate_limit_file = f"temp/rate_limit_{hashlib.sha256(user_id.encode()).hexdigest()[:16]}.txt"
            
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(minutes=window_minutes)
            
            # 既存のリクエスト時刻を読み込み
            request_times = []
            if os.path.exists(rate_limit_file):
                with open(rate_limit_file, 'r') as f:
                    for line in f:
                        try:
                            request_time = datetime.fromisoformat(line.strip())
                            if request_time > cutoff_time:
                                request_times.append(request_time)
                        except ValueError:
                            continue
            
            # 制限チェック
            if len(request_times) >= limit:
                self.log_security_event("RATE_LIMIT_EXCEEDED", f"User exceeded rate limit: {len(request_times)} requests", user_id)
                return False
            
            # 現在のリクエストを記録
            request_times.append(current_time)
            
            # ファイルに保存
            with open(rate_limit_file, 'w') as f:
                for request_time in request_times:
                    f.write(request_time.isoformat() + '\n')
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return True  # エラーの場合は許可
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """機密データの暗号化（簡易実装）"""
        try:
            # 実際の実装では、適切な暗号化ライブラリを使用
            # ここでは簡易的なBase64エンコードを使用
            import base64
            return base64.b64encode(data.encode()).decode()
            
        except Exception as e:
            logger.error(f"Error encrypting data: {str(e)}")
            return data
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """機密データの復号化（簡易実装）"""
        try:
            import base64
            return base64.b64decode(encrypted_data.encode()).decode()
            
        except Exception as e:
            logger.error(f"Error decrypting data: {str(e)}")
            return encrypted_data

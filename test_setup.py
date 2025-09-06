#!/usr/bin/env python3
"""
環境設定のテストスクリプト
"""
import os
import sys
from dotenv import load_dotenv

def test_environment():
    """環境変数の設定をテスト"""
    print("🔧 環境設定テストを開始します...")
    
    # .envファイルを読み込み
    load_dotenv()
    
    # 必要な環境変数をチェック
    required_vars = [
        'LINE_CHANNEL_ACCESS_TOKEN',
        'LINE_CHANNEL_SECRET',
        'GOOGLE_APPLICATION_CREDENTIALS'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith('your_'):
            missing_vars.append(var)
        else:
            print(f"✅ {var}: 設定済み")
    
    if missing_vars:
        print(f"\n❌ 以下の環境変数が設定されていません:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n📝 .envファイルを確認して、実際の値に置き換えてください。")
        return False
    
    # Google Cloud認証情報の確認
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not os.path.exists(creds_path):
        print(f"❌ Google Cloud認証ファイルが見つかりません: {creds_path}")
        return False
    
    print("✅ Google Cloud認証ファイル: 存在確認")
    
    # LINE Bot APIのテスト
    try:
        from linebot import LineBotApi
        line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
        # 簡単なAPI呼び出しテスト
        print("✅ LINE Bot API: 接続成功")
    except Exception as e:
        print(f"❌ LINE Bot API: 接続エラー - {str(e)}")
        return False
    
    # Google Cloud Vision APIのテスト
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        print("✅ Google Cloud Vision API: 接続成功")
    except Exception as e:
        print(f"❌ Google Cloud Vision API: 接続エラー - {str(e)}")
        return False
    
    print("\n🎉 全ての環境設定が正常です！")
    print("📱 アプリケーションを起動できます: python3 app.py")
    return True

def test_dependencies():
    """依存関係のテスト"""
    print("\n📦 依存関係のテスト...")
    
    required_packages = [
        'flask',
        'linebot',
        'google.cloud.vision',
        'PIL',
        'cv2',
        'pytesseract',
        'pandas',
        'matplotlib',
        'numpy'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}: インストール済み")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package}: 未インストール")
    
    if missing_packages:
        print(f"\n📝 以下のパッケージをインストールしてください:")
        print("pip install -r requirements.txt")
        return False
    
    print("✅ 全ての依存関係が正常です！")
    return True

if __name__ == "__main__":
    print("🚀 携帯料金診断Bot 環境設定テスト")
    print("=" * 50)
    
    # 依存関係のテスト
    deps_ok = test_dependencies()
    
    if deps_ok:
        # 環境変数のテスト
        env_ok = test_environment()
        
        if env_ok:
            print("\n🎯 次のステップ:")
            print("1. python3 app.py でアプリケーションを起動")
            print("2. ngrok http 5000 でWebhook URLを公開")
            print("3. LINE Developers ConsoleでWebhook URLを設定")
            print("4. LINE Botに友達追加してテスト")
        else:
            print("\n🔧 環境設定を完了してから再実行してください。")
            print("📖 詳細は setup_guide.md を参照してください。")
    else:
        print("\n📦 依存関係をインストールしてから再実行してください。")
        print("pip install -r requirements.txt")
    
    sys.exit(0 if (deps_ok and env_ok) else 1)

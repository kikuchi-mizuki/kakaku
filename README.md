# 携帯料金診断Bot

LINE Botを使用して携帯料金明細を解析し、dモバイルのおすすめプランを提案するシステムです。

## 機能概要

- 📱 携帯料金明細（画像/PDF）のOCR解析
- 🔍 回線費用のみを自動抽出（端末代金等は除外）
- 🎯 dモバイルプランの自動選定（S以外）
- 📊 50年累積損失の可視化（折れ線グラフ + CSV）
- 💰 その金額でできることの例示
- 🔗 2つのCTAボタン（回線切り替え/獲得）

## システム構成

```
kakaku/
├── app.py                 # メインアプリケーション
├── config.py             # 設定ファイル
├── requirements.txt      # 依存関係
├── services/            # サービス層
│   ├── line_service.py      # LINE Bot API
│   ├── ocr_service.py       # OCR処理
│   ├── bill_processor.py    # 請求書解析
│   ├── plan_selector.py     # プラン選定
│   ├── cost_comparator.py   # 料金比較・可視化
│   ├── analytics_service.py # ログ・解析
│   └── security_service.py  # セキュリティ
├── utils/               # ユーティリティ
│   └── logger.py           # ログ設定
├── tests/               # テスト
│   ├── test_bill_processor.py
│   ├── test_plan_selector.py
│   └── test_cost_comparator.py
├── logs/                # ログファイル
├── temp/                # 一時ファイル
└── outputs/             # 出力ファイル
```

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の設定を行ってください：

```env
# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret

# Google Cloud Vision API
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# アプリケーション設定
FLASK_ENV=development
SECRET_KEY=your_secret_key

# ログ設定
LOG_LEVEL=INFO
ENABLE_FILE_LOGGING=true

# Tesseract設定（オプション）
# TESSERACT_CMD=/usr/bin/tesseract

# AI診断設定
AI_DIAGNOSIS_ENABLED=true
AI_CONFIDENCE_THRESHOLD=0.7

# OpenAI API設定（推奨）
OPENAI_API_KEY=your_openai_api_key_here
USE_OPENAI_ANALYSIS=true

# プラン選定設定
EXCLUDE_S_PLAN=true
ENABLE_24H_UNLIMITED=true

# 料金比較設定
SHOW_50YEAR_ANALYSIS=true
SHOW_DMOBILE_BENEFITS=true

# dモバイルアフィリエイトリンク
DMOBILE_SWITCH_URL=https://mypage.dmobile.jp/DJP249422?openExternalBrowser=1
DMOBILE_ACQUIRE_URL=https://mypage.dmobile.jp/CJP249422
```

### 3. Google Cloud Vision APIの設定

1. Google Cloud Consoleでプロジェクトを作成
2. Vision APIを有効化
3. サービスアカウントキーをダウンロード
4. `GOOGLE_APPLICATION_CREDENTIALS`にパスを設定

### 4. LINE Botの設定

1. LINE Developers Consoleでチャネルを作成
2. Webhook URLを設定: `https://your-domain.com/webhook`
3. チャネルアクセストークンとシークレットを取得

### 5. 環境変数の詳細説明

#### 必須設定
- `LINE_CHANNEL_ACCESS_TOKEN`: LINE Botのチャネルアクセストークン
- `LINE_CHANNEL_SECRET`: LINE Botのチャネルシークレット

#### AI診断設定
- `AI_DIAGNOSIS_ENABLED`: AI診断機能の有効/無効 (true/false)
- `AI_CONFIDENCE_THRESHOLD`: AI診断の信頼度閾値 (0.0-1.0)

#### OpenAI API設定（推奨）
- `OPENAI_API_KEY`: OpenAI APIキー（高精度な分析のため推奨）
- `USE_OPENAI_ANALYSIS`: OpenAI APIを使用するか (true/false)

**OpenAI APIの取得方法:**
1. [OpenAI Platform](https://platform.openai.com/)にアクセス
2. アカウントを作成・ログイン
3. API Keysセクションで新しいAPIキーを生成
4. 生成されたキーを`OPENAI_API_KEY`に設定

#### プラン選定設定
- `EXCLUDE_S_PLAN`: Sプランを除外するか (true/false)
- `ENABLE_24H_UNLIMITED`: 24時間かけ放題オプションを有効にするか (true/false)

#### 料金比較設定
- `SHOW_50YEAR_ANALYSIS`: 50年累積分析を表示するか (true/false)
- `SHOW_DMOBILE_BENEFITS`: dモバイルのメリットを表示するか (true/false)

#### ログ設定
- `ENABLE_FILE_LOGGING`: ファイルログを有効にするか (true/false)
- `LOG_LEVEL`: ログレベル (DEBUG/INFO/WARNING/ERROR)

#### Tesseract設定（オプション）
- `TESSERACT_CMD`: Tesseractの実行ファイルパス（自動検出できない場合のみ設定）

**Tesseractのインストール方法:**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-jpn
```

**CentOS/RHEL:**
```bash
sudo yum install tesseract tesseract-langpack-jpn
# または
sudo dnf install tesseract tesseract-langpack-jpn
```

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Windows:**
1. [Tesseract公式サイト](https://github.com/UB-Mannheim/tesseract/wiki)からダウンロード
2. インストール後、環境変数PATHに追加
3. 日本語言語パックもインストール

**Docker環境:**
```dockerfile
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-jpn
```

**インストール確認:**
```bash
tesseract --version
tesseract --list-langs
```

## 実行方法

### 開発環境

```bash
python app.py
```

### 本番環境

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## テスト実行

```bash
python run_tests.py
```

## 使用方法

1. LINE Botに友達追加
2. 携帯料金明細の画像を送信
3. 自動解析結果を確認
4. おすすめプランとCTAボタンでアクション

## 対応キャリア

- ドコモ
- au
- ソフトバンク
- 楽天モバイル
- 主要MVNO

## 提案プラン

- dモバイル M（1日2GB + 5分かけ放題）
- dモバイル L（1日4GB + 5分かけ放題）
- dモバイル M + 24時間かけ放題
- dモバイル L + 24時間かけ放題

※ Sプランは提案対象外

## セキュリティ・プライバシー

- 電話番号は中間4桁をマスク
- 画像は解析後に短期破棄（24-72時間）
- 通信はTLS暗号化
- 個人情報は適切に保護

## ログ・解析

- 解析結果の匿名化ログ
- プラン選択の傾向分析
- CTAクリック率の追跡
- エラー監視

## デプロイ

### クラウド環境での注意点

- **ファイルログ**: クラウド環境では `ENABLE_FILE_LOGGING=false` に設定することを推奨
- **OpenCV**: `opencv-python-headless` を使用（GUI依存関係なし）
- **ログディレクトリ**: 自動作成されるため、事前作成不要

### Railway

```bash
railway login
railway init
railway up
```

### Render

1. GitHubリポジトリを接続
2. 環境変数を設定
3. 自動デプロイ

### GCP Cloud Run

```bash
gcloud run deploy kakaku-bot --source .
```

## ライセンス

MIT License

## 貢献

プルリクエストやイシューの報告を歓迎します。

## サポート

問題が発生した場合は、GitHubのIssuesで報告してください。

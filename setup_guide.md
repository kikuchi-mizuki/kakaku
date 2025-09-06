# 携帯料金診断Bot セットアップガイド

## 1. LINE Botの設定

### 1.1 LINE Developers Consoleでの設定

1. [LINE Developers Console](https://developers.line.biz/ja/)にアクセス
2. ログイン後、「Create」をクリック
3. 「Create a new provider」でプロバイダー名を入力
4. 「Create a new channel」で「Messaging API」を選択
5. チャネル情報を入力：
   - Channel name: `携帯料金診断Bot`
   - Channel description: `携帯料金明細を解析してdモバイルプランを提案`
   - Category: `Tools`
   - Subcategory: `Other`

### 1.2 認証情報の取得

1. 作成したチャネルの「Basic settings」タブで：
   - **Channel secret** をコピー
   - **Channel access token** を発行してコピー

2. 「Messaging API settings」タブで：
   - Webhook URL: `https://your-domain.com/webhook` (後で設定)
   - Webhookの利用: `オン`
   - Auto-reply messages: `オフ`
   - Greeting messages: `オフ`

## 2. Google Cloud Vision APIの設定

### 2.1 Google Cloud Consoleでの設定

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成（例：`kakaku-bot-2024`）
3. プロジェクトを選択

### 2.2 Vision APIの有効化

1. 「APIとサービス」>「ライブラリ」に移動
2. 「Vision API」を検索
3. 「有効にする」をクリック

### 2.3 サービスアカウントの作成

1. 「IAMと管理」>「サービスアカウント」に移動
2. 「サービスアカウントを作成」をクリック
3. サービスアカウント情報を入力：
   - 名前: `kakaku-bot-service`
   - 説明: `携帯料金診断Bot用サービスアカウント`
4. ロール: `Cloud Vision API User`
5. 「キーを作成」>「JSON」を選択
6. ダウンロードしたJSONファイルを安全な場所に保存

## 3. 環境変数の設定

### 3.1 .envファイルの作成

プロジェクトルートに`.env`ファイルを作成し、以下の内容を記述：

```env
# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token_here
LINE_CHANNEL_SECRET=your_channel_secret_here

# Google Cloud Vision API
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# アプリケーション設定
FLASK_ENV=development
SECRET_KEY=your_secret_key_here

# dモバイルアフィリエイトリンク
DMOBILE_SWITCH_URL=https://mypage.dmobile.jp/DJP249422?openExternalBrowser=1
DMOBILE_ACQUIRE_URL=https://mypage.dmobile.jp/CJP249422
```

### 3.2 実際の値に置き換え

1. `your_channel_access_token_here` → 実際のチャネルアクセストークン
2. `your_channel_secret_here` → 実際のチャネルシークレット
3. `path/to/your/service-account-key.json` → ダウンロードしたJSONファイルのパス
4. `your_secret_key_here` → ランダムな文字列（例：`kakaku_bot_2024_secret_key`）

## 4. ローカルテスト

### 4.1 アプリケーションの起動

```bash
python3 app.py
```

### 4.2 ngrokでのWebhook URL公開

```bash
# ngrokをインストール（未インストールの場合）
brew install ngrok  # macOS
# または https://ngrok.com/download からダウンロード

# Webhook URLを公開
ngrok http 5000
```

### 4.3 LINE Developers ConsoleでWebhook URL設定

1. ngrokで表示されたURL（例：`https://abc123.ngrok.io`）をコピー
2. LINE Developers Consoleの「Messaging API settings」で：
   - Webhook URL: `https://abc123.ngrok.io/webhook`
   - 「検証」をクリックして成功を確認
   - Webhookの利用を「オン」に設定

## 5. テスト実行

### 5.1 LINE Botに友達追加

1. 作成したチャネルのQRコードをスキャン
2. 友達追加

### 5.2 テストメッセージ送信

1. 「ヘルプ」と送信 → ヘルプメッセージが表示されることを確認
2. 携帯料金明細の画像を送信 → 解析結果が表示されることを確認

## 6. デプロイ

### 6.1 Railwayでのデプロイ

```bash
# Railway CLIをインストール
npm install -g @railway/cli

# ログイン
railway login

# プロジェクトを初期化
railway init

# 環境変数を設定
railway variables set LINE_CHANNEL_ACCESS_TOKEN=your_token
railway variables set LINE_CHANNEL_SECRET=your_secret
railway variables set GOOGLE_APPLICATION_CREDENTIALS=your_json_content

# デプロイ
railway up
```

### 6.2 Renderでのデプロイ

1. GitHubにリポジトリをプッシュ
2. Render.comにアクセス
3. 新しいWebサービスを作成
4. GitHubリポジトリを選択
5. 環境変数を設定
6. デプロイ

## 7. トラブルシューティング

### 7.1 よくある問題

- **Webhook検証エラー**: URLが正しく設定されているか確認
- **OCRエラー**: Google Cloud Vision APIの認証情報を確認
- **LINE Bot応答なし**: チャネルアクセストークンを確認

### 7.2 ログの確認

```bash
# ローカル実行時のログ
tail -f logs/app_$(date +%Y%m%d).log

# Railwayでのログ
railway logs

# Renderでのログ
Render Dashboard > サービス > Logs
```

## 8. 次のステップ

1. 実際の請求書画像でテスト
2. プラン選択ロジックの調整
3. ユーザーフィードバックの収集
4. 機能の拡張（他社プラン比較等）

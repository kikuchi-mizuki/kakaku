import logging
import re
import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from config import Config
try:
    import requests  # HTTPフォールバック用
except Exception:
    requests = None
from typing import Dict, List, Optional
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class AIDiagnosisService:
    """AI診断サービス - 携帯料金の詳細分析と提案"""
    
    def __init__(self):
        # 環境変数の検証
        self._validate_environment()
        
        # OpenAI API設定
        self.openai_client = None
        self.use_openai = Config.USE_OPENAI_ANALYSIS and Config.OPENAI_API_KEY
        
        if self.use_openai:
            try:
                logger.info(f"Attempting to initialize OpenAI API with key: {Config.OPENAI_API_KEY[:10]}...")
                
                # OpenAIライブラリのインポート
                try:
                    from openai import OpenAI
                    logger.info("OpenAI library imported successfully")
                    
                    # ライブラリのバージョン確認
                    try:
                        import openai
                        logger.info(f"OpenAI library version: {getattr(openai, '__version__', 'unknown')}")
                    except Exception:
                        logger.info("Could not determine OpenAI library version")
                        
                except ImportError as e:
                    logger.error(f"Failed to import OpenAI library: {str(e)}")
                    raise
                
                # APIキーの検証
                if not Config.OPENAI_API_KEY or len(Config.OPENAI_API_KEY) < 10:
                    logger.error("OpenAI API key is invalid or too short")
                    raise ValueError("Invalid OpenAI API key")
                
                # OpenAI APIの初期化（プロキシ設定を無効化）
                self.openai_client = self._initialize_openai_without_proxy(Config.OPENAI_API_KEY)
                logger.info("OpenAI API initialization completed successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI API: {str(e)}")
                logger.error(f"Error type: {type(e).__name__}")
                logger.info("Falling back to rule-based analysis only")
                self.use_openai = False
        
        self.carrier_patterns = {
            'docomo': ['ドコモ', 'NTTドコモ', 'docomo', 'DOCOMO'],
            'au': ['au', 'KDDI', 'au by KDDI'],
            'softbank': ['ソフトバンク', 'SoftBank', 'softbank', 'SOFTBANK'],
            'rakuten': ['楽天モバイル', 'Rakuten Mobile', '楽天', 'rakuten'],
            'ymobile': ['ワイモバイル', 'Y!mobile', 'Ymobile', 'ワイモバ'],
            'uq': ['UQ mobile', 'UQモバイル', 'uq'],
            'ahamo': ['ahamo', 'アハモ'],
            'povo': ['povo', 'ポヴォ'],
            'LINEMO': ['LINEMO', 'ラインモ']
        }
        
        self.terminal_keywords = [
            '端末代金', '端末決済', '端末料金', '機種代金', 'スマートフォン代金',
            'iPhone代金', 'Android代金', '端末分割', '端末ローン', '端末購入',
            'デバイス代金', 'ハードウェア代金', '端末価格', '機種価格'
        ]
        
        self.line_cost_keywords = [
            '基本料金', '月額料金', '通信料', 'データ通信料', '通話料',
            '回線料', 'サービス料', 'オプション料', 'プラン料金', '月額プラン',
            'データプラン', '通話プラン', '回線使用料', 'サービス使用料'
        ]

    def analyze_bill_with_ai(self, ocr_text: str) -> Dict:
        """AI診断による請求書分析（OpenAI API統合）"""
        try:
            logger.info("Starting AI diagnosis of bill")
            
            # OpenAI APIを使用する場合
            if self.use_openai:
                analysis_result = self._analyze_with_openai(ocr_text)
                if analysis_result and analysis_result.get('confidence', 0) > Config.AI_CONFIDENCE_THRESHOLD:
                    logger.info("OpenAI analysis completed successfully")
                    return analysis_result
                else:
                    logger.warning("OpenAI analysis failed or low confidence, falling back to rule-based analysis")
            
            # ルールベース分析（フォールバック）
            analysis_result = self._analyze_with_rules(ocr_text)
            
            logger.info(f"AI diagnosis completed: {analysis_result['carrier']}, Line cost: ¥{analysis_result['line_cost']:,}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in AI diagnosis: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            # エラーの詳細情報を提供
            error_details = [
                '解析中にエラーが発生しました',
                f'エラー種別: {type(e).__name__}',
                f'エラー内容: {str(e)}',
                '',
                '【推奨対応】',
                '1. 画像の鮮明度を確認してください',
                '2. Tesseractのインストールを確認してください',
                '3. Google Cloud Vision APIの設定を確認してください',
                '4. OpenAI APIキーの設定を確認してください'
            ]
            
            return {
                'carrier': 'Unknown',
                'current_plan': 'Unknown',
                'line_cost': 0,
                'terminal_cost': 0,
                'total_cost': 0,
                'data_usage': 0,
                'call_usage': 0,
                'confidence': 0.0,
                'analysis_details': error_details,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def _analyze_with_openai(self, ocr_text: str) -> Dict:
        """OpenAI APIを使った分析"""
        try:
            prompt = self._create_analysis_prompt(ocr_text)
            
            # 利用可能な呼び出し経路を順に試行
            response = None
            if self.openai_client is not None and hasattr(self.openai_client, 'chat'):
                # 新しいAPI形式 (v1.0+)
                response = self.openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "あなたは携帯料金明細の専門分析AIです。請求書の内容を正確に分析し、JSON形式で結果を返してください。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1000
                )
            elif self.openai_client is not None and hasattr(self.openai_client, 'ChatCompletion'):
                # 古いAPI形式 (v0.x)
                response = self.openai_client.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "あなたは携帯料金明細の専門分析AIです。請求書の内容を正確に分析し、JSON形式で結果を返してください。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1000
                )
            else:
                logger.info("Using HTTP fallback for OpenAI API")
                result_text = self._analyze_with_openai_http(prompt)
                if not result_text:
                    return None
                analysis_result = json.loads(result_text)
                analysis_result = self._validate_openai_result(analysis_result)
                return analysis_result
            
            result_text = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response: {result_text}")
            
            # JSON形式の結果をパース
            analysis_result = json.loads(result_text)
            
            # 結果の検証と補完
            analysis_result = self._validate_openai_result(analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in OpenAI analysis: {str(e)}")
            return None

    def _analyze_with_openai_http(self, prompt: str) -> Optional[str]:
        """ライブラリ非依存のHTTPフォールバックでChat Completionsを呼び出す"""
        try:
            if requests is None:
                logger.error("requests library is not available for HTTP fallback")
                return None
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "あなたは携帯料金明細の専門分析AIです。請求書の内容を正確に分析し、JSON形式で結果を返してください。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            # プロキシ環境変数の影響を避ける
            # プロキシ環境変数の影響を避けるため proxies を明示的に空指定
            resp = requests.post(url, headers=headers, json=payload, timeout=30, proxies={})
            if resp.status_code != 200:
                logger.error(f"HTTP fallback failed: {resp.status_code} {resp.text}")
                return None
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"HTTP fallback exception: {str(e)}")
            return None
    
    def _create_analysis_prompt(self, ocr_text: str) -> str:
        """OpenAI API用のプロンプトを作成"""
        prompt = f"""
以下の携帯料金明細の内容を分析してください：

{ocr_text}

以下の情報を抽出し、JSON形式で返してください：

{{
    "carrier": "キャリア名（docomo, au, softbank, rakuten, ymobile, uq, ahamo, povo, LINEMO のいずれか）",
    "current_plan": "現在のプラン名",
    "line_cost": 回線費用の数値（端末代金を除く）,
    "terminal_cost": 端末代金の数値,
    "total_cost": 合計金額の数値,
    "data_usage": データ使用量の数値（GB）,
    "call_usage": 通話時間の数値（分）,
    "confidence": 分析の信頼度（0.0-1.0）,
    "analysis_details": ["分析の詳細1", "分析の詳細2", ...]
}}

注意事項：
- 回線費用は端末代金を除外してください
- 金額は数値のみで返してください（カンマや円マークは不要）
- 信頼度は分析の確実性を0.0-1.0で評価してください
- 不明な項目は0または"Unknown"で返してください
- JSON形式のみで返し、説明文は含めないでください
"""
        return prompt
    
    def _validate_openai_result(self, result: Dict) -> Dict:
        """OpenAI APIの結果を検証・補完"""
        try:
            # 必須フィールドの確認
            required_fields = ['carrier', 'current_plan', 'line_cost', 'terminal_cost', 'total_cost', 'data_usage', 'call_usage', 'confidence']
            
            for field in required_fields:
                if field not in result:
                    if field in ['line_cost', 'terminal_cost', 'total_cost', 'data_usage', 'call_usage', 'confidence']:
                        result[field] = 0
                    else:
                        result[field] = 'Unknown'
            
            # 数値フィールドの型変換
            numeric_fields = ['line_cost', 'terminal_cost', 'total_cost', 'data_usage', 'call_usage', 'confidence']
            for field in numeric_fields:
                if isinstance(result[field], str):
                    try:
                        result[field] = float(result[field])
                    except ValueError:
                        result[field] = 0
            
            # 回線費用の計算（端末代金を除外）
            if result['total_cost'] > 0 and result['terminal_cost'] > 0:
                result['line_cost'] = max(0, result['total_cost'] - result['terminal_cost'])
            
            # 分析詳細の生成
            if 'analysis_details' not in result or not result['analysis_details']:
                result['analysis_details'] = self._generate_analysis_details(result)
            
            logger.info(f"Validated OpenAI result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error validating OpenAI result: {str(e)}")
            return None
    
    def _analyze_with_rules(self, ocr_text: str) -> Dict:
        """ルールベース分析（フォールバック）"""
        try:
            # 基本情報の抽出
            analysis_result = {
                'carrier': self._detect_carrier(ocr_text),
                'current_plan': self._extract_current_plan(ocr_text),
                'line_cost': self._extract_line_cost(ocr_text),
                'terminal_cost': self._extract_terminal_cost(ocr_text),
                'total_cost': 0,
                'data_usage': self._extract_data_usage(ocr_text),
                'call_usage': self._extract_call_usage(ocr_text),
                'confidence': 0.0,
                'analysis_details': []
            }
            
            # 回線費用のみを計算（端末代金を除外）
            analysis_result['total_cost'] = analysis_result['line_cost']
            
            # 信頼度の計算
            analysis_result['confidence'] = self._calculate_confidence(analysis_result, ocr_text)
            
            # 分析詳細の生成
            analysis_result['analysis_details'] = self._generate_analysis_details(analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in rule-based analysis: {str(e)}")
            return {
                'carrier': 'Unknown',
                'current_plan': 'Unknown',
                'line_cost': 0,
                'terminal_cost': 0,
                'total_cost': 0,
                'data_usage': 0,
                'call_usage': 0,
                'confidence': 0.0,
                'analysis_details': ['解析中にエラーが発生しました']
            }

    def _detect_carrier(self, text: str) -> str:
        """キャリアの検出（改善版）"""
        text_lower = text.lower()
        
        # より詳細なパターンマッチング
        for carrier, patterns in self.carrier_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    logger.info(f"Carrier detected: {carrier} (pattern: {pattern})")
                    return carrier
        
        # 追加のパターンマッチング
        additional_patterns = {
            'docomo': ['ntt', 'ドコモ', 'docomo'],
            'au': ['kddi', 'au', 'エーユー'],
            'softbank': ['softbank', 'ソフトバンク', 'sb'],
            'rakuten': ['rakuten', '楽天', '楽天モバイル'],
            'ymobile': ['ymobile', 'ワイモバイル', 'y!mobile']
        }
        
        for carrier, patterns in additional_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    logger.info(f"Carrier detected (additional): {carrier} (pattern: {pattern})")
                    return carrier
        
        logger.warning(f"No carrier detected in text: {text[:100]}...")
        return 'Unknown'

    def _extract_current_plan(self, text: str) -> str:
        """現在のプランの抽出（改善版）"""
        # プラン名のパターンを検索
        plan_patterns = [
            r'プラン[：:]\s*([^\n\r]+)',
            r'料金プラン[：:]\s*([^\n\r]+)',
            r'契約プラン[：:]\s*([^\n\r]+)',
            r'サービスプラン[：:]\s*([^\n\r]+)',
            r'プラン名[：:]\s*([^\n\r]+)',
            r'([^\n\r]*プラン[^\n\r]*)',
            r'([^\n\r]*データプラン[^\n\r]*)',
            r'([^\n\r]*通話プラン[^\n\r]*)',
            r'([^\n\r]*スマホプラン[^\n\r]*)',
            r'([A-Za-z0-9]+プラン)',
            r'([A-Za-z0-9]+コース)',
            r'([A-Za-z0-9]+パック)'
        ]
        
        for pattern in plan_patterns:
            match = re.search(pattern, text)
            if match:
                plan_name = match.group(1).strip()
                if plan_name and plan_name != 'Unknown':
                    logger.info(f"Plan detected: {plan_name}")
                    return plan_name
        
        # 追加の検索パターン
        additional_patterns = [
            r'([A-Za-z0-9]+プラン[0-9]+GB)',
            r'([A-Za-z0-9]+プラン[0-9]+)',
            r'(データ[0-9]+GB)',
            r'(通話[0-9]+分)',
            r'([0-9]+GBプラン)',
            r'([0-9]+分プラン)'
        ]
        
        for pattern in additional_patterns:
            match = re.search(pattern, text)
            if match:
                plan_name = match.group(1).strip()
                if plan_name:
                    logger.info(f"Plan detected (additional): {plan_name}")
                    return plan_name
        
        logger.warning(f"No plan detected in text: {text[:100]}...")
        return 'Unknown Plan'

    def _extract_line_cost(self, text: str) -> int:
        """回線費用の抽出（端末代金を除外）- 改善版"""
        try:
            logger.info("=== 回線費用抽出開始 ===")
            logger.info(f"入力テキスト: {text[:200]}...")
            
            # より詳細な金額抽出パターン（強化版）
            amount_patterns = [
                r'¥([0-9,]+)',           # ¥1,000
                r'([0-9,]+)円',          # 1,000円
                r'([0-9,]+)',            # 1,000
                r'([0-9]+)',             # 1000
                r'([0-9,]+)\.([0-9]{2})', # 1,000.00
                r'([0-9]+)\.([0-9]{2})',  # 1000.00
                r'([0-9,]+)円',          # 1,000円（重複だが確実性向上）
                r'([0-9]+)円',           # 1000円
                r'([0-9,]+)\.([0-9]{2})円', # 1,000.00円
                r'([0-9]+)\.([0-9]{2})円',  # 1000.00円
                r'([0-9,]+)円\s*合計',    # 1,000円 合計
                r'([0-9]+)円\s*合計',     # 1000円 合計
                r'合計\s*¥?([0-9,]+)',   # 合計 ¥1,000
                r'合計\s*([0-9,]+)円',   # 合計 1,000円
                r'請求金額\s*¥?([0-9,]+)', # 請求金額 ¥1,000
                r'請求金額\s*([0-9,]+)円', # 請求金額 1,000円
                r'月額\s*¥?([0-9,]+)',   # 月額 ¥1,000
                r'月額\s*([0-9,]+)円',   # 月額 1,000円
                r'料金\s*¥?([0-9,]+)',   # 料金 ¥1,000
                r'料金\s*([0-9,]+)円'    # 料金 1,000円
            ]
            
            # 請求書の構造を分析
            lines = text.split('\n')
            line_costs = []
            total_cost = 0
            
            logger.info(f"テキスト行数: {len(lines)}")
            
            # 1. 明細項目から回線費用を抽出
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # 回線費用に関連するキーワードをチェック
                for keyword in self.line_cost_keywords:
                    if keyword in line:
                        # 金額を抽出
                        for pattern in amount_patterns:
                            matches = re.findall(pattern, line)
                            for match in matches:
                                try:
                                    cost = int(match.replace(',', ''))
                                    if 100 <= cost <= 100000:  # 妥当な範囲
                                        line_costs.append(cost)
                                        logger.info(f"行{i+1}: 回線費用発見 - {keyword} = ¥{cost:,} (行内容: {line})")
                                except ValueError:
                                    continue
            
            logger.info(f"明細項目から抽出した回線費用: {line_costs}")
            
            # 2. 合計金額から端末代金を除外
            total_amount = self._extract_total_amount(text)
            terminal_cost = self._extract_terminal_cost(text)
            
            logger.info(f"合計金額: ¥{total_amount:,}")
            logger.info(f"端末代金: ¥{terminal_cost:,}")
            
            if total_amount > 0:
                # 合計金額から端末代金を引いたものを回線費用とする
                line_cost = max(0, total_amount - terminal_cost)
                logger.info(f"計算方法1: 合計({total_amount:,}) - 端末({terminal_cost:,}) = {line_cost:,}")
                return line_cost
            
            # 3. 明細項目の合計を使用
            if line_costs:
                total_line_cost = sum(line_costs)
                logger.info(f"計算方法2: 明細項目合計 = {total_line_cost:,}")
                return total_line_cost
            
            # 4. フォールバック: 月額料金の推定
            estimated_cost = self._estimate_monthly_cost(text)
            if estimated_cost > 0:
                logger.info(f"計算方法3: 推定値 = {estimated_cost:,}")
                return estimated_cost
            
            logger.warning("回線費用の抽出に失敗しました")
            return 0
            
        except Exception as e:
            logger.error(f"Error extracting line cost: {str(e)}")
            return 0
    
    def _extract_total_amount(self, text: str) -> int:
        """請求書の合計金額を抽出"""
        try:
            logger.info("=== 合計金額抽出開始 ===")
            
            # 合計金額のパターン（強化版）
            total_patterns = [
                r'合計[：:]*\s*¥?([0-9,]+)',
                r'請求金額[：:]*\s*¥?([0-9,]+)',
                r'総額[：:]*\s*¥?([0-9,]+)',
                r'月額料金[：:]*\s*¥?([0-9,]+)',
                r'料金合計[：:]*\s*¥?([0-9,]+)',
                r'請求額[：:]*\s*¥?([0-9,]+)',
                r'支払金額[：:]*\s*¥?([0-9,]+)',
                r'合計\s*¥?([0-9,]+)',
                r'請求\s*¥?([0-9,]+)',
                r'月額\s*¥?([0-9,]+)',
                r'料金\s*¥?([0-9,]+)',
                r'([0-9,]+)円\s*合計',
                r'([0-9,]+)円\s*請求',
                r'([0-9,]+)円\s*月額',
                r'合計[：:]*\s*([0-9,]+)円',
                r'請求金額[：:]*\s*([0-9,]+)円',
                r'総額[：:]*\s*([0-9,]+)円',
                r'月額料金[：:]*\s*([0-9,]+)円',
                r'料金合計[：:]*\s*([0-9,]+)円',
                r'請求額[：:]*\s*([0-9,]+)円',
                r'支払金額[：:]*\s*([0-9,]+)円',
                r'合計\s*([0-9,]+)円',
                r'請求\s*([0-9,]+)円',
                r'月額\s*([0-9,]+)円',
                r'料金\s*([0-9,]+)円',
                r'([0-9,]+)\.([0-9]{2})円\s*合計',
                r'([0-9,]+)\.([0-9]{2})円\s*請求',
                r'([0-9,]+)\.([0-9]{2})円\s*月額',
                r'合計[：:]*\s*([0-9,]+)\.([0-9]{2})円',
                r'請求金額[：:]*\s*([0-9,]+)\.([0-9]{2})円',
                r'総額[：:]*\s*([0-9,]+)\.([0-9]{2})円'
            ]
            
            for pattern in total_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        amount = int(match.replace(',', ''))
                        if 1000 <= amount <= 100000:  # 妥当な範囲
                            logger.info(f"合計金額発見: ¥{amount:,} (パターン: {pattern})")
                            return amount
                    except ValueError:
                        continue
            
            logger.warning("合計金額の抽出に失敗しました")
            return 0
            
        except Exception as e:
            logger.error(f"Error extracting total amount: {str(e)}")
            return 0
    
    def _estimate_monthly_cost(self, text: str) -> int:
        """月額料金の推定"""
        try:
            # キャリア別の推定料金
            carrier = self._detect_carrier(text)
            
            # 一般的な月額料金の範囲
            estimated_costs = {
                'docomo': 5000,
                'au': 4500,
                'softbank': 4000,
                'rakuten': 3000,
                'ymobile': 3500,
                'uq': 3000,
                'ahamo': 3000,
                'povo': 3000,
                'LINEMO': 3000
            }
            
            if carrier in estimated_costs:
                return estimated_costs[carrier]
            
            return 4000  # デフォルト推定値
            
        except Exception as e:
            logger.error(f"Error estimating monthly cost: {str(e)}")
            return 0

    def _extract_terminal_cost(self, text: str) -> int:
        """端末代金の抽出 - 改善版"""
        try:
            terminal_costs = []
            
            # 端末代金のパターンを拡張
            terminal_patterns = [
                r'端末代金[：:]*\s*¥?([0-9,]+)',
                r'端末決済[：:]*\s*¥?([0-9,]+)',
                r'端末料金[：:]*\s*¥?([0-9,]+)',
                r'機種代金[：:]*\s*¥?([0-9,]+)',
                r'スマートフォン代金[：:]*\s*¥?([0-9,]+)',
                r'iPhone代金[：:]*\s*¥?([0-9,]+)',
                r'Android代金[：:]*\s*¥?([0-9,]+)',
                r'端末分割[：:]*\s*¥?([0-9,]+)',
                r'端末ローン[：:]*\s*¥?([0-9,]+)',
                r'端末購入[：:]*\s*¥?([0-9,]+)',
                r'デバイス代金[：:]*\s*¥?([0-9,]+)',
                r'ハードウェア代金[：:]*\s*¥?([0-9,]+)',
                r'端末価格[：:]*\s*¥?([0-9,]+)',
                r'機種価格[：:]*\s*¥?([0-9,]+)',
                r'月割[：:]*\s*¥?([0-9,]+)',
                r'分割払い[：:]*\s*¥?([0-9,]+)'
            ]
            
            for pattern in terminal_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    try:
                        cost = int(match.replace(',', ''))
                        if 1000 <= cost <= 200000:  # 端末代金の妥当な範囲
                            terminal_costs.append(cost)
                            logger.info(f"Found terminal cost: ¥{cost:,}")
                    except ValueError:
                        continue
            
            # 端末代金の合計
            total_terminal_cost = sum(terminal_costs)
            if total_terminal_cost > 0:
                logger.info(f"Total terminal cost: ¥{total_terminal_cost:,}")
            
            return total_terminal_cost
            
        except Exception as e:
            logger.error(f"Error extracting terminal cost: {str(e)}")
            return 0

    def _extract_data_usage(self, text: str) -> float:
        """データ使用量の抽出（GB）"""
        data_patterns = [
            r'([0-9.]+)\s*GB',
            r'([0-9.]+)\s*ギガ',
            r'データ使用量[：:]*\s*([0-9.]+)',
            r'通信量[：:]*\s*([0-9.]+)'
        ]
        
        for pattern in data_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return 0.0

    def _extract_call_usage(self, text: str) -> int:
        """通話使用量の抽出（分）"""
        call_patterns = [
            r'([0-9]+)\s*分',
            r'通話時間[：:]*\s*([0-9]+)',
            r'通話料[：:]*\s*([0-9]+)'
        ]
        
        for pattern in call_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        return 0

    def _calculate_confidence(self, analysis: Dict, text: str) -> float:
        """分析の信頼度を計算（改善版）"""
        confidence = 0.0
        
        # キャリアが検出された場合
        if analysis['carrier'] != 'Unknown':
            confidence += 0.4
            logger.info(f"Confidence +0.4 for carrier detection: {analysis['carrier']}")
        
        # 回線費用が検出された場合
        if analysis['line_cost'] > 0:
            confidence += 0.3
            logger.info(f"Confidence +0.3 for line cost detection: ¥{analysis['line_cost']:,}")
        
        # プランが検出された場合
        if analysis['current_plan'] != 'Unknown Plan' and analysis['current_plan'] != 'Unknown':
            confidence += 0.2
            logger.info(f"Confidence +0.2 for plan detection: {analysis['current_plan']}")
        
        # データ使用量が検出された場合
        if analysis['data_usage'] > 0:
            confidence += 0.05
            logger.info(f"Confidence +0.05 for data usage detection: {analysis['data_usage']}GB")
        
        # 端末代金が検出された場合
        if analysis.get('terminal_cost', 0) > 0:
            confidence += 0.05
            logger.info(f"Confidence +0.05 for terminal cost detection: ¥{analysis['terminal_cost']:,}")
        
        # テキストの長さによる調整
        if len(text) > 100:
            confidence += 0.1
            logger.info("Confidence +0.1 for sufficient text length")
        
        # 数値の存在による調整
        import re
        numbers = re.findall(r'\d+', text)
        if len(numbers) >= 3:
            confidence += 0.1
            logger.info(f"Confidence +0.1 for multiple numbers found: {len(numbers)}")
        
        final_confidence = min(confidence, 1.0)
        logger.info(f"Final confidence: {final_confidence:.2f}")
        return final_confidence

    def _generate_analysis_details(self, analysis: Dict) -> List[str]:
        """分析詳細の生成"""
        details = []
        
        if analysis['carrier'] != 'Unknown':
            details.append(f"キャリア: {analysis['carrier']}")
        
        if analysis['current_plan'] != 'Unknown Plan':
            details.append(f"現在のプラン: {analysis['current_plan']}")
        
        if analysis['line_cost'] > 0:
            details.append(f"回線費用: ¥{analysis['line_cost']:,}")
        
        if analysis['terminal_cost'] > 0:
            details.append(f"端末代金: ¥{analysis['terminal_cost']:,} (計算から除外)")
        
        if analysis['data_usage'] > 0:
            details.append(f"データ使用量: {analysis['data_usage']}GB")
        
        if analysis['call_usage'] > 0:
            details.append(f"通話時間: {analysis['call_usage']}分")
        
        # 信頼度の表示
        confidence = analysis.get('confidence', 0.0)
        if confidence > 0.8:
            details.append(f"分析信頼度: 高 ({confidence:.1%})")
        elif confidence > 0.5:
            details.append(f"分析信頼度: 中 ({confidence:.1%})")
        else:
            details.append(f"分析信頼度: 低 ({confidence:.1%})")
        
        return details

    def generate_simple_conclusion(self, analysis: Dict, recommended_plan: Dict, comparison: Dict) -> str:
        """シンプルで分かりやすい結論を生成"""
        try:
            # 基本情報の取得
            carrier = analysis.get('carrier', 'Unknown')
            current_plan = analysis.get('current_plan', 'Unknown')
            current_cost = analysis['line_cost']
            recommended_cost = recommended_plan['monthly_cost']
            monthly_saving = current_cost - recommended_cost
            
            # キャリア名の日本語化
            carrier_jp = self._get_carrier_japanese_name(carrier)
            
            conclusion_parts = []
            
            # ヘッダー
            conclusion_parts.append("📱 **携帯料金診断結果**")
            conclusion_parts.append("=" * 30)
            
            # 現在の状況
            conclusion_parts.append(f"📋 **現在の状況**")
            conclusion_parts.append(f"キャリア: {carrier_jp}")
            if current_plan != 'Unknown':
                conclusion_parts.append(f"プラン: {current_plan}")
            conclusion_parts.append(f"月額料金: **¥{current_cost:,}**")
            
            # 推奨プラン
            conclusion_parts.append(f"\n🎯 **dモバイル推奨プラン**")
            conclusion_parts.append(f"プラン: {recommended_plan['name']}")
            conclusion_parts.append(f"月額料金: **¥{recommended_cost:,}**")
            
            # 節約効果
            if monthly_saving > 0:
                conclusion_parts.append(f"\n💰 **節約効果**")
                conclusion_parts.append(f"月額節約: **¥{monthly_saving:,}**")
                conclusion_parts.append(f"年間節約: **¥{monthly_saving * 12:,}**")
                conclusion_parts.append(f"50年累積: **¥{monthly_saving * 12 * 50:,}**")
            else:
                conclusion_parts.append(f"\n✅ **診断結果**")
                conclusion_parts.append("現在のプランが最適です！")
            
            # 解析信頼度
            confidence = analysis.get('confidence', 0.0)
            conclusion_parts.append(f"\n🎯 解析信頼度: {confidence:.1%}")
            
            return "\n".join(conclusion_parts)
            
        except Exception as e:
            logger.error(f"Error generating conclusion: {str(e)}")
            return "分析結果の生成中にエラーが発生しました。"
    
    def _get_carrier_japanese_name(self, carrier: str) -> str:
        """キャリア名を日本語に変換"""
        carrier_names = {
            'docomo': 'NTTドコモ',
            'au': 'au (KDDI)',
            'softbank': 'ソフトバンク',
            'rakuten': '楽天モバイル',
            'ymobile': 'ワイモバイル',
            'uq': 'UQ mobile',
            'ahamo': 'ahamo',
            'povo': 'povo',
            'linemo': 'LINEMO'
        }
        return carrier_names.get(carrier.lower(), carrier)
    
    def _initialize_openai_safely(self, api_key: str):
        """OpenAI APIを安全に初期化（環境変数の干渉を完全に回避）"""
        try:
            # 完全にクリーンな環境で初期化
            import subprocess
            import sys
            import tempfile
            import json
            
            # 一時的なPythonスクリプトを作成（バージョン対応）
            script_content = f'''
import os
import sys

# 環境変数をクリア
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy']
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

try:
    import openai
    print(f"OpenAI version: {{getattr(openai, '__version__', 'unknown')}}")
    
    # バージョンに応じた初期化
    if hasattr(openai, 'OpenAI'):
        # v1.0+ の場合
        try:
            client = openai.OpenAI(api_key="{api_key}")
            print("SUCCESS: OpenAI v1.0+ initialized")
        except Exception as e1:
            print(f"ERROR v1.0+: {{str(e1)}}")
            # 古い方法を試行
            openai.api_key = "{api_key}"
            print("SUCCESS: OpenAI legacy method initialized")
    else:
        # v0.x の場合
        openai.api_key = "{api_key}"
        print("SUCCESS: OpenAI v0.x initialized")
        
except Exception as e:
    print(f"ERROR: {{str(e)}}")
    sys.exit(1)
'''
            
            # 一時ファイルにスクリプトを書き込み
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            try:
                # 分離されたプロセスで実行
                logger.info(f"Running isolated process with script: {script_path}")
                result = subprocess.run([sys.executable, script_path], 
                                      capture_output=True, text=True, timeout=30)
                
                logger.info(f"Isolated process stdout: {result.stdout}")
                logger.info(f"Isolated process stderr: {result.stderr}")
                logger.info(f"Isolated process return code: {result.returncode}")
                
                if result.returncode == 0 and "SUCCESS" in result.stdout:
                    logger.info("OpenAI API initialized successfully (isolated process)")
                    # メインプロセスで同様の方法で初期化
                    return self._initialize_openai_with_version_check(api_key)
                else:
                    error_msg = f"Return code: {result.returncode}, stdout: {result.stdout}, stderr: {result.stderr}"
                    logger.error(f"Isolated initialization failed: {error_msg}")
                    raise Exception(f"Isolated process failed: {error_msg}")
                    
            finally:
                # 一時ファイルを削除
                import os
                try:
                    os.unlink(script_path)
                    logger.info(f"Cleaned up temporary script: {script_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup script: {cleanup_error}")
                    
        except Exception as e:
            logger.warning(f"Isolated initialization failed: {str(e)}")
            
            # フォールバック1: 古いAPI形式
            try:
                logger.info("Attempting legacy OpenAI API initialization")
                import openai
                openai.api_key = api_key
                logger.info("OpenAI API initialized successfully (legacy method)")
                return openai
            except Exception as e2:
                logger.warning(f"Legacy initialization failed: {str(e2)}")
                
                # フォールバック2: 環境変数を完全にクリアして再試行
                try:
                    logger.info("Attempting environment-clean initialization")
                    import os
                    
                    # すべての環境変数をバックアップ
                    env_backup = dict(os.environ)
                    
                    # 問題のある環境変数をクリア
                    problematic_vars = [
                        'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
                        'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy',
                        'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE'
                    ]
                    
                    for var in problematic_vars:
                        if var in os.environ:
                            del os.environ[var]
                    
                    # クリーンな環境で初期化
                    from openai import OpenAI
                    client = OpenAI(api_key=api_key)
                    logger.info("OpenAI API initialized successfully (environment-clean method)")
                    
                    # 環境変数を復元
                    os.environ.clear()
                    os.environ.update(env_backup)
                    
                    return client
                    
                except Exception as e3:
                    logger.error(f"Environment-clean initialization also failed: {str(e3)}")
                    
                    # 環境変数を復元
                    try:
                        os.environ.clear()
                        os.environ.update(env_backup)
                    except:
                        pass
                    
                    raise e3
    
    def _initialize_openai_with_version_check(self, api_key: str):
        """バージョンチェック付きOpenAI初期化"""
        try:
            import openai
            version = getattr(openai, '__version__', 'unknown')
            logger.info(f"OpenAI version: {version}")
            
            # バージョンに応じた初期化
            if hasattr(openai, 'OpenAI'):
                # v1.0+ の場合
                try:
                    client = openai.OpenAI(api_key=api_key)
                    logger.info("OpenAI v1.0+ initialized successfully")
                    return client
                except Exception as e1:
                    logger.warning(f"OpenAI v1.0+ failed: {str(e1)}")
                    # 古い方法を試行
                    openai.api_key = api_key
                    logger.info("OpenAI legacy method initialized successfully")
                    logger.info("Testing legacy method with a simple API call...")
                    try:
                        # 簡単なテスト呼び出し
                        test_response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": "test"}],
                            max_tokens=1
                        )
                        logger.info("Legacy method test successful")
                    except Exception as test_e:
                        logger.warning(f"Legacy method test failed: {str(test_e)}")
                    return openai
            else:
                # v0.x の場合
                openai.api_key = api_key
                logger.info("OpenAI v0.x initialized successfully")
                return openai
                
        except Exception as e:
            logger.error(f"Version-specific initialization failed: {str(e)}")
            raise e
    
    def _validate_environment(self):
        """環境変数の検証"""
        try:
            logger.info("Validating environment variables...")
            
            # OpenAI API設定の検証
            if Config.USE_OPENAI_ANALYSIS:
                if not Config.OPENAI_API_KEY:
                    logger.warning("USE_OPENAI_ANALYSIS is True but OPENAI_API_KEY is not set")
                else:
                    logger.info(f"OpenAI API key is set (length: {len(Config.OPENAI_API_KEY)})")
            else:
                logger.info("OpenAI analysis is disabled")
            
            # Google Cloud Vision API設定の検証
            if Config.GOOGLE_APPLICATION_CREDENTIALS:
                logger.info(f"Google Cloud Vision API credentials: {Config.GOOGLE_APPLICATION_CREDENTIALS}")
            else:
                logger.info("Google Cloud Vision API credentials not set")
            
            # Tesseract設定の検証
            tesseract_cmd = os.getenv('TESSERACT_CMD')
            if tesseract_cmd:
                logger.info(f"Tesseract command: {tesseract_cmd}")
            else:
                logger.info("Tesseract command not set (will use auto-detection)")
            
            logger.info("Environment validation completed")
            
        except Exception as e:
            logger.error(f"Error validating environment: {str(e)}")

    def generate_loss_analysis(self, comparison: Dict) -> Dict:
        """損失分析の生成"""
        try:
            monthly_saving = comparison.get('monthly_saving', 0)
            yearly_saving = comparison.get('yearly_saving', 0)
            total_50year = comparison.get('total_50year', 0)
            
            # その金額でできることの例
            examples = {
                'yearly': self._get_yearly_examples(yearly_saving),
                '10year': self._get_10year_examples(yearly_saving * 10),
                '50year': self._get_50year_examples(abs(total_50year))
            }
            
            return {
                'monthly_loss': monthly_saving if monthly_saving > 0 else 0,
                'yearly_loss': yearly_saving if yearly_saving > 0 else 0,
                'total_50year_loss': total_50year if total_50year < 0 else 0,
                'examples': examples
            }
            
        except Exception as e:
            logger.error(f"Error generating loss analysis: {str(e)}")
            return {
                'monthly_loss': 0,
                'yearly_loss': 0,
                'total_50year_loss': 0,
                'examples': {'yearly': 'N/A', '10year': 'N/A', '50year': 'N/A'}
            }

    def _get_yearly_examples(self, amount: int) -> str:
        """年間金額でできることの例"""
        if amount >= 100000:
            return "海外旅行1回"
        elif amount >= 50000:
            return "国内旅行2回"
        elif amount >= 30000:
            return "高級レストラン10回"
        elif amount >= 20000:
            return "新しい服・靴"
        elif amount >= 10000:
            return "映画・コンサート5回"
        else:
            return "ちょっとした贅沢"

    def _get_10year_examples(self, amount: int) -> str:
        """10年金額でできることの例"""
        if amount >= 1000000:
            return "新車購入"
        elif amount >= 500000:
            return "高級腕時計"
        elif amount >= 300000:
            return "海外旅行10回"
        elif amount >= 200000:
            return "高級家電一式"
        elif amount >= 100000:
            return "家具・インテリア"
        else:
            return "趣味・娯楽"

    def _get_50year_examples(self, amount: int) -> str:
        """50年金額でできることの例"""
        if amount >= 5000000:
            return "家の頭金"
        elif amount >= 2000000:
            return "高級車購入"
        elif amount >= 1000000:
            return "海外旅行50回"
        elif amount >= 500000:
            return "高級家具一式"
        elif amount >= 200000:
            return "高級家電・PC"
        else:
            return "趣味・娯楽"

    def generate_dmobile_benefits(self, analysis: Dict) -> List[str]:
        """dモバイルのメリットを生成"""
        benefits = [
            "📶 docomo回線で安定した通信品質",
            "🔄 毎日リセット型データ容量",
            "📞 かけ放題オプション充実",
            "💰 格安料金でdocomo回線を利用",
            "🎯 シンプルで分かりやすい料金体系",
            "📱 最新スマートフォン対応",
            "🌐 全国どこでも快適な通信",
            "💳 クレジットカード決済対応"
        ]
        
        # データ使用量に応じたメリット
        if analysis.get('data_usage', 0) > 10:
            benefits.append("📊 大容量データプランで安心")
        elif analysis.get('data_usage', 0) > 5:
            benefits.append("📊 中容量データプランで十分")
        else:
            benefits.append("📊 小容量データプランで節約")
        
        # 通話使用量に応じたメリット
        if analysis.get('call_usage', 0) > 1000:
            benefits.append("📞 24時間かけ放題オプション推奨")
        elif analysis.get('call_usage', 0) > 500:
            benefits.append("📞 5分かけ放題オプション推奨")
        
        return benefits
    
    def _initialize_openai_without_proxy(self, api_key: str):
        """プロキシ設定を無効化してOpenAI APIを初期化"""
        try:
            import os
            
            # プロキシ関連の環境変数を一時的にクリア
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
            original_values = {}
            
            for var in proxy_vars:
                if var in os.environ:
                    original_values[var] = os.environ[var]
                    del os.environ[var]
            
            try:
                import openai
                from openai import OpenAI
                
                version = getattr(openai, '__version__', 'unknown')
                logger.info(f"OpenAI version: {version}")
                
                # v1.0+の場合は新しいクライアントを使用
                if hasattr(openai, 'OpenAI'):
                    client = OpenAI(api_key=api_key)
                    logger.info("OpenAI v1.0+ client initialized successfully")
                    return client
                else:
                    # v0.xの場合は従来の方法
                    openai.api_key = api_key
                    logger.info("OpenAI v0.x initialized successfully")
                    return openai
                    
            finally:
                # 環境変数を復元
                for var, value in original_values.items():
                    os.environ[var] = value
                    
        except Exception as e:
            logger.error(f"OpenAI initialization without proxy failed: {str(e)}")
            raise e

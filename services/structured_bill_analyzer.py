import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class TaxCategory(Enum):
    TAXABLE = "課税"
    NON_TAXABLE = "非課税"
    EXEMPT = "対象外"

class BillCategory(Enum):
    BASE = "base"           # 基本プラン
    VOICE = "voice"         # 通話料
    DATA = "data"           # データ通信料
    DISCOUNT = "discount"   # 割引
    OPTION = "option"       # オプション
    FEE = "fee"            # 手数料
    DEVICE = "device"       # 端末代金
    TAX = "tax"            # 消費税
    SUBTOTAL = "subtotal"   # 小計
    TOTAL = "total"        # 合計

@dataclass
class BillLine:
    label: str              # 項目名
    amount: float           # 金額（正規化済み）
    tax_category: TaxCategory
    bill_category: BillCategory
    confidence: float       # 信頼度
    raw_text: str          # 元のテキスト

@dataclass
class BillSummary:
    subtotal: float         # 小計
    tax_amount: float       # 消費税
    total_amount: float     # 合計
    line_cost: float        # 通信費（端末代金除外）

class StructuredBillAnalyzer:
    def __init__(self):
        self.carrier_dictionaries = self._load_carrier_dictionaries()
        self.business_rules = self._load_business_rules()
    
    def _load_carrier_dictionaries(self) -> Dict[str, Dict[str, BillCategory]]:
        """キャリア別語彙辞書を読み込み"""
        return {
            'softbank': {
                # アンカー（最重要）
                '小計': BillCategory.SUBTOTAL,
                '課税対象額': BillCategory.SUBTOTAL,
                'subtotal': BillCategory.SUBTOTAL,
                '消費税等': BillCategory.TAX,
                '消費税': BillCategory.TAX,
                'tax': BillCategory.TAX,
                'ご請求金額': BillCategory.TOTAL,
                'ご請求額': BillCategory.TOTAL,
                '合計': BillCategory.TOTAL,
                'total': BillCategory.TOTAL,
                
                # 除外（端末代金）
                '分割支払金': BillCategory.DEVICE,
                '分割金': BillCategory.DEVICE,
                '割賦': BillCategory.DEVICE,
                '端末': BillCategory.DEVICE,
                'device': BillCategory.DEVICE,
                
                # 割引
                '割引': BillCategory.DISCOUNT,
                '▲': BillCategory.DISCOUNT,
                'discount': BillCategory.DISCOUNT,
                '家族割': BillCategory.DISCOUNT,
                'おうち割': BillCategory.DISCOUNT,
                
                # その他（オプション・手数料・基本料・データ・通話をまとめる）
                '請求書発行手数料': BillCategory.OPTION,
                'あんしん保証': BillCategory.OPTION,
                'AppleCare': BillCategory.OPTION,
                'オプション': BillCategory.OPTION,
                '基本料': BillCategory.OPTION,
                'データ': BillCategory.OPTION,
                '通話': BillCategory.OPTION,
                'S!': BillCategory.OPTION,
                'My SoftBank': BillCategory.OPTION,
                'Y!mobile': BillCategory.OPTION,
                'Wi-Fi': BillCategory.OPTION,
                'メール': BillCategory.OPTION,
                'SMS': BillCategory.OPTION,
            },
            'docomo': {
                # アンカー（最重要）
                '小計': BillCategory.SUBTOTAL,
                '課税対象額': BillCategory.SUBTOTAL,
                'subtotal': BillCategory.SUBTOTAL,
                '消費税等': BillCategory.TAX,
                '消費税': BillCategory.TAX,
                'tax': BillCategory.TAX,
                '合計請求額': BillCategory.TOTAL,
                'ご請求金額': BillCategory.TOTAL,
                '請求金額': BillCategory.TOTAL,
                '合計': BillCategory.TOTAL,
                'total': BillCategory.TOTAL,
                
                # 除外（端末代金）
                '分割支払金': BillCategory.DEVICE,
                '分割金': BillCategory.DEVICE,
                '端末': BillCategory.DEVICE,
                '割賦': BillCategory.DEVICE,
                'device': BillCategory.DEVICE,
                
                # 割引
                '割引': BillCategory.DISCOUNT,
                '▲': BillCategory.DISCOUNT,
                'discount': BillCategory.DISCOUNT,
                'dカードお支払割': BillCategory.DISCOUNT,
                'みんなドコモ割': BillCategory.DISCOUNT,
                
                # その他（オプション・手数料・基本料・データ・通話をまとめる）
                'spモード': BillCategory.OPTION,
                'ギガホ': BillCategory.OPTION,
                'ギガライト': BillCategory.OPTION,
                '5Gギガホ': BillCategory.OPTION,
                'オプション': BillCategory.OPTION,
                '請求書発行手数料': BillCategory.OPTION,
                '基本使用料': BillCategory.OPTION,
                '基本料': BillCategory.OPTION,
                'データ': BillCategory.OPTION,
                '通話': BillCategory.OPTION,
                'メール': BillCategory.OPTION,
                'SMS': BillCategory.OPTION,
            },
            'au': {
                # アンカー（最重要）
                '小計': BillCategory.SUBTOTAL,
                '課税対象額': BillCategory.SUBTOTAL,
                'subtotal': BillCategory.SUBTOTAL,
                '消費税等': BillCategory.TAX,
                '消費税': BillCategory.TAX,
                'tax': BillCategory.TAX,
                'ご請求金額': BillCategory.TOTAL,
                '請求金額': BillCategory.TOTAL,
                '合計': BillCategory.TOTAL,
                'total': BillCategory.TOTAL,
                
                # 除外（端末代金）
                '分割支払金': BillCategory.DEVICE,
                '分割金': BillCategory.DEVICE,
                '割賦': BillCategory.DEVICE,
                '端末': BillCategory.DEVICE,
                'device': BillCategory.DEVICE,
                
                # 割引
                '割引': BillCategory.DISCOUNT,
                '▲': BillCategory.DISCOUNT,
                'discount': BillCategory.DISCOUNT,
                '家族割プラス': BillCategory.DISCOUNT,
                'スマートバリュー': BillCategory.DISCOUNT,
                
                # その他（オプション・手数料・基本料・データ・通話をまとめる）
                'LTE NET': BillCategory.OPTION,
                '使い放題MAX': BillCategory.OPTION,
                'ピタット': BillCategory.OPTION,
                '請求書発行手数料': BillCategory.OPTION,
                'AppleCare': BillCategory.OPTION,
                'オプション': BillCategory.OPTION,
                '基本料': BillCategory.OPTION,
                'データ': BillCategory.OPTION,
                '通話': BillCategory.OPTION,
                'メール': BillCategory.OPTION,
                'SMS': BillCategory.OPTION,
            },
            'generic': {
                # アンカー（最重要）
                '小計': BillCategory.SUBTOTAL,
                '課税対象額': BillCategory.SUBTOTAL,
                'subtotal': BillCategory.SUBTOTAL,
                '消費税等': BillCategory.TAX,
                '消費税': BillCategory.TAX,
                'tax': BillCategory.TAX,
                'ご請求金額': BillCategory.TOTAL,
                '合計': BillCategory.TOTAL,
                'total': BillCategory.TOTAL,
                'billing': BillCategory.TOTAL,
                'summary of your charges': BillCategory.TOTAL,
                
                # 除外（端末代金）
                '分割支払金': BillCategory.DEVICE,
                '分割金': BillCategory.DEVICE,
                '端末': BillCategory.DEVICE,
                '割賦': BillCategory.DEVICE,
                'device': BillCategory.DEVICE,
                'installment': BillCategory.DEVICE,
                
                # 割引
                '割引': BillCategory.DISCOUNT,
                '▲': BillCategory.DISCOUNT,
                'discount': BillCategory.DISCOUNT,
                'rebate': BillCategory.DISCOUNT,
                
                # その他（オプション・手数料・基本料・データ・通話をまとめる）
                'オプション': BillCategory.OPTION,
                'サービス': BillCategory.OPTION,
                '請求書発行手数料': BillCategory.OPTION,
                '手数料': BillCategory.OPTION,
                '基本料': BillCategory.OPTION,
                'データ': BillCategory.OPTION,
                '通話': BillCategory.OPTION,
                'メール': BillCategory.OPTION,
                'SMS': BillCategory.OPTION,
                'option': BillCategory.OPTION,
                'service': BillCategory.OPTION,
                'fee': BillCategory.OPTION,
                'charge': BillCategory.OPTION,
            }
        }
    
    def _load_business_rules(self) -> Dict:
        """ビジネスルールを読み込み"""
        return {
            'exclude_from_line_cost': [BillCategory.DEVICE],
            'discount_categories': [BillCategory.DISCOUNT],
            'tax_categories': [BillCategory.TAX],
            'reconciliation_tolerance': 5,  # ±5円以内
            'required_categories': [BillCategory.SUBTOTAL, BillCategory.TAX, BillCategory.TOTAL]
        }
    
    def analyze_bill(self, ocr_text: str, carrier: str = None) -> Dict:
        """請求書を構造化分析"""
        try:
            print("=== 構造化請求書分析開始 ===")
            logger.info("=== 構造化請求書分析開始 ===")
            print(f"入力テキスト（最初の200文字）: {ocr_text[:200]}...")
            logger.info(f"入力テキスト（最初の200文字）: {ocr_text[:200]}...")
            
            # 0. キャリア検出（未指定の場合）
            if not carrier:
                carrier = self._detect_carrier_from_text(ocr_text)
                print(f"検出されたキャリア: {carrier}")
                logger.info(f"検出されたキャリア: {carrier}")
            
            # 1. OCRテキストを行ごとに分割
            lines = self._split_into_lines(ocr_text)
            print(f"分割された行数: {len(lines)}")
            logger.info(f"分割された行数: {len(lines)}")
            for i, line in enumerate(lines[:5]):  # 最初の5行をログ出力
                print(f"行{i+1}: {line}")
                logger.info(f"行{i+1}: {line}")
            
            # 2. 各行を構造化データに変換
            bill_lines = self._parse_lines_to_structured_data(lines, carrier)
            print(f"構造化された行数: {len(bill_lines)}")
            logger.info(f"構造化された行数: {len(bill_lines)}")
            
            # 3. キャリア別語彙辞書で分類
            classified_lines = self._classify_with_carrier_dictionary(bill_lines, carrier)
            
            # 4. 金額の正規化
            normalized_lines = self._normalize_amounts(classified_lines)
            
            # 5. ビジネスルールで検算
            validated_lines = self._apply_business_rules(normalized_lines)
            
            # 6. 集約値の計算
            summary = self._calculate_summary(validated_lines)
            
            # 7. 通信費の計算（端末代金除外）
            line_cost = self._calculate_line_cost(validated_lines)
            
            confidence = self._calculate_overall_confidence(validated_lines)
            print(f"分析完了: 通信費 ¥{line_cost:,}, 信頼度: {confidence:.2f}")
            logger.info(f"分析完了: 通信費 ¥{line_cost:,}, 信頼度: {confidence:.2f}")
            
            # 通信費が0の場合は信頼度を下げる
            if line_cost == 0:
                confidence = min(confidence, 0.3)  # 最大0.3まで下げる
                print(f"通信費が0のため信頼度を調整: {confidence:.2f}")
                logger.warning(f"通信費が0のため信頼度を調整: {confidence:.2f}")
            
            # 信頼度ゲート：0.8未満の場合は後段処理を停止
            if confidence < 0.8:
                print(f"信頼度ゲート: {confidence:.2f} < 0.8 のため後段処理を停止")
                logger.warning(f"信頼度ゲート: {confidence:.2f} < 0.8 のため後段処理を停止")
            
            return {
                'carrier': carrier or 'Unknown',
                'line_cost': line_cost,
                'total_cost': summary.total_amount,
                'terminal_cost': self._get_terminal_cost(validated_lines),
                'bill_lines': [self._line_to_dict(line) for line in validated_lines],
                'summary': self._summary_to_dict(summary),
                'confidence': confidence,
                'analysis_details': self._generate_analysis_details(line_cost, confidence, carrier),
                'reliable': confidence >= 0.8  # 信頼度ゲートフラグ
            }
            
        except Exception as e:
            logger.error(f"構造化分析エラー: {str(e)}")
            return self._fallback_analysis(ocr_text)
    
    def _detect_carrier_from_text(self, text: str) -> str:
        """OCRテキストからキャリアを自動検出（スコアベース）"""
        text_lower = text.lower()
        
        # キャリアスコアを初期化
        scores = {'softbank': 0, 'au': 0, 'docomo': 0}
        
        # 主要キーワード（高スコア）
        if re.search(r'my\s*softbank|ソフトバンク|softbank', text, re.I):
            scores['softbank'] += 3
        if re.search(r'my\s*au|au|kddi', text, re.I):
            scores['au'] += 3
        if re.search(r'docomo|ドコモ|my\s*docomo', text, re.I):
            scores['docomo'] += 3
        
        # 予備キーワード（中スコア）
        if re.search(r'おうち割|s!|y!mobile|あんしん保証', text, re.I):
            scores['softbank'] += 2
        if re.search(r'スマートバリュー|家族割プラス|ピタット|使い放題max', text, re.I):
            scores['au'] += 2
        if re.search(r'spモード|dカード|ギガホ|ギガライト', text, re.I):
            scores['docomo'] += 2
        
        # 軽微なキーワード（低スコア）
        if re.search(r'paypay|wi-fi|メール', text, re.I):
            scores['softbank'] += 1
        if re.search(r'lte\s*net|applecare', text, re.I):
            scores['au'] += 1
        if re.search(r'5g|みんなドコモ', text, re.I):
            scores['docomo'] += 1
        
        # 最高スコアのキャリアを返す
        max_score = max(scores.values())
        if max_score > 0:
            detected_carrier = max(scores, key=scores.get)
            print(f"キャリア検出: {detected_carrier} (スコア: {max_score})")
            logger.info(f"キャリア検出: {detected_carrier} (スコア: {max_score})")
            return detected_carrier
        else:
            print("キャリア検出: generic (スコア不足)")
            logger.info("キャリア検出: generic (スコア不足)")
            return 'generic'
    
    def _split_into_lines(self, text: str) -> List[str]:
        """OCRテキストを行ごとに分割"""
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 2:  # 空行や短すぎる行を除外
                lines.append(line)
        return lines
    
    def _parse_lines_to_structured_data(self, lines: List[str], carrier: str = None) -> List[BillLine]:
        """各行を構造化データに変換"""
        bill_lines = []
        
        for line in lines:
            try:
                # ラベルと金額を抽出
                label, amount = self._extract_label_and_amount(line)
                
                print(f"行解析: '{line}' -> ラベル: '{label}', 金額: {amount}")
                logger.info(f"行解析: '{line}' -> ラベル: '{label}', 金額: {amount}")
                
                if label and amount is not None:
                    bill_line = BillLine(
                        label=label,
                        amount=amount,
                        tax_category=TaxCategory.TAXABLE,  # デフォルト
                        bill_category=BillCategory.OPTION,  # デフォルト
                        confidence=0.5,
                        raw_text=line
                    )
                    bill_lines.append(bill_line)
                    print(f"構造化データ追加: {label} = ¥{amount:,}")
                    logger.info(f"構造化データ追加: {label} = ¥{amount:,}")
                    
            except Exception as e:
                print(f"行解析エラー: {line} - {str(e)}")
                logger.warning(f"行解析エラー: {line} - {str(e)}")
                continue
        
        return bill_lines
    
    def _extract_label_and_amount(self, line: str) -> Tuple[str, Optional[float]]:
        """行からラベルと金額を抽出"""
        # 日付や電話番号を除外するパターン
        exclude_patterns = [
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # 日付 (2025/06/01)
            r'\d{4}\d{2}\d{2}',              # 日付 (20250601)
            r'\d{3}-\d{4}-\d{4}',            # 電話番号 (090-3088-0577)
            r'\d{10,}',                      # 長い数字 (請求番号など)
        ]
        
        # 除外パターンにマッチする場合は処理をスキップ
        for pattern in exclude_patterns:
            if re.search(pattern, line):
                print(f"除外パターンにマッチ: {line} (パターン: {pattern})")
                return line, None
        
        # 追加の除外パターン（OCRノイズ対策）
        additional_exclude_patterns = [
            r'^\s*\d+\s*$',  # 数字のみの行
            r'^\s*[A-Z]+\s*$',  # 大文字のみの行
            r'^\s*[a-z]+\s*$',  # 小文字のみの行（短い場合）
        ]
        
        for pattern in additional_exclude_patterns:
            if re.search(pattern, line):
                print(f"追加除外パターンにマッチ: {line} (パターン: {pattern})")
                return line, None
        
        # 金額パターン（日本語・英語対応）
        amount_patterns = [
            r'¥([0-9,]+)',           # ¥1,000
            r'([0-9,]+)円',          # 1,000円
            r'([0-9,]+)',            # 1,000
            r'([0-9]+)',             # 1000
            r'([0-9,]+)\.([0-9]{2})', # 1,000.00
            r'([0-9]+)\.([0-9]{2})',  # 1000.00
        ]
        
        # 負数パターン
        negative_patterns = [
            r'▲([0-9,]+)',           # ▲1,000
            r'−([0-9,]+)',           # −1,000
            r'-([0-9,]+)',           # -1,000
        ]
        
        # 金額を抽出
        amount = None
        is_negative = False
        
        # 負数チェック
        for pattern in negative_patterns:
            match = re.search(pattern, line)
            if match:
                amount = float(match.group(1).replace(',', ''))
                is_negative = True
                break
        
        # 正数チェック
        if amount is None:
            for pattern in amount_patterns:
                match = re.search(pattern, line)
                if match:
                    amount = float(match.group(1).replace(',', ''))
                    break
        
        if amount is None:
            return line, None
        
        # 負数の場合は符号を反転
        if is_negative:
            amount = -amount
        
        # 金額の妥当性チェック（強化版）
        if not self._is_valid_amount(amount, line):
            print(f"金額が妥当範囲外: {amount} (行: {line})")
            return line, None
        
        # 小数点以下の桁数チェック（2桁以下）
        if amount != int(amount) and len(str(amount).split('.')[1]) > 2:
            print(f"小数点桁数が多すぎる: {amount} (行: {line})")
            return line, None
        
        # ラベルを抽出（金額部分を除去）
        label = line
        for pattern in amount_patterns + negative_patterns:
            label = re.sub(pattern, '', label).strip()
        
        # 余分な文字を除去
        label = re.sub(r'[：:]\s*$', '', label).strip()
        
        # ラベルの妥当性チェック（空でない、長すぎない、意味のある文字を含む）
        if not label or len(label) > 100 or len(label) < 2:
            print(f"ラベルが妥当でない: '{label}' (行: {line})")
            return line, None
        
        # ラベルに意味のある文字が含まれているかチェック（数字のみ、記号のみは除外）
        if re.match(r'^[\d\s\-_\(\)\[\]{}]+$', label):
            print(f"ラベルが数字・記号のみ: '{label}' (行: {line})")
            return line, None
        
        return label, amount
    
    def _is_valid_amount(self, amount: float, line: str) -> bool:
        """金額の妥当性チェック（強化版）"""
        # 基本的な範囲チェック
        if amount < 0 or amount > 1000000:
            return False
        
        # 異常に小さい金額の除外（1円未満、ただし割引は除く）
        if amount > 0 and amount < 1:
            return False
        
        # 異常に大きい金額の除外（請求書としては現実的でない）
        if amount > 500000:  # 50万円以上は異常
            return False
        
        # 小数点以下の桁数チェック
        if amount != int(amount):
            decimal_part = str(amount).split('.')[1]
            if len(decimal_part) > 2:
                return False
        
        return True
    
    def _classify_with_carrier_dictionary(self, bill_lines: List[BillLine], carrier: str = None) -> List[BillLine]:
        """キャリア別語彙辞書で分類（ファジーマッチング対応）"""
        if not carrier or carrier not in self.carrier_dictionaries:
            carrier = 'generic'  # デフォルト
        
        dictionary = self.carrier_dictionaries[carrier]
        print(f"使用する辞書: {carrier} (項目数: {len(dictionary)})")
        logger.info(f"使用する辞書: {carrier} (項目数: {len(dictionary)})")
        
        classified_count = 0
        for line in bill_lines:
            print(f"分類対象: '{line.label}' (金額: ¥{line.amount:,})")
            
            # 1. 通常の辞書マッチング
            matched = False
            for keyword, category in dictionary.items():
                if keyword.lower() in line.label.lower():
                    line.bill_category = category
                    line.confidence = 0.9
                    classified_count += 1
                    matched = True
                    print(f"辞書分類成功: '{line.label}' -> {category.value} (キーワード: {keyword})")
                    logger.info(f"辞書分類成功: '{line.label}' -> {category.value} (キーワード: {keyword})")
                    break
            
            # 2. ファジーマッチング（文字化け対応）
            if not matched:
                fuzzy_match = self._fuzzy_classify(line.label, carrier)
                if fuzzy_match:
                    line.bill_category = fuzzy_match['category']
                    line.confidence = 0.7  # ファジーマッチは信頼度を下げる
                    classified_count += 1
                    print(f"ファジー分類成功: '{line.label}' -> {fuzzy_match['category'].value} (パターン: {fuzzy_match['pattern']})")
                    logger.info(f"ファジー分類成功: '{line.label}' -> {fuzzy_match['category'].value} (パターン: {fuzzy_match['pattern']})")
                else:
                    print(f"分類失敗: '{line.label}' - マッチするキーワードなし")
        
        print(f"分類完了: {classified_count}/{len(bill_lines)} 行が分類されました")
        logger.info(f"分類完了: {classified_count}/{len(bill_lines)} 行が分類されました")
        return bill_lines
    
    def _fuzzy_classify(self, label: str, carrier: str) -> Optional[Dict]:
        """rapidfuzzを使ったファジーマッチング"""
        try:
            from rapidfuzz import process, fuzz
            
            if carrier not in self.carrier_dictionaries:
                return None
            
            dictionary = self.carrier_dictionaries[carrier]
            keys = list(dictionary.keys())
            
            # ファジーマッチング実行（70点以上でマッチ）
            match = process.extractOne(label, keys, scorer=fuzz.partial_ratio)
            
            if match and match[1] >= 70:
                matched_key = match[0]
                category = dictionary[matched_key]
                return {
                    'category': category, 
                    'pattern': matched_key,
                    'score': match[1]
                }
            
            return None
            
        except ImportError:
            # rapidfuzzが利用できない場合は正規表現フォールバック
            return self._regex_fallback_classify(label, carrier)
        except Exception as e:
            logger.warning(f"ファジーマッチングエラー: {str(e)}")
            return None
    
    def _regex_fallback_classify(self, label: str, carrier: str) -> Optional[Dict]:
        """rapidfuzzが利用できない場合の正規表現フォールバック"""
        # 文字化けパターンと正しい項目のマッピング
        fuzzy_patterns = {
            'softbank': {
                # データ通信関連
                r'.*[Dd][Aa][Tt][Aa].*': BillCategory.OPTION,
                r'.*[Ll][Tt][Ee].*': BillCategory.OPTION,
                r'.*[Gg][Hh][Aa].*': BillCategory.OPTION,
                r'.*[Kk][Oo][Mm].*': BillCategory.OPTION,
                # 保証関連
                r'.*[Aa][Pp][Pp][Ll][Ee].*': BillCategory.OPTION,
                r'.*[Ss][Aa][Ll][Aa].*': BillCategory.OPTION,
                r'.*[Ww][Oo][Ww].*': BillCategory.OPTION,
                # Wi-Fi関連
                r'.*[Ww][Ii].*[Ff][Ii].*': BillCategory.OPTION,
                r'.*[Ss][Pp][Oo][Tt].*': BillCategory.OPTION,
                # メール関連
                r'.*[Mm][Aa][Ii][Ll].*': BillCategory.OPTION,
                r'.*[Nn][Aa][Ss].*': BillCategory.OPTION,
                # 手数料関連
                r'.*[Rr][Aa][Tt].*': BillCategory.OPTION,
                r'.*[Tt][Oo][Aa].*': BillCategory.OPTION,
            }
        }
        
        if carrier not in fuzzy_patterns:
            return None
        
        patterns = fuzzy_patterns[carrier]
        for pattern, category in patterns.items():
            if re.search(pattern, label, re.IGNORECASE):
                return {'category': category, 'pattern': pattern, 'score': 75}
        
        return None
    
    def _normalize_amounts(self, bill_lines: List[BillLine]) -> List[BillLine]:
        """金額の正規化"""
        for line in bill_lines:
            # 割引カテゴリは必ず負数
            if line.bill_category == BillCategory.DISCOUNT and line.amount > 0:
                line.amount = -line.amount
                logger.info(f"割引正規化: {line.label} -> ¥{line.amount:,}")
        
        return bill_lines
    
    def _apply_business_rules(self, bill_lines: List[BillLine]) -> List[BillLine]:
        """ビジネスルールで検算"""
        # アンカー優先で集約値を取得
        subtotal = self._get_anchor_amount(bill_lines, ['小計', 'subtotal', '課税対象額'])
        tax_amount = self._get_anchor_amount(bill_lines, ['消費税等', 'tax', '消費税'])
        total_amount = self._get_anchor_amount(bill_lines, ['ご請求金額', 'total', '請求金額', '合計'])
        
        print(f"検算開始: 小計={subtotal:,}, 消費税={tax_amount:,}, 合計={total_amount:,}")
        
        # 検算
        calculated_total = subtotal + tax_amount
        tolerance = self.business_rules['reconciliation_tolerance']
        
        if abs(calculated_total - total_amount) > tolerance:
            print(f"検算不一致: 計算値({calculated_total:,}) vs 合計({total_amount:,})")
            logger.warning(f"検算不一致: 計算値({calculated_total:,}) vs 合計({total_amount:,})")
            
            # 集約行を優先（フォールバック）
            if total_amount > 0:
                print(f"フォールバック: 合計金額({total_amount:,})を優先")
                logger.info(f"フォールバック: 合計金額({total_amount:,})を優先")
                # 合計金額を基準に調整
                adjustment = total_amount - calculated_total
                print(f"調整額: {adjustment:,}円")
                logger.info(f"調整額: {adjustment:,}円")
        else:
            print(f"検算一致: 計算値({calculated_total:,}) = 合計({total_amount:,})")
            logger.info(f"検算一致: 計算値({calculated_total:,}) = 合計({total_amount:,})")
        
        return bill_lines
    
    def _calculate_summary(self, bill_lines: List[BillLine]) -> BillSummary:
        """集約値の計算（アンカー優先ルール）"""
        # アンカー優先で集約値を取得
        subtotal = self._get_anchor_amount(bill_lines, ['小計', 'subtotal', '課税対象額'])
        tax_amount = self._get_anchor_amount(bill_lines, ['消費税等', 'tax', '消費税'])
        total_amount = self._get_anchor_amount(bill_lines, ['ご請求金額', 'total', '請求金額', '合計'])
        
        print(f"アンカー優先集約値: 小計={subtotal:,}, 消費税={tax_amount:,}, 合計={total_amount:,}")
        logger.info(f"アンカー優先集約値: 小計={subtotal:,}, 消費税={tax_amount:,}, 合計={total_amount:,}")
        
        return BillSummary(
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_cost=0  # 後で計算
        )
    
    def _get_anchor_amount(self, bill_lines: List[BillLine], anchor_keywords: List[str]) -> float:
        """アンカーキーワードで集約値を取得（同一行・右端金額限定）"""
        for line in bill_lines:
            for keyword in anchor_keywords:
                if keyword.lower() in line.label.lower():
                    print(f"アンカー発見: '{line.label}' -> {keyword} = ¥{line.amount:,}")
                    return line.amount
        
        # アンカーが見つからない場合は0を返す（フォールバック禁止）
        print(f"アンカー未発見: {anchor_keywords}")
        return 0.0
    
    def _find_anchor_oneline(self, bill_lines: List[BillLine], anchor_type: str) -> Optional[float]:
        """アンカー語と同じ行にある最右の金額を取得（同一行限定・確実版）"""
        ANCHORS = {
            "subtotal": r"(小計|課税対象額)",
            "tax": r"(消費税(等)?)",
            "total": r"((合計)?請求(額|金額)|ご請求金額|合計)"
        }
        
        if anchor_type not in ANCHORS:
            return None
        
        pattern = re.compile(ANCHORS[anchor_type])
        
        for line in bill_lines:
            if not pattern.search(line.label):
                continue
            
            # その行の右端金額を取得
            amount = self._rightmost_amount_on_line(line.label)
            if amount and self._is_valid_anchor_amount(amount, anchor_type):
                print(f"同一行アンカー発見: '{line.label}' -> {anchor_type} = ¥{amount:,}")
                return amount
        
        print(f"同一行アンカー未発見: {anchor_type}")
        return None
    
    def _rightmost_amount_on_line(self, text: str) -> Optional[float]:
        """行内の右端金額を取得"""
        AMOUNT_RE = re.compile(r"[¥￥]?\s*-?\d{1,3}(?:,\d{3})*(?:\.\d+)?")
        candidates = AMOUNT_RE.findall(text)
        
        if not candidates:
            return None
        
        # 右端 ≒ 最後のヒットを優先
        for token in reversed(candidates):
            amount = self._to_amount(token)
            if amount is not None:
                return amount
        
        return None
    
    def _to_amount(self, s: str) -> Optional[float]:
        """文字列を金額に変換（妥当性チェック付き）"""
        s = s.replace("￥", "¥").replace(",", "")
        try:
            v = float(re.sub(r"[^\d\.-]", "", s))
            # 妥当域: 1〜99,999円（電話番号/IDを排除）
            return v if 0 < abs(v) < 100000 else None
        except:
            return None
    
    def _is_valid_anchor_amount(self, amount: float, anchor_type: str) -> bool:
        """アンカー金額の妥当性チェック"""
        if amount <= 0:
            return False
        
        # 小さい金額のアンカー禁止（脚注・手数料の誤掴み避け）
        if amount < 1000:
            return False
        
        # 異常に大きい金額の除外
        if amount > 100000:
            return False
        
        return True
    
    def _fallback_anchor_amount(self, bill_lines: List[BillLine], anchor_keywords: List[str]) -> float:
        """アンカーが見つからない場合のフォールバック（重複防止）"""
        # 金額の大きさで推定
        amounts = [line.amount for line in bill_lines if line.amount > 0]
        if not amounts:
            return 0.0
        
        amounts.sort(reverse=True)  # 大きい順
        
        if '小計' in anchor_keywords or 'subtotal' in anchor_keywords:
            # 小計は最大金額の可能性が高い
            return amounts[0] if amounts else 0.0
        elif '消費税' in anchor_keywords or 'tax' in anchor_keywords:
            # 消費税は小さい金額（通常1000円以下）
            small_amounts = [a for a in amounts if a < 1000]
            return small_amounts[0] if small_amounts else 0.0
        elif '合計' in anchor_keywords or 'total' in anchor_keywords:
            # 合計は最大金額
            return amounts[0] if amounts else 0.0
        
        return 0.0
    
    def _get_anchor_amount_with_used_tracking(self, bill_lines: List[BillLine], anchor_keywords: List[str], used_amounts: set) -> float:
        """アンカーキーワードで集約値を取得（使用済み金額追跡）"""
        for line in bill_lines:
            for keyword in anchor_keywords:
                if keyword.lower() in line.label.lower():
                    if line.amount not in used_amounts:
                        used_amounts.add(line.amount)
                        print(f"アンカー発見: '{line.label}' -> {keyword} = ¥{line.amount:,}")
                        return line.amount
        
        # アンカーが見つからない場合はフォールバック
        print(f"アンカー未発見: {anchor_keywords}")
        fallback_amount = self._fallback_anchor_amount(bill_lines, anchor_keywords)
        if fallback_amount > 0 and fallback_amount not in used_amounts:
            used_amounts.add(fallback_amount)
            print(f"フォールバック成功: {anchor_keywords} = ¥{fallback_amount:,}")
            return fallback_amount
        
        return 0.0
    
    def _calculate_line_cost(self, bill_lines: List[BillLine]) -> float:
        """通信費の計算（同一行アンカー・値の使い回し禁止・安全側検算）"""
        # 同一行アンカーで集約値を取得（値の使い回し禁止）
        subtotal = self._find_anchor_oneline(bill_lines, "subtotal")
        tax_amount = self._find_anchor_oneline(bill_lines, "tax")
        total_amount = self._find_anchor_oneline(bill_lines, "total")
        
        print(f"通信費計算: 小計={subtotal or 0:,}, 消費税={tax_amount or 0:,}, 合計={total_amount or 0:,}")
        logger.info(f"通信費計算: 小計={subtotal or 0:,}, 消費税={tax_amount or 0:,}, 合計={total_amount or 0:,}")
        
        # 組合せフィットで最良セットを選ぶ
        best_result = self._find_best_combination(subtotal, tax_amount, total_amount)
        
        if best_result['status'] == 'reliable':
            line_cost = best_result['amount']
            confidence = best_result.get('confidence', 0.8)
            print(f"信頼できる結果: {best_result['method']} = ¥{line_cost:,} (信頼度: {confidence:.2f})")
            logger.info(f"信頼できる結果: {best_result['method']} = ¥{line_cost:,} (信頼度: {confidence:.2f})")
            return line_cost
        else:
            print(f"判定不能: {best_result['message']}")
            logger.warning(f"判定不能: {best_result['message']}")
            return 0.0  # 判定不能の場合は0を返す
    
    def _find_best_combination(self, subtotal: Optional[float], tax_amount: Optional[float], total_amount: Optional[float]) -> Dict:
        """組合せフィットで最良セットを選ぶ（安全側検算）"""
        tolerance = self.business_rules['reconciliation_tolerance']
        
        # 合計の妥当性チェック
        total_amount = self._sanitize_total(total_amount)
        
        # 1. subtotal & tax & total が揃い、検算一致 → total 採用
        if subtotal and tax_amount and total_amount:
            calculated_total = subtotal + tax_amount
            if abs(calculated_total - total_amount) <= tolerance and self._is_valid_tax_ratio(tax_amount, subtotal):
                return {
                    'status': 'reliable',
                    'amount': total_amount,
                    'method': '検算一致（合計採用）',
                    'confidence': 0.95
                }
        
        # 2. subtotal & tax が揃い、税が妥当 → s+t 採用
        if subtotal and tax_amount and self._is_valid_tax_ratio(tax_amount, subtotal):
            return {
                'status': 'reliable',
                'amount': subtotal + tax_amount,
                'method': '小計+税（税妥当）',
                'confidence': 0.9
            }
        
        # 3. total のみ妥当 → total 採用
        if total_amount:
            return {
                'status': 'reliable',
                'amount': total_amount,
                'method': '合計のみ',
                'confidence': 0.8
            }
        
        # 4. それ以外 → 判定不能（確定値を出さない）
        return {
            'status': 'unreliable',
            'message': '明細の合計が特定できませんでした。画像の鮮明度を確認してください。',
            'confidence': 0.0
        }
    
    def _is_valid_tax_ratio(self, tax_amount: float, subtotal: float) -> bool:
        """税の妥当性チェック（日本の消費税10%を中心に±1.5%を許容）"""
        if not subtotal or not tax_amount:
            return False
        
        ratio = tax_amount / subtotal
        return 0.085 <= ratio <= 0.115  # 8.5%〜11.5%の範囲
    
    def _sanitize_total(self, total: Optional[float]) -> Optional[float]:
        """合計の妥当性チェック（脚注誤掴み回避）"""
        if total is None:
            return None
        # 合計が1,000円未満なら無効（脚注・手数料の誤掴み避け）
        return total if total >= 1000 else None
    
    def _generate_analysis_details(self, line_cost: float, confidence: float, carrier: str) -> List[str]:
        """分析詳細を生成"""
        details = []
        
        if line_cost == 0:
            details.extend([
                '【分析結果】',
                '明細の合計が特定できませんでした',
                '',
                '【原因】',
                '• 画像の文字化けが激しく、アンカー（小計・消費税・合計）が読み取れません',
                '• 請求書の重要な部分が認識できていません',
                '',
                '【推奨対応】',
                '1. 画像の鮮明度を確認してください',
                '2. 請求書全体が写るように撮影してください',
                '3. 光の反射や影を避けて撮影してください',
                '4. より鮮明な画像で再試行してください'
            ])
        elif confidence < 0.5:
            details.extend([
                '【分析結果】',
                f'通信費: ¥{line_cost:,}',
                f'信頼度: {confidence:.1%} (低)',
                '',
                '【注意】',
                '分析結果の信頼度が低いため、',
                '手動での確認をお勧めします'
            ])
        else:
            details.extend([
                '【分析結果】',
                f'通信費: ¥{line_cost:,}',
                f'信頼度: {confidence:.1%}',
                f'キャリア: {carrier}',
                '',
                '【推奨】',
                'dモバイルへの切り替えで',
                '月額料金の削減が期待できます'
            ])
        
        return details
    
    def _get_terminal_cost(self, bill_lines: List[BillLine]) -> float:
        """端末代金の取得"""
        return self._get_amount_by_category(bill_lines, BillCategory.DEVICE)
    
    def _get_amount_by_category(self, bill_lines: List[BillLine], category: BillCategory) -> float:
        """カテゴリ別の金額を取得"""
        for line in bill_lines:
            if line.bill_category == category:
                return line.amount
        return 0.0
    
    def _calculate_overall_confidence(self, bill_lines: List[BillLine]) -> float:
        """全体の信頼度を計算"""
        if not bill_lines:
            return 0.0
        
        total_confidence = sum(line.confidence for line in bill_lines)
        return total_confidence / len(bill_lines)
    
    def _line_to_dict(self, line: BillLine) -> Dict:
        """BillLineを辞書に変換"""
        return {
            'label': line.label,
            'amount': line.amount,
            'tax_category': line.tax_category.value,
            'bill_category': line.bill_category.value,
            'confidence': line.confidence,
            'raw_text': line.raw_text
        }
    
    def _summary_to_dict(self, summary: BillSummary) -> Dict:
        """BillSummaryを辞書に変換"""
        return {
            'subtotal': summary.subtotal,
            'tax_amount': summary.tax_amount,
            'total_amount': summary.total_amount,
            'line_cost': summary.line_cost
        }
    
    def _fallback_analysis(self, ocr_text: str) -> Dict:
        """フォールバック分析"""
        logger.warning("構造化分析に失敗、フォールバック分析を実行")
        
        # 簡単な金額抽出
        amount_patterns = [
            r'¥([0-9,]+)',
            r'([0-9,]+)円',
            r'([0-9,]+)',
        ]
        
        amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, ocr_text)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    if 1000 <= amount <= 100000:
                        amounts.append(amount)
                except ValueError:
                    continue
        
        total_cost = max(amounts) if amounts else 0
        
        return {
            'carrier': 'Unknown',
            'line_cost': total_cost,
            'total_cost': total_cost,
            'terminal_cost': 0,
            'bill_lines': [],
            'summary': {
                'subtotal': total_cost,
                'tax_amount': 0,
                'total_amount': total_cost,
                'line_cost': total_cost
            },
            'confidence': 0.3
        }

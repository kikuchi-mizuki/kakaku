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
                'あんしん保証': BillCategory.OPTION,
                'My SoftBank': BillCategory.OPTION,
                '請求書発行手数料': BillCategory.FEE,
                'スマートフォン基本料': BillCategory.BASE,
                'データ通信料': BillCategory.DATA,
                '通話料': BillCategory.VOICE,
                '家族割': BillCategory.DISCOUNT,
                '端末分割金': BillCategory.DEVICE,
                '消費税等': BillCategory.TAX,
                '小計': BillCategory.SUBTOTAL,
                'ご請求金額': BillCategory.TOTAL
            },
            'docomo': {
                'spモード': BillCategory.OPTION,
                'dカードお支払割': BillCategory.DISCOUNT,
                '基本料金': BillCategory.BASE,
                'データ通信料': BillCategory.DATA,
                '通話料': BillCategory.VOICE,
                '家族割引': BillCategory.DISCOUNT,
                '端末代金': BillCategory.DEVICE,
                '消費税等': BillCategory.TAX,
                '小計': BillCategory.SUBTOTAL,
                'ご請求金額': BillCategory.TOTAL
            },
            'au': {
                '家族割プラス': BillCategory.DISCOUNT,
                'スマートバリュー': BillCategory.DISCOUNT,
                '基本料金': BillCategory.BASE,
                'データ通信料': BillCategory.DATA,
                '通話料': BillCategory.VOICE,
                '端末代金': BillCategory.DEVICE,
                '消費税等': BillCategory.TAX,
                '小計': BillCategory.SUBTOTAL,
                'ご請求金額': BillCategory.TOTAL
            },
            'rakuten': {
                '楽天モバイル': BillCategory.BASE,
                'データ通信料': BillCategory.DATA,
                '通話料': BillCategory.VOICE,
                '端末代金': BillCategory.DEVICE,
                '消費税等': BillCategory.TAX,
                '小計': BillCategory.SUBTOTAL,
                'ご請求金額': BillCategory.TOTAL
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
            logger.info("=== 構造化請求書分析開始 ===")
            
            # 1. OCRテキストを行ごとに分割
            lines = self._split_into_lines(ocr_text)
            logger.info(f"分割された行数: {len(lines)}")
            
            # 2. 各行を構造化データに変換
            bill_lines = self._parse_lines_to_structured_data(lines, carrier)
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
            
            logger.info(f"分析完了: 通信費 ¥{line_cost:,}")
            
            return {
                'carrier': carrier or 'Unknown',
                'line_cost': line_cost,
                'total_cost': summary.total_amount,
                'terminal_cost': self._get_terminal_cost(validated_lines),
                'bill_lines': [self._line_to_dict(line) for line in validated_lines],
                'summary': self._summary_to_dict(summary),
                'confidence': self._calculate_overall_confidence(validated_lines)
            }
            
        except Exception as e:
            logger.error(f"構造化分析エラー: {str(e)}")
            return self._fallback_analysis(ocr_text)
    
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
                    logger.info(f"行解析: {label} = ¥{amount:,}")
                    
            except Exception as e:
                logger.warning(f"行解析エラー: {line} - {str(e)}")
                continue
        
        return bill_lines
    
    def _extract_label_and_amount(self, line: str) -> Tuple[str, Optional[float]]:
        """行からラベルと金額を抽出"""
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
        
        # ラベルを抽出（金額部分を除去）
        label = line
        for pattern in amount_patterns + negative_patterns:
            label = re.sub(pattern, '', label).strip()
        
        # 余分な文字を除去
        label = re.sub(r'[：:]\s*$', '', label).strip()
        
        return label, amount
    
    def _classify_with_carrier_dictionary(self, bill_lines: List[BillLine], carrier: str = None) -> List[BillLine]:
        """キャリア別語彙辞書で分類"""
        if not carrier or carrier not in self.carrier_dictionaries:
            carrier = 'docomo'  # デフォルト
        
        dictionary = self.carrier_dictionaries[carrier]
        
        for line in bill_lines:
            # 辞書で分類
            for keyword, category in dictionary.items():
                if keyword in line.label:
                    line.bill_category = category
                    line.confidence = 0.9
                    logger.info(f"辞書分類: {line.label} -> {category.value}")
                    break
        
        return bill_lines
    
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
        # 集約値の検証
        subtotal = self._get_amount_by_category(bill_lines, BillCategory.SUBTOTAL)
        tax_amount = self._get_amount_by_category(bill_lines, BillCategory.TAX)
        total_amount = self._get_amount_by_category(bill_lines, BillCategory.TOTAL)
        
        # 検算
        calculated_total = subtotal + tax_amount
        tolerance = self.business_rules['reconciliation_tolerance']
        
        if abs(calculated_total - total_amount) > tolerance:
            logger.warning(f"検算不一致: 計算値({calculated_total:,}) vs 合計({total_amount:,})")
            # 集約行を優先
            if total_amount > 0:
                # 合計金額を基準に調整
                adjustment = total_amount - calculated_total
                logger.info(f"調整: {adjustment:,}円")
        
        return bill_lines
    
    def _calculate_summary(self, bill_lines: List[BillLine]) -> BillSummary:
        """集約値の計算"""
        subtotal = self._get_amount_by_category(bill_lines, BillCategory.SUBTOTAL)
        tax_amount = self._get_amount_by_category(bill_lines, BillCategory.TAX)
        total_amount = self._get_amount_by_category(bill_lines, BillCategory.TOTAL)
        
        return BillSummary(
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_cost=0  # 後で計算
        )
    
    def _calculate_line_cost(self, bill_lines: List[BillLine]) -> float:
        """通信費の計算（端末代金除外）"""
        exclude_categories = self.business_rules['exclude_from_line_cost']
        
        line_cost = 0
        for line in bill_lines:
            if line.bill_category not in exclude_categories:
                line_cost += line.amount
        
        return max(0, line_cost)  # 負数は0に
    
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

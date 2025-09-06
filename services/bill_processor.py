import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BillLine:
    """請求明細の1行を表すクラス"""
    text: str
    amount: Optional[int] = None
    category: Optional[str] = None
    phone_number: Optional[str] = None

class BillProcessor:
    def __init__(self):
        # 電話番号の正規表現パターン
        self.phone_patterns = [
            r'0[789]0-?\d{4}-?\d{4}',  # 携帯電話
            r'0\d{1,4}-?\d{1,4}-?\d{4}',  # 固定電話
            r'\d{3}-?\d{4}-?\d{4}',  # 市外局番なし
        ]
        
        # 回線費用のキーワード（採用）
        self.included_keywords = {
            'basic': ['基本料', '基本料金', '月額料金', 'プラン料金', '音声プラン', 'データプラン'],
            'data': ['データ通信', '通信料', 'パケット通信', 'データ定額', '通信定額'],
            'voice': ['通話料', '音声通話', '通話従量', '通話料金'],
            'voice_option': ['通話定額', '定額通話', 'かけ放題', '通話オプション', '音声オプション', '準定額', '5分かけ放題', '10分かけ放題', '24時間かけ放題'],
            'discount': ['割引', '家族割', 'セット割', '学割', '学生割', 'シニア割', '障害者割']
        }
        
        # 除外するキーワード
        self.excluded_keywords = [
            '端末', 'スマートフォン', 'iPhone', 'Android', '機種代', '端末代',
            '分割', '一括', '頭金', '事務手数料', '事務費', '手数料',
            '保証', 'AppleCare', '修理', '交換', 'アクセサリ', 'ケース',
            '充電器', 'イヤホン', 'カバー', 'フィルム', 'ストラップ'
        ]
        
        # 金額の正規表現
        self.amount_pattern = r'[¥￥]?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        
        # 小計・合計のキーワード
        self.total_keywords = ['小計', '合計', '請求金額', '請求額', '総額', '計']
    
    def process_bill(self, ocr_result: Dict) -> Dict:
        """請求書を処理して回線費用を抽出"""
        try:
            text = ocr_result.get('text', '')
            blocks = ocr_result.get('blocks', [])
            
            # 家族明細の分割
            family_blocks = self._split_family_bill(text, blocks)
            
            # 各ブロックを処理
            processed_blocks = []
            for block in family_blocks:
                processed_block = self._process_single_bill(block)
                if processed_block:
                    processed_blocks.append(processed_block)
            
            # 最も適切なブロックを選択（またはユーザーに選択させる）
            selected_block = self._select_best_block(processed_blocks)
            
            return selected_block
            
        except Exception as e:
            logger.error(f"Error processing bill: {str(e)}")
            return {
                'total_cost': 0,
                'breakdown': {},
                'phone_number': None,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _split_family_bill(self, text: str, blocks: List[Dict]) -> List[Dict]:
        """家族明細を分割"""
        try:
            # 電話番号で分割
            phone_numbers = self._extract_phone_numbers(text)
            
            if len(phone_numbers) <= 1:
                # 単一回線の場合
                return [{'text': text, 'blocks': blocks, 'phone_number': phone_numbers[0] if phone_numbers else None}]
            
            # 複数回線の場合、電話番号ごとに分割
            family_blocks = []
            for phone in phone_numbers:
                # 電話番号周辺のテキストを抽出
                phone_block = self._extract_phone_block(text, phone)
                if phone_block:
                    family_blocks.append({
                        'text': phone_block,
                        'blocks': [],  # 簡易実装
                        'phone_number': phone
                    })
            
            return family_blocks
            
        except Exception as e:
            logger.error(f"Error splitting family bill: {str(e)}")
            return [{'text': text, 'blocks': blocks, 'phone_number': None}]
    
    def _extract_phone_numbers(self, text: str) -> List[str]:
        """テキストから電話番号を抽出"""
        phone_numbers = []
        for pattern in self.phone_patterns:
            matches = re.findall(pattern, text)
            phone_numbers.extend(matches)
        
        # 重複を除去
        return list(set(phone_numbers))
    
    def _extract_phone_block(self, text: str, phone_number: str) -> str:
        """電話番号周辺のテキストブロックを抽出"""
        try:
            # 電話番号の位置を取得
            phone_pos = text.find(phone_number)
            if phone_pos == -1:
                return ""
            
            # 前後のテキストを抽出（簡易実装）
            start = max(0, phone_pos - 500)
            end = min(len(text), phone_pos + 1000)
            
            return text[start:end]
            
        except Exception as e:
            logger.error(f"Error extracting phone block: {str(e)}")
            return ""
    
    def _process_single_bill(self, block: Dict) -> Optional[Dict]:
        """単一の請求書ブロックを処理"""
        try:
            text = block['text']
            phone_number = block.get('phone_number')
            
            # 行ごとに分割
            lines = text.split('\n')
            bill_lines = []
            
            for line in lines:
                if line.strip():
                    bill_line = self._parse_bill_line(line)
                    if bill_line:
                        bill_lines.append(bill_line)
            
            # 回線費用を抽出
            total_cost, breakdown = self._extract_line_costs(bill_lines)
            
            return {
                'total_cost': total_cost,
                'breakdown': breakdown,
                'phone_number': phone_number,
                'confidence': self._calculate_confidence(bill_lines),
                'raw_lines': bill_lines
            }
            
        except Exception as e:
            logger.error(f"Error processing single bill: {str(e)}")
            return None
    
    def _parse_bill_line(self, line: str) -> Optional[BillLine]:
        """請求明細の1行を解析"""
        try:
            line = line.strip()
            if not line:
                return None
            
            # 金額を抽出
            amount_match = re.search(self.amount_pattern, line)
            amount = None
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                try:
                    amount = int(float(amount_str))
                except ValueError:
                    pass
            
            # カテゴリを判定
            category = self._categorize_line(line)
            
            return BillLine(
                text=line,
                amount=amount,
                category=category
            )
            
        except Exception as e:
            logger.error(f"Error parsing bill line: {str(e)}")
            return None
    
    def _categorize_line(self, line: str) -> Optional[str]:
        """行のカテゴリを判定"""
        line_lower = line.lower()
        
        # 除外キーワードをチェック
        for keyword in self.excluded_keywords:
            if keyword in line_lower:
                return 'excluded'
        
        # 採用キーワードをチェック
        for category, keywords in self.included_keywords.items():
            for keyword in keywords:
                if keyword in line_lower:
                    return category
        
        # 小計・合計をチェック
        for keyword in self.total_keywords:
            if keyword in line_lower:
                return 'total'
        
        return None
    
    def _extract_line_costs(self, bill_lines: List[BillLine]) -> Tuple[int, Dict]:
        """回線費用を抽出"""
        total_cost = 0
        breakdown = {
            'basic': 0,
            'data': 0,
            'voice': 0,
            'voice_option': 0,
            'discount': 0,
            'excluded': 0
        }
        
        for line in bill_lines:
            if line.category and line.amount:
                if line.category == 'excluded':
                    breakdown['excluded'] += line.amount
                elif line.category in breakdown:
                    breakdown[line.category] += line.amount
                    total_cost += line.amount
                elif line.category == 'total':
                    # 小計・合計の場合は、既存の合計と比較
                    if abs(line.amount - total_cost) < 1000:  # 1000円以内の差なら採用
                        total_cost = line.amount
        
        return total_cost, breakdown
    
    def _select_best_block(self, blocks: List[Dict]) -> Dict:
        """最適なブロックを選択"""
        if not blocks:
            return {
                'total_cost': 0,
                'breakdown': {},
                'phone_number': None,
                'confidence': 0.0,
                'error': 'No valid blocks found'
            }
        
        if len(blocks) == 1:
            return blocks[0]
        
        # 複数ブロックがある場合、信頼度が最も高いものを選択
        best_block = max(blocks, key=lambda x: x.get('confidence', 0))
        
        # 将来的にはユーザーに選択させるUIを実装
        logger.info(f"Multiple blocks found, selected block with confidence: {best_block.get('confidence', 0)}")
        
        return best_block
    
    def _calculate_confidence(self, bill_lines: List[BillLine]) -> float:
        """信頼度を計算"""
        if not bill_lines:
            return 0.0
        
        # 金額が抽出できた行の割合
        lines_with_amount = sum(1 for line in bill_lines if line.amount is not None)
        amount_ratio = lines_with_amount / len(bill_lines)
        
        # カテゴリが判定できた行の割合
        lines_with_category = sum(1 for line in bill_lines if line.category is not None)
        category_ratio = lines_with_category / len(bill_lines)
        
        # 回線費用らしい行の割合
        line_cost_lines = sum(1 for line in bill_lines if line.category and line.category != 'excluded')
        line_cost_ratio = line_cost_lines / len(bill_lines) if bill_lines else 0
        
        # 総合信頼度
        confidence = (amount_ratio * 0.4 + category_ratio * 0.3 + line_cost_ratio * 0.3)
        
        return min(confidence, 1.0)

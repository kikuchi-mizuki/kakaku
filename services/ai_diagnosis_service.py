import logging
import re
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AIDiagnosisService:
    """AI診断サービス - 携帯料金の詳細分析と提案"""
    
    def __init__(self):
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
        """AI診断による請求書分析"""
        try:
            logger.info("Starting AI diagnosis of bill")
            
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
            
            logger.info(f"AI diagnosis completed: {analysis_result['carrier']}, Line cost: ¥{analysis_result['line_cost']:,}")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in AI diagnosis: {str(e)}")
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
        """キャリアの検出"""
        text_lower = text.lower()
        
        for carrier, patterns in self.carrier_patterns.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return carrier
        
        return 'Unknown'

    def _extract_current_plan(self, text: str) -> str:
        """現在のプランの抽出"""
        # プラン名のパターンを検索
        plan_patterns = [
            r'プラン[：:]\s*([^\n\r]+)',
            r'料金プラン[：:]\s*([^\n\r]+)',
            r'([A-Za-z0-9]+プラン)',
            r'([A-Za-z0-9]+コース)',
            r'([A-Za-z0-9]+パック)'
        ]
        
        for pattern in plan_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        
        return 'Unknown Plan'

    def _extract_line_cost(self, text: str) -> int:
        """回線費用の抽出（端末代金を除外）"""
        # 金額のパターンを検索
        amount_patterns = [
            r'¥([0-9,]+)',
            r'([0-9,]+)円',
            r'([0-9,]+)'
        ]
        
        line_costs = []
        
        # 回線費用に関連するキーワードの周辺から金額を抽出
        for keyword in self.line_cost_keywords:
            pattern = f'{keyword}[：:]*\s*¥?([0-9,]+)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    cost = int(match.replace(',', ''))
                    if 100 <= cost <= 100000:  # 妥当な範囲の金額
                        line_costs.append(cost)
                except ValueError:
                    continue
        
        # 端末代金を除外
        terminal_costs = self._extract_terminal_cost(text)
        
        # 回線費用の合計を計算（端末代金を除外）
        total_line_cost = sum(line_costs)
        if terminal_costs > 0:
            total_line_cost = max(0, total_line_cost - terminal_costs)
        
        return total_line_cost

    def _extract_terminal_cost(self, text: str) -> int:
        """端末代金の抽出"""
        terminal_costs = []
        
        for keyword in self.terminal_keywords:
            pattern = f'{keyword}[：:]*\s*¥?([0-9,]+)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    cost = int(match.replace(',', ''))
                    if 1000 <= cost <= 200000:  # 端末代金の妥当な範囲
                        terminal_costs.append(cost)
                except ValueError:
                    continue
        
        return sum(terminal_costs)

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
        """分析の信頼度を計算"""
        confidence = 0.0
        
        # キャリアが検出された場合
        if analysis['carrier'] != 'Unknown':
            confidence += 0.3
        
        # 回線費用が検出された場合
        if analysis['line_cost'] > 0:
            confidence += 0.4
        
        # プランが検出された場合
        if analysis['current_plan'] != 'Unknown Plan':
            confidence += 0.2
        
        # データ使用量が検出された場合
        if analysis['data_usage'] > 0:
            confidence += 0.1
        
        return min(confidence, 1.0)

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
        
        return details

    def generate_simple_conclusion(self, analysis: Dict, recommended_plan: Dict, comparison: Dict) -> str:
        """シンプルで分かりやすい結論を生成"""
        try:
            current_cost = analysis['line_cost']
            recommended_cost = recommended_plan['monthly_cost']
            monthly_saving = current_cost - recommended_cost
            
            if monthly_saving > 0:
                conclusion = f"💰 月額¥{monthly_saving:,}節約できます！\n"
                conclusion += f"現在: ¥{current_cost:,} → おすすめ: ¥{recommended_cost:,}\n"
                conclusion += f"年間で¥{monthly_saving * 12:,}の節約になります。"
            else:
                conclusion = f"現在のプランが最適です。\n"
                conclusion += f"現在: ¥{current_cost:,} → おすすめ: ¥{recommended_cost:,}"
            
            return conclusion
            
        except Exception as e:
            logger.error(f"Error generating conclusion: {str(e)}")
            return "分析結果の生成中にエラーが発生しました。"

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
        
        return benefits[:6]  # 最大6個のメリットを返す

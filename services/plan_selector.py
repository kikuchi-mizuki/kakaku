import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Plan:
    """プラン情報を表すクラス"""
    name: str
    monthly_cost: int
    data_limit: str
    voice_option: str
    features: List[str]
    description: str

class PlanSelector:
    def __init__(self):
        # dモバイルのプラン情報（2024年最新）
        self.plans = {
            'X': Plan(
                name='dモバイル X',
                monthly_cost=5720,  # 税込
                data_limit='1日4GB / 月間120GB相当',
                voice_option='オプション追加可能',
                features=['docomo回線', '毎日リセット型容量', '大容量データ'],
                description='大容量データユーザー向けのプレミアムプラン'
            ),
            'L': Plan(
                name='dモバイル L',
                monthly_cost=5720,  # 税込
                data_limit='1日2GB / 月間60GB相当',
                voice_option='24時間かけ放題標準付帯',
                features=['docomo回線', '毎日リセット型容量', '24時間かけ放題'],
                description='通話重視ユーザー向けのプラン'
            ),
            'M': Plan(
                name='dモバイル M',
                monthly_cost=3520,  # 税込
                data_limit='1日1GB / 月間30GB相当',
                voice_option='5分かけ放題標準付帯',
                features=['docomo回線', '毎日リセット型容量', '5分かけ放題'],
                description='中量データユーザー向けのバランス型プラン'
            ),
            'S': Plan(
                name='dモバイル S',
                monthly_cost=1078,  # 税込
                data_limit='月間3GB',
                voice_option='オプション追加可能',
                features=['docomo回線', '月間容量制限', '低価格'],
                description='軽量データユーザー向けのエントリープラン'
            )
        }
        
        # オプション料金（税込）
        self.voice_options = {
            '24h_unlimited': 1870,  # 24時間かけ放題オプション
            '10min_unlimited': 935,  # 10分かけ放題オプション
            '5min_unlimited': 715,  # 5分かけ放題オプション
        }
    
    def select_plan(self, bill_data: Dict) -> Dict:
        """請求書データから最適なプランを選択（基本はLプラン推奨）"""
        try:
            current_cost = bill_data.get('total_cost', 0)
            breakdown = bill_data.get('breakdown', {})
            
            # 特徴量を抽出
            features = self._extract_features(bill_data)
            
            # プラン選択ロジック
            best_plan, selection_reason = self._select_optimal_plan(features, bill_data)
            
            return {
                'name': best_plan.name,
                'monthly_cost': best_plan.monthly_cost,
                'data_limit': best_plan.data_limit,
                'voice_option': best_plan.voice_option,
                'features': best_plan.features,
                'description': best_plan.description,
                'alternatives': self._get_alternatives(best_plan),  # 代替案（Sプラン除外）
                'selection_reason': selection_reason
            }
            
        except Exception as e:
            logger.error(f"Error selecting plan: {str(e)}")
            # デフォルトでLプランを返す
            return {
                'name': self.plans['L'].name,
                'monthly_cost': self.plans['L'].monthly_cost,
                'data_limit': self.plans['L'].data_limit,
                'voice_option': self.plans['L'].voice_option,
                'features': self.plans['L'].features,
                'description': self.plans['L'].description,
                'alternatives': [],
                'selection_reason': 'デフォルト選択（解析エラー）'
            }
    
    def _extract_features(self, bill_data: Dict) -> Dict:
        """請求書から特徴量を抽出"""
        breakdown = bill_data.get('breakdown', {})
        current_cost = bill_data.get('total_cost', 0)
        data_usage = bill_data.get('data_usage', 0)  # GB
        call_usage = bill_data.get('call_usage', 0)  # 分
        
        features = {
            'current_cost': current_cost,
            'data_usage': data_usage,
            'call_usage': call_usage,
            'has_voice_option': breakdown.get('voice_option', 0) > 0,
            'has_24h_unlimited': False,  # 24時間かけ放題の判定
            'has_10min_unlimited': False,  # 10分かけ放題の判定
            'has_5min_unlimited': False,  # 5分かけ放題の判定
            'voice_cost_high': breakdown.get('voice', 0) > 2000,  # 通話料が高い
            'data_cost_high': breakdown.get('data', 0) > 3000 or data_usage > 60,  # データ通信料が高い or 60GB以上
            'has_discount': breakdown.get('discount', 0) < 0,  # 割引がある
            'cost_level': self._get_cost_level(current_cost)
        }
        
        # 音声オプションの詳細判定（簡易実装）
        voice_option_cost = breakdown.get('voice_option', 0)
        if voice_option_cost > 800:
            features['has_24h_unlimited'] = True
        elif voice_option_cost > 400:
            features['has_10min_unlimited'] = True
        elif voice_option_cost > 0:
            features['has_5min_unlimited'] = True
        
        return features
    
    def _get_cost_level(self, cost: int) -> str:
        """コストレベルを判定"""
        if cost < 3000:
            return 'low'
        elif cost < 5000:
            return 'medium'
        else:
            return 'high'
    
    def _select_optimal_plan(self, features: Dict, bill_data: Dict) -> tuple:
        """最適なプランを選択（基本はLプラン推奨）"""
        data_usage = bill_data.get('data_usage', 0)  # GB
        call_usage = bill_data.get('call_usage', 0)  # 分
        voice_cost = bill_data.get('breakdown', {}).get('voice', 0)
        
        # 1. 電話を一切使わない場合 → Mプラン
        if call_usage == 0 and voice_cost == 0:
            return self.plans['M'], "通話を使用しないためMプランを推奨"
        
        # 2. データ使用量が多い場合（月間60GB以上相当） → Xプラン
        if data_usage > 60 or features.get('data_cost_high', False):
            return self.plans['X'], "大容量データ使用のためXプランを推奨"
        
        # 3. その他の場合（基本） → Lプラン
        return self.plans['L'], "バランスの良いLプランを推奨"
    
    def _select_plans_by_features(self, features: Dict, current_cost: int) -> List[Plan]:
        """特徴量に基づいてプランを選択（Sプラン除外）"""
        candidates = []
        
        # ルールベースの選定ロジック（Sプランは除外）
        
        # 1. 大容量データユーザー（通信料高額 or 高コスト）
        if features['data_cost_high'] or features['cost_level'] == 'high':
            candidates.append(self.plans['X'])
            candidates.append(self.plans['L'])
            candidates.append(self.plans['M'])
        
        # 2. 中程度のコストユーザー
        elif features['cost_level'] == 'medium':
            candidates.append(self.plans['L'])
            candidates.append(self.plans['M'])
            candidates.append(self.plans['X'])
        
        # 3. 低コストユーザー
        else:
            candidates.append(self.plans['M'])
            candidates.append(self.plans['L'])
        
        # 重複を除去
        unique_candidates = []
        seen_names = set()
        for plan in candidates:
            if plan.name not in seen_names:
                unique_candidates.append(plan)
                seen_names.add(plan.name)
        
        return unique_candidates
    
    def _needs_24h_unlimited(self, features: Dict, bill_data: Dict) -> bool:
        """24時間かけ放題が必要かどうかを判定"""
        # 通話料が高額な場合
        if features.get('voice_cost_high', False):
            return True
        
        # 既に24時間かけ放題を使用している場合
        if features.get('has_24h_unlimited', False):
            return True
        
        # 通話時間が多い場合（推定）
        call_usage = bill_data.get('call_usage', 0)
        if call_usage > 1000:  # 1000分以上
            return True
        
        # 通話料金が月額2000円以上の場合
        voice_cost = bill_data.get('breakdown', {}).get('voice', 0)
        if voice_cost > 2000:
            return True
        
        return False
    
    def _get_alternatives(self, selected_plan: Plan) -> List[str]:
        """代替案を取得（Sプラン除外）"""
        alternatives = []
        
        # 選択されたプラン以外のプランを代替案として追加（Sプランは除外）
        for plan_key, plan in self.plans.items():
            if plan.name != selected_plan.name and plan_key != 'S':
                alternatives.append(plan.name)
        
        return alternatives[:2]  # 最大2つまで
    
    def _get_selection_reason(self, features: Dict, selected_plan: Plan) -> str:
        """選択理由を生成"""
        reasons = []
        
        if features['has_24h_unlimited'] or features['voice_cost_high']:
            reasons.append("通話料金が高額のため")
        
        if features['data_cost_high']:
            reasons.append("データ通信料が高額のため")
        
        if features['cost_level'] == 'high':
            reasons.append("現在の料金が高額のため")
        
        if selected_plan.name == 'dモバイル X':
            reasons.append("大容量データプランを推奨")
        elif selected_plan.name == 'dモバイル L':
            reasons.append("通話重視プランを推奨")
        elif selected_plan.name == 'dモバイル M':
            reasons.append("バランス型プランを推奨")
        
        if not reasons:
            reasons.append("現在の利用状況に最適なプランを推奨")
        
        return "、".join(reasons)
    
    def get_all_plans(self) -> List[Dict]:
        """全プラン情報を取得"""
        return [
            {
                'name': plan.name,
                'monthly_cost': plan.monthly_cost,
                'data_limit': plan.data_limit,
                'voice_option': plan.voice_option,
                'features': plan.features,
                'description': plan.description
            }
            for plan in self.plans.values()
        ]
    
    def calculate_plan_cost(self, plan_name: str, add_24h_option: bool = False) -> int:
        """プランの月額料金を計算"""
        # プラン名からキーを検索
        plan_key = None
        for key, plan in self.plans.items():
            if plan.name == plan_name:
                plan_key = key
                break
        
        if plan_key is None:
            return 0
        
        base_cost = self.plans[plan_key].monthly_cost
        
        # Lプランは既に24時間かけ放題が標準付帯されているため、オプション追加は不要
        if add_24h_option and plan_key != 'L' and '24時間かけ放題' not in plan_name:
            base_cost += self.voice_options['24h_unlimited']
        
        return base_cost

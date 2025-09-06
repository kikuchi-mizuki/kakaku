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
        # dモバイルのプラン情報（2024年時点）
        self.plans = {
            'M': Plan(
                name='dモバイル M',
                monthly_cost=2980,
                data_limit='1日2GB',
                voice_option='5分かけ放題',
                features=['docomo回線', '毎日リセット型容量', '5分かけ放題'],
                description='中量データユーザー向けのバランス型プラン'
            ),
            'L': Plan(
                name='dモバイル L',
                monthly_cost=3980,
                data_limit='1日4GB',
                voice_option='5分かけ放題',
                features=['docomo回線', '毎日リセット型容量', '5分かけ放題'],
                description='大容量データユーザー向けのプラン'
            ),
            'M_24h': Plan(
                name='dモバイル M + 24時間かけ放題',
                monthly_cost=3980,
                data_limit='1日2GB',
                voice_option='24時間かけ放題',
                features=['docomo回線', '毎日リセット型容量', '24時間かけ放題'],
                description='中量データ + 通話重視ユーザー向け'
            ),
            'L_24h': Plan(
                name='dモバイル L + 24時間かけ放題',
                monthly_cost=4980,
                data_limit='1日4GB',
                voice_option='24時間かけ放題',
                features=['docomo回線', '毎日リセット型容量', '24時間かけ放題'],
                description='大容量データ + 通話重視ユーザー向け'
            )
        }
        
        # オプション料金
        self.voice_options = {
            '24h_unlimited': 1000,  # 24時間かけ放題オプション
            '10min_unlimited': 500,  # 10分かけ放題オプション
        }
    
    def select_plan(self, bill_data: Dict) -> Dict:
        """請求書データから最適なプランを選択"""
        try:
            current_cost = bill_data.get('total_cost', 0)
            breakdown = bill_data.get('breakdown', {})
            
            # 特徴量を抽出
            features = self._extract_features(bill_data)
            
            # プランを選定
            recommended_plans = self._select_plans_by_features(features, current_cost)
            
            # 最適なプランを選択
            best_plan = recommended_plans[0] if recommended_plans else self.plans['M']
            
            return {
                'name': best_plan.name,
                'monthly_cost': best_plan.monthly_cost,
                'data_limit': best_plan.data_limit,
                'voice_option': best_plan.voice_option,
                'features': best_plan.features,
                'description': best_plan.description,
                'alternatives': [p.name for p in recommended_plans[1:3]],  # 代替案
                'selection_reason': self._get_selection_reason(features, best_plan)
            }
            
        except Exception as e:
            logger.error(f"Error selecting plan: {str(e)}")
            # デフォルトでMプランを返す
            return {
                'name': self.plans['M'].name,
                'monthly_cost': self.plans['M'].monthly_cost,
                'data_limit': self.plans['M'].data_limit,
                'voice_option': self.plans['M'].voice_option,
                'features': self.plans['M'].features,
                'description': self.plans['M'].description,
                'alternatives': [],
                'selection_reason': 'デフォルト選択（解析エラー）'
            }
    
    def _extract_features(self, bill_data: Dict) -> Dict:
        """請求書から特徴量を抽出"""
        breakdown = bill_data.get('breakdown', {})
        current_cost = bill_data.get('total_cost', 0)
        
        features = {
            'current_cost': current_cost,
            'has_voice_option': breakdown.get('voice_option', 0) > 0,
            'has_24h_unlimited': False,  # 24時間かけ放題の判定
            'has_10min_unlimited': False,  # 10分かけ放題の判定
            'has_5min_unlimited': False,  # 5分かけ放題の判定
            'voice_cost_high': breakdown.get('voice', 0) > 2000,  # 通話料が高い
            'data_cost_high': breakdown.get('data', 0) > 3000,  # データ通信料が高い
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
    
    def _select_plans_by_features(self, features: Dict, current_cost: int) -> List[Plan]:
        """特徴量に基づいてプランを選択"""
        candidates = []
        
        # ルールベースの選定ロジック
        
        # 1. 通話重視ユーザー（24時間かけ放題相当 or 通話料高額）
        if features['has_24h_unlimited'] or features['voice_cost_high']:
            if features['data_cost_high'] or features['cost_level'] == 'high':
                candidates.append(self.plans['L_24h'])
                candidates.append(self.plans['M_24h'])
            else:
                candidates.append(self.plans['M_24h'])
                candidates.append(self.plans['L_24h'])
        
        # 2. データ重視ユーザー（通信料高額 or 速度制限記載）
        elif features['data_cost_high'] or features['cost_level'] == 'high':
            candidates.append(self.plans['L'])
            candidates.append(self.plans['M'])
        
        # 3. バランス型ユーザー（中程度のコスト）
        elif features['cost_level'] == 'medium':
            candidates.append(self.plans['M'])
            candidates.append(self.plans['L'])
        
        # 4. 低コストユーザー
        else:
            candidates.append(self.plans['M'])
        
        # 重複を除去
        unique_candidates = []
        seen_names = set()
        for plan in candidates:
            if plan.name not in seen_names:
                unique_candidates.append(plan)
                seen_names.add(plan.name)
        
        return unique_candidates
    
    def _get_selection_reason(self, features: Dict, selected_plan: Plan) -> str:
        """選択理由を生成"""
        reasons = []
        
        if features['has_24h_unlimited'] or features['voice_cost_high']:
            reasons.append("通話料金が高額のため")
        
        if features['data_cost_high']:
            reasons.append("データ通信料が高額のため")
        
        if features['cost_level'] == 'high':
            reasons.append("現在の料金が高額のため")
        
        if selected_plan.name == 'dモバイル L':
            reasons.append("大容量データプランを推奨")
        elif selected_plan.name == 'dモバイル M':
            reasons.append("バランス型プランを推奨")
        elif '24時間かけ放題' in selected_plan.name:
            reasons.append("通話重視プランを推奨")
        
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
        if plan_name not in self.plans:
            return 0
        
        base_cost = self.plans[plan_name].monthly_cost
        
        if add_24h_option and '24時間かけ放題' not in plan_name:
            base_cost += self.voice_options['24h_unlimited']
        
        return base_cost

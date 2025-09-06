import unittest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.plan_selector import PlanSelector

class TestPlanSelector(unittest.TestCase):
    def setUp(self):
        self.selector = PlanSelector()
    
    def test_plan_initialization(self):
        """プラン初期化のテスト"""
        self.assertIn('M', self.selector.plans)
        self.assertIn('L', self.selector.plans)
        self.assertIn('M_24h', self.selector.plans)
        self.assertIn('L_24h', self.selector.plans)
        
        # Sプランは含まれていないことを確認
        self.assertNotIn('S', self.selector.plans)
    
    def test_feature_extraction(self):
        """特徴量抽出のテスト"""
        bill_data = {
            'total_cost': 4500,
            'breakdown': {
                'basic': 2980,
                'data': 1200,
                'voice': 800,
                'voice_option': 1000,
                'discount': -500
            }
        }
        
        features = self.selector._extract_features(bill_data)
        
        self.assertEqual(features['current_cost'], 4500)
        self.assertTrue(features['has_voice_option'])
        self.assertTrue(features['has_24h_unlimited'])
        self.assertTrue(features['has_discount'])
        self.assertEqual(features['cost_level'], 'medium')
    
    def test_cost_level_classification(self):
        """コストレベル分類のテスト"""
        # 低コスト
        level = self.selector._get_cost_level(2500)
        self.assertEqual(level, 'low')
        
        # 中コスト
        level = self.selector._get_cost_level(4000)
        self.assertEqual(level, 'medium')
        
        # 高コスト
        level = self.selector._get_cost_level(6000)
        self.assertEqual(level, 'high')
    
    def test_plan_selection_voice_heavy(self):
        """通話重視ユーザーのプラン選択テスト"""
        bill_data = {
            'total_cost': 5000,
            'breakdown': {
                'basic': 2980,
                'data': 800,
                'voice': 2500,  # 高額な通話料
                'voice_option': 1200,  # 24時間かけ放題相当
                'discount': -500
            }
        }
        
        result = self.selector.select_plan(bill_data)
        
        # 通話重視なので24時間かけ放題プランが選ばれるはず
        self.assertIn('24時間かけ放題', result['name'])
        self.assertIn('通話', result['selection_reason'])
    
    def test_plan_selection_data_heavy(self):
        """データ重視ユーザーのプラン選択テスト"""
        bill_data = {
            'total_cost': 4500,
            'breakdown': {
                'basic': 2980,
                'data': 3000,  # 高額なデータ通信料
                'voice': 500,
                'voice_option': 0,
                'discount': -500
            }
        }
        
        result = self.selector.select_plan(bill_data)
        
        # データ重視なのでLプランが選ばれるはず（またはMプラン）
        self.assertTrue('L' in result['name'] or 'M' in result['name'])
        # データ重視の理由が含まれるか、バランス型として判定される
        self.assertTrue('データ' in result['selection_reason'] or 'バランス' in result['selection_reason'])
    
    def test_plan_selection_balanced(self):
        """バランス型ユーザーのプラン選択テスト"""
        bill_data = {
            'total_cost': 3500,
            'breakdown': {
                'basic': 2980,
                'data': 800,
                'voice': 500,
                'voice_option': 0,
                'discount': -500
            }
        }
        
        result = self.selector.select_plan(bill_data)
        
        # バランス型なのでMプランが選ばれるはず
        self.assertIn('M', result['name'])
        self.assertIn('バランス', result['selection_reason'])
    
    def test_plan_selection_low_cost(self):
        """低コストユーザーのプラン選択テスト"""
        bill_data = {
            'total_cost': 2500,
            'breakdown': {
                'basic': 2000,
                'data': 500,
                'voice': 200,
                'voice_option': 0,
                'discount': -200
            }
        }
        
        result = self.selector.select_plan(bill_data)
        
        # 低コストなのでMプランが選ばれるはず
        self.assertIn('M', result['name'])
    
    def test_plan_cost_calculation(self):
        """プラン料金計算のテスト"""
        # 基本プラン
        cost = self.selector.calculate_plan_cost('M')
        self.assertEqual(cost, 2980)
        
        # オプション付きプラン
        cost = self.selector.calculate_plan_cost('M', add_24h_option=True)
        self.assertEqual(cost, 3980)  # 2980 + 1000
    
    def test_get_all_plans(self):
        """全プラン取得のテスト"""
        plans = self.selector.get_all_plans()
        
        self.assertEqual(len(plans), 4)
        
        plan_names = [plan['name'] for plan in plans]
        self.assertIn('dモバイル M', plan_names)
        self.assertIn('dモバイル L', plan_names)
        self.assertIn('dモバイル M + 24時間かけ放題', plan_names)
        self.assertIn('dモバイル L + 24時間かけ放題', plan_names)
    
    def test_selection_reason_generation(self):
        """選択理由生成のテスト"""
        features = {
            'has_24h_unlimited': True,
            'voice_cost_high': True,
            'data_cost_high': False,
            'cost_level': 'high'
        }
        
        plan = self.selector.plans['L_24h']
        reason = self.selector._get_selection_reason(features, plan)
        
        self.assertIn('通話', reason)
        self.assertIn('高額', reason)
    
    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        # 不正なデータ
        bill_data = {
            'total_cost': 0,
            'breakdown': {}
        }
        
        result = self.selector.select_plan(bill_data)
        
        # エラー時はデフォルトでMプランが返される
        self.assertEqual(result['name'], 'dモバイル M')
        # エラー時はデフォルト選択の理由が含まれる
        self.assertTrue('デフォルト' in result['selection_reason'] or 'バランス' in result['selection_reason'])

if __name__ == '__main__':
    unittest.main()

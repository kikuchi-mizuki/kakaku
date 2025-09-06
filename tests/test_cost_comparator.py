import unittest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.cost_comparator import CostComparator

class TestCostComparator(unittest.TestCase):
    def setUp(self):
        self.comparator = CostComparator()
    
    def test_cost_comparison_basic(self):
        """基本的な料金比較のテスト"""
        current_cost = 4500
        recommended_plan = {
            'name': 'dモバイル M',
            'monthly_cost': 2980
        }
        
        result = self.comparator.compare_costs(current_cost, recommended_plan)
        
        self.assertEqual(result['current_cost'], 4500)
        self.assertEqual(result['recommended_cost'], 2980)
        self.assertEqual(result['monthly_saving'], 1520)
        self.assertEqual(result['yearly_saving'], 18240)
        self.assertEqual(result['total_50year'], 912000)
        self.assertGreater(result['saving_percentage'], 0)
    
    def test_cost_comparison_negative_saving(self):
        """節約額が負の場合のテスト"""
        current_cost = 2000
        recommended_plan = {
            'name': 'dモバイル L',
            'monthly_cost': 3980
        }
        
        result = self.comparator.compare_costs(current_cost, recommended_plan)
        
        self.assertEqual(result['monthly_saving'], -1980)
        self.assertEqual(result['yearly_saving'], -23760)
        self.assertEqual(result['total_50year'], -1188000)
        self.assertLess(result['saving_percentage'], 0)
    
    def test_examples_generation(self):
        """その金額でできることの例生成テスト"""
        # 年間10万円の場合
        examples = self.comparator._get_examples(100000)
        
        self.assertEqual(examples['yearly'], '家族旅行（国内）')
        self.assertEqual(examples['10year'], '新車の頭金')
        self.assertEqual(examples['50year'], '新車購入（複数台）')
        
        # 年間5万円の場合
        examples = self.comparator._get_examples(50000)
        
        self.assertEqual(examples['yearly'], '高級レストラン10回')
        self.assertEqual(examples['10year'], '住宅ローンの一部返済')
        self.assertEqual(examples['50year'], '住宅購入の一部')
        
        # 年間1万円の場合
        examples = self.comparator._get_examples(10000)
        
        self.assertEqual(examples['yearly'], '書籍100冊購入')
        self.assertEqual(examples['10year'], '老後資金の積立')
        self.assertEqual(examples['50year'], '遺産として残す')
    
    def test_csv_data_generation(self):
        """CSVデータ生成のテスト"""
        current_cost = 4500
        plan_cost = 2980
        
        csv_data = self.comparator._generate_csv_data(current_cost, plan_cost)
        
        self.assertIsInstance(csv_data, str)
        self.assertIn('年', csv_data)
        self.assertIn('月額差額', csv_data)
        self.assertIn('年間差額', csv_data)
        self.assertIn('累積差額', csv_data)
        
        # 最初の行（ヘッダー）を確認
        lines = csv_data.split('\n')
        self.assertIn('年,月額差額,年間差額,累積差額', lines[0])
    
    def test_graph_data_generation(self):
        """グラフデータ生成のテスト"""
        current_cost = 4500
        plan_cost = 2980
        
        graph_data = self.comparator._generate_cost_graph(current_cost, plan_cost)
        
        # Base64エンコードされた画像データが返されることを確認
        self.assertIsInstance(graph_data, str)
        self.assertGreater(len(graph_data), 1000)  # 画像データなので十分な長さがある
    
    def test_error_handling(self):
        """エラーハンドリングのテスト"""
        # 不正なデータ
        current_cost = 0
        recommended_plan = {}
        
        result = self.comparator.compare_costs(current_cost, recommended_plan)
        
        # エラー時でも基本的な構造は返される
        self.assertIn('current_cost', result)
        self.assertIn('recommended_cost', result)
        self.assertIn('monthly_saving', result)
        self.assertIn('yearly_saving', result)
        self.assertIn('total_50year', result)
    
    def test_saving_percentage_calculation(self):
        """節約率計算のテスト"""
        # 50%節約の場合
        current_cost = 4000
        recommended_plan = {
            'name': 'dモバイル M',
            'monthly_cost': 2000
        }
        
        result = self.comparator.compare_costs(current_cost, recommended_plan)
        
        self.assertEqual(result['saving_percentage'], 50.0)
        
        # 0円の場合
        current_cost = 0
        result = self.comparator.compare_costs(current_cost, recommended_plan)
        
        self.assertEqual(result['saving_percentage'], 0)
    
    def test_file_saving(self):
        """ファイル保存のテスト"""
        # テスト用のデータ
        graph_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="  # 1x1 PNG
        csv_data = "年,月額差額,年間差額,累積差額\n1,1000,12000,12000"
        
        # グラフ保存
        graph_path = self.comparator.save_graph_to_file(graph_data, "test_graph.png")
        if graph_path:
            self.assertTrue(os.path.exists(graph_path))
            os.remove(graph_path)  # クリーンアップ
        
        # CSV保存
        csv_path = self.comparator.save_csv_to_file(csv_data, "test_data.csv")
        if csv_path:
            self.assertTrue(os.path.exists(csv_path))
            os.remove(csv_path)  # クリーンアップ

if __name__ == '__main__':
    unittest.main()

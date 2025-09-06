import unittest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bill_processor import BillProcessor, BillLine

class TestBillProcessor(unittest.TestCase):
    def setUp(self):
        self.processor = BillProcessor()
    
    def test_phone_number_extraction(self):
        """電話番号抽出のテスト"""
        text = "090-1234-5678 基本料金 2,980円"
        phone_numbers = self.processor._extract_phone_numbers(text)
        self.assertIn("090-1234-5678", phone_numbers)
    
    def test_phone_number_masking(self):
        """電話番号マスキングのテスト"""
        from services.security_service import SecurityService
        security = SecurityService()
        
        # 携帯電話番号
        masked = security.mask_phone_number("090-1234-5678")
        self.assertEqual(masked, "090-****-5678")
        
        # 固定電話
        masked = security.mask_phone_number("03-1234-5678")
        self.assertEqual(masked, "03-****-5678")
    
    def test_bill_line_parsing(self):
        """請求明細行の解析テスト"""
        line = "基本料金 2,980円"
        bill_line = self.processor._parse_bill_line(line)
        
        self.assertIsNotNone(bill_line)
        self.assertEqual(bill_line.amount, 2980)
        self.assertEqual(bill_line.category, 'basic')
    
    def test_cost_categorization(self):
        """費用分類のテスト"""
        # 基本料金
        category = self.processor._categorize_line("基本料金 2,980円")
        self.assertEqual(category, 'basic')
        
        # 通話料金
        category = self.processor._categorize_line("通話料金 1,200円")
        self.assertEqual(category, 'voice')
        
        # データ通信
        category = self.processor._categorize_line("データ通信料 800円")
        self.assertEqual(category, 'data')
        
        # 端末代金（除外）
        category = self.processor._categorize_line("端末代金 50,000円")
        self.assertEqual(category, 'excluded')
    
    def test_line_cost_extraction(self):
        """回線費用抽出のテスト"""
        bill_lines = [
            BillLine("基本料金 2,980円", 2980, "basic"),
            BillLine("データ通信料 800円", 800, "data"),
            BillLine("通話料金 1,200円", 1200, "voice"),
            BillLine("端末代金 50,000円", 50000, "excluded"),
            BillLine("小計 4,980円", 4980, "total")
        ]
        
        total_cost, breakdown = self.processor._extract_line_costs(bill_lines)
        
        self.assertEqual(total_cost, 4980)
        self.assertEqual(breakdown['basic'], 2980)
        self.assertEqual(breakdown['data'], 800)
        self.assertEqual(breakdown['voice'], 1200)
        self.assertEqual(breakdown['excluded'], 50000)  # 除外項目は記録される
    
    def test_family_bill_splitting(self):
        """家族明細分割のテスト"""
        text = """
        090-1234-5678
        基本料金 2,980円
        データ通信料 800円
        小計 3,780円
        
        090-5678-9012
        基本料金 2,980円
        データ通信料 1,200円
        小計 4,180円
        """
        
        blocks = self.processor._split_family_bill(text, [])
        
        self.assertEqual(len(blocks), 2)
        self.assertIn("090-1234-5678", blocks[0]['text'])
        self.assertIn("090-5678-9012", blocks[1]['text'])
    
    def test_confidence_calculation(self):
        """信頼度計算のテスト"""
        bill_lines = [
            BillLine("基本料金 2,980円", 2980, "basic"),
            BillLine("データ通信料 800円", 800, "data"),
            BillLine("不明な項目", None, None),
        ]
        
        confidence = self.processor._calculate_confidence(bill_lines)
        
        # 金額抽出率: 2/3 = 0.67
        # カテゴリ判定率: 2/3 = 0.67
        # 回線費用率: 2/3 = 0.67
        # 総合信頼度: 0.67 * 0.4 + 0.67 * 0.3 + 0.67 * 0.3 = 0.67
        self.assertAlmostEqual(confidence, 0.67, places=2)
    
    def test_process_bill_integration(self):
        """請求書処理の統合テスト"""
        ocr_result = {
            'text': """
            090-1234-5678
            基本料金 2,980円
            データ通信料 800円
            通話料金 1,200円
            端末代金 50,000円
            小計 4,980円
            """,
            'blocks': [],
            'confidence': 0.9
        }
        
        result = self.processor.process_bill(ocr_result)
        
        self.assertEqual(result['total_cost'], 4980)
        self.assertEqual(result['breakdown']['basic'], 2980)
        self.assertEqual(result['breakdown']['data'], 800)
        self.assertEqual(result['breakdown']['voice'], 1200)
        self.assertGreater(result['confidence'], 0.5)

if __name__ == '__main__':
    unittest.main()

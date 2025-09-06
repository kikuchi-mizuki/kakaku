#!/usr/bin/env python3
"""
テスト実行スクリプト
"""
import unittest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_tests():
    """全テストを実行"""
    # テストディスカバリ
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 結果の表示
    print(f"\n{'='*50}")
    print(f"テスト結果: {result.testsRun}件実行")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}件")
    print(f"失敗: {len(result.failures)}件")
    print(f"エラー: {len(result.errors)}件")
    
    if result.failures:
        print(f"\n失敗したテスト:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nエラーが発生したテスト:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

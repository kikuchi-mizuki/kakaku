import logging
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
import os
from typing import Dict, List, Tuple
import io
import base64

logger = logging.getLogger(__name__)

class CostComparator:
    def __init__(self):
        # フォント設定（日本語対応）
        plt.rcParams['font.family'] = ['DejaVu Sans', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']
        
        # グラフのスタイル設定
        plt.style.use('default')
        
        # その金額でできることの例
        self.examples = {
            'yearly': [
                '家族旅行（国内）',
                '高級レストラン10回',
                '映画鑑賞50回',
                '書籍100冊購入'
            ],
            '10year': [
                '新車の頭金',
                '住宅ローンの一部返済',
                '子供の教育費',
                '老後資金の積立'
            ],
            '50year': [
                '新車購入（複数台）',
                '住宅購入の一部',
                '老後生活費の一部',
                '遺産として残す'
            ]
        }
    
    def compare_costs(self, current_cost: int, recommended_plan: Dict, analysis_data: Dict = None) -> Dict:
        """料金比較を実行（AI診断データ対応）"""
        try:
            plan_cost = recommended_plan['monthly_cost']
            
            # 差額計算
            monthly_saving = current_cost - plan_cost
            yearly_saving = monthly_saving * 12
            
            # 50年累積計算
            total_50year = yearly_saving * 50
            
            # グラフ生成
            graph_data = self._generate_cost_graph(current_cost, plan_cost)
            
            # CSV生成
            csv_data = self._generate_csv_data(current_cost, plan_cost)
            
            # その金額でできること（改善版）
            examples = self._get_enhanced_examples(abs(yearly_saving))
            
            # 損失分析
            loss_analysis = self._generate_loss_analysis(monthly_saving, yearly_saving, total_50year)
            
            # dモバイルのメリット
            dmobile_benefits = self._get_dmobile_benefits(analysis_data)
            
            return {
                'current_cost': current_cost,
                'recommended_cost': plan_cost,
                'monthly_saving': monthly_saving,
                'yearly_saving': yearly_saving,
                'total_50year': total_50year,
                'graph_data': graph_data,
                'csv_data': csv_data,
                'examples': examples,
                'loss_analysis': loss_analysis,
                'dmobile_benefits': dmobile_benefits,
                'saving_percentage': (monthly_saving / current_cost * 100) if current_cost > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error comparing costs: {str(e)}")
            return {
                'current_cost': current_cost,
                'recommended_cost': recommended_plan.get('monthly_cost', 0),
                'monthly_saving': 0,
                'yearly_saving': 0,
                'total_50year': 0,
                'graph_data': None,
                'csv_data': None,
                'examples': {},
                'saving_percentage': 0,
                'error': str(e)
            }
    
    def _generate_cost_graph(self, current_cost: int, plan_cost: int) -> str:
        """50年累積損失の折れ線グラフを生成"""
        try:
            # データ準備
            years = list(range(1, 51))
            monthly_saving = current_cost - plan_cost
            yearly_saving = monthly_saving * 12
            
            # 累積差額を計算
            cumulative_savings = [yearly_saving * year for year in years]
            
            # グラフ作成
            fig, ax = plt.subplots(figsize=(12, 8))
            
            # 折れ線グラフ
            ax.plot(years, cumulative_savings, 
                   linewidth=3, 
                   color='#FF6B6B' if monthly_saving > 0 else '#1DB446',
                   marker='o', 
                   markersize=4,
                   markevery=5)
            
            # グラフの装飾
            ax.set_title('50年間の累積差額', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('年数', fontsize=12)
            ax.set_ylabel('累積差額 (円)', fontsize=12)
            
            # グリッド
            ax.grid(True, alpha=0.3)
            
            # 軸の設定
            ax.set_xlim(0, 51)
            
            # 数値のフォーマット
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'¥{x:,.0f}'))
            
            # 重要なポイントをハイライト
            if len(cumulative_savings) >= 10:
                ax.axhline(y=cumulative_savings[9], color='gray', linestyle='--', alpha=0.5)
                ax.text(10, cumulative_savings[9], f'10年: ¥{cumulative_savings[9]:,.0f}', 
                       ha='left', va='bottom', fontsize=10)
            
            if len(cumulative_savings) >= 25:
                ax.axhline(y=cumulative_savings[24], color='gray', linestyle='--', alpha=0.5)
                ax.text(25, cumulative_savings[24], f'25年: ¥{cumulative_savings[24]:,.0f}', 
                       ha='left', va='bottom', fontsize=10)
            
            # 最終値を表示
            final_value = cumulative_savings[-1]
            ax.text(50, final_value, f'50年: ¥{final_value:,.0f}', 
                   ha='right', va='bottom', fontsize=12, fontweight='bold')
            
            # レイアウト調整
            plt.tight_layout()
            
            # 画像をBase64エンコード
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return image_base64
            
        except Exception as e:
            logger.error(f"Error generating cost graph: {str(e)}")
            return None
    
    def _generate_csv_data(self, current_cost: int, plan_cost: int) -> str:
        """CSVデータを生成"""
        try:
            # データ準備
            years = list(range(1, 51))
            monthly_saving = current_cost - plan_cost
            yearly_saving = monthly_saving * 12
            
            # DataFrame作成
            data = []
            cumulative = 0
            
            for year in years:
                cumulative += yearly_saving
                data.append({
                    '年': year,
                    '月額差額': monthly_saving,
                    '年間差額': yearly_saving,
                    '累積差額': cumulative
                })
            
            df = pd.DataFrame(data)
            
            # CSV文字列として返す
            csv_string = df.to_csv(index=False, encoding='utf-8-sig')
            
            return csv_string
            
        except Exception as e:
            logger.error(f"Error generating CSV data: {str(e)}")
            return ""
    
    def _get_examples(self, yearly_amount: int) -> Dict:
        """その金額でできることの例を取得"""
        try:
            examples = {}
            
            # 年間
            if yearly_amount >= 100000:  # 10万円以上
                examples['yearly'] = '家族旅行（国内）'
            elif yearly_amount >= 50000:  # 5万円以上
                examples['yearly'] = '高級レストラン10回'
            elif yearly_amount >= 20000:  # 2万円以上
                examples['yearly'] = '映画鑑賞50回'
            else:
                examples['yearly'] = '書籍100冊購入'
            
            # 10年
            ten_year_amount = yearly_amount * 10
            if ten_year_amount >= 1000000:  # 100万円以上
                examples['10year'] = '新車の頭金'
            elif ten_year_amount >= 500000:  # 50万円以上
                examples['10year'] = '住宅ローンの一部返済'
            elif ten_year_amount >= 200000:  # 20万円以上
                examples['10year'] = '子供の教育費'
            else:
                examples['10year'] = '老後資金の積立'
            
            # 50年
            fifty_year_amount = yearly_amount * 50
            if fifty_year_amount >= 5000000:  # 500万円以上
                examples['50year'] = '新車購入（複数台）'
            elif fifty_year_amount >= 2000000:  # 200万円以上
                examples['50year'] = '住宅購入の一部'
            elif fifty_year_amount >= 1000000:  # 100万円以上
                examples['50year'] = '老後生活費の一部'
            else:
                examples['50year'] = '遺産として残す'
            
            return examples
            
        except Exception as e:
            logger.error(f"Error getting examples: {str(e)}")
            return {
                'yearly': 'N/A',
                '10year': 'N/A',
                '50year': 'N/A'
            }
    
    def _get_enhanced_examples(self, yearly_amount: int) -> Dict:
        """その金額でできることの例を取得（改善版）"""
        try:
            examples = {}
            
            # 年間
            if yearly_amount >= 200000:  # 20万円以上
                examples['yearly'] = '海外旅行1回'
            elif yearly_amount >= 100000:  # 10万円以上
                examples['yearly'] = '国内旅行2回'
            elif yearly_amount >= 50000:  # 5万円以上
                examples['yearly'] = '高級レストラン10回'
            elif yearly_amount >= 30000:  # 3万円以上
                examples['yearly'] = '映画・コンサート5回'
            elif yearly_amount >= 20000:  # 2万円以上
                examples['yearly'] = '新しい服・靴'
            elif yearly_amount >= 10000:  # 1万円以上
                examples['yearly'] = 'ちょっとした贅沢'
            else:
                examples['yearly'] = '節約効果あり'
            
            # 10年
            ten_year_amount = yearly_amount * 10
            if ten_year_amount >= 2000000:  # 200万円以上
                examples['10year'] = '新車購入'
            elif ten_year_amount >= 1000000:  # 100万円以上
                examples['10year'] = '高級腕時計'
            elif ten_year_amount >= 500000:  # 50万円以上
                examples['10year'] = '海外旅行10回'
            elif ten_year_amount >= 300000:  # 30万円以上
                examples['10year'] = '高級家電一式'
            elif ten_year_amount >= 200000:  # 20万円以上
                examples['10year'] = '家具・インテリア'
            elif ten_year_amount >= 100000:  # 10万円以上
                examples['10year'] = '趣味・娯楽'
            else:
                examples['10year'] = '積立効果あり'
            
            # 50年
            fifty_year_amount = yearly_amount * 50
            if fifty_year_amount >= 10000000:  # 1000万円以上
                examples['50year'] = '家の頭金'
            elif fifty_year_amount >= 5000000:  # 500万円以上
                examples['50year'] = '高級車購入'
            elif fifty_year_amount >= 2000000:  # 200万円以上
                examples['50year'] = '海外旅行50回'
            elif fifty_year_amount >= 1000000:  # 100万円以上
                examples['50year'] = '高級家具一式'
            elif fifty_year_amount >= 500000:  # 50万円以上
                examples['50year'] = '高級家電・PC'
            elif fifty_year_amount >= 200000:  # 20万円以上
                examples['50year'] = '趣味・娯楽'
            else:
                examples['50year'] = '長期積立効果'
            
            return examples
            
        except Exception as e:
            logger.error(f"Error getting enhanced examples: {str(e)}")
            return {
                'yearly': 'N/A',
                '10year': 'N/A',
                '50year': 'N/A'
            }
    
    def _generate_loss_analysis(self, monthly_saving: int, yearly_saving: int, total_50year: int) -> Dict:
        """損失分析を生成"""
        try:
            return {
                'monthly_loss': monthly_saving if monthly_saving > 0 else 0,
                'yearly_loss': yearly_saving if yearly_saving > 0 else 0,
                'total_50year_loss': total_50year if total_50year > 0 else 0,
                'loss_summary': self._get_loss_summary(monthly_saving, yearly_saving, total_50year)
            }
        except Exception as e:
            logger.error(f"Error generating loss analysis: {str(e)}")
            return {
                'monthly_loss': 0,
                'yearly_loss': 0,
                'total_50year_loss': 0,
                'loss_summary': '損失分析エラー'
            }
    
    def _get_loss_summary(self, monthly_saving: int, yearly_saving: int, total_50year: int) -> str:
        """損失サマリーを生成"""
        if monthly_saving > 0:
            return f"現在のキャリアを使い続けると、月額¥{monthly_saving:,}、年間¥{yearly_saving:,}、50年間で¥{total_50year:,}の損失になります。"
        else:
            return "現在のプランが最適です。"
    
    def _get_dmobile_benefits(self, analysis_data: Dict = None) -> List[str]:
        """dモバイルのメリットを取得"""
        benefits = [
            "📶 docomo回線で安定した通信品質",
            "🔄 毎日リセット型データ容量",
            "📞 かけ放題オプション充実",
            "💰 格安料金でdocomo回線を利用",
            "🎯 シンプルで分かりやすい料金体系",
            "📱 最新スマートフォン対応"
        ]
        
        if analysis_data:
            # データ使用量に応じたメリット
            data_usage = analysis_data.get('data_usage', 0)
            if data_usage > 10:
                benefits.append("📊 大容量データプランで安心")
            elif data_usage > 5:
                benefits.append("📊 中容量データプランで十分")
            else:
                benefits.append("📊 小容量データプランで節約")
            
            # 通話使用量に応じたメリット
            call_usage = analysis_data.get('call_usage', 0)
            if call_usage > 1000:
                benefits.append("📞 24時間かけ放題オプション推奨")
            elif call_usage > 500:
                benefits.append("📞 5分かけ放題オプション推奨")
        
        return benefits[:6]  # 最大6個のメリットを返す
    
    def save_graph_to_file(self, graph_data: str, filename: str) -> str:
        """グラフをファイルに保存"""
        try:
            if not graph_data:
                return None
            
            # Base64デコード
            image_data = base64.b64decode(graph_data)
            
            # ファイルに保存
            filepath = f"outputs/{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving graph to file: {str(e)}")
            return None
    
    def save_csv_to_file(self, csv_data: str, filename: str) -> str:
        """CSVをファイルに保存"""
        try:
            if not csv_data:
                return None
            
            # ファイルに保存
            filepath = f"outputs/{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write(csv_data)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving CSV to file: {str(e)}")
            return None

import logging
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import os
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class AnalysisLog:
    """解析ログのデータクラス"""
    log_id: str
    timestamp: str
    user_id_hash: str
    phone_number_masked: Optional[str]
    ocr_confidence: float
    ocr_method: str
    current_cost: int
    recommended_plan: str
    monthly_saving: int
    yearly_saving: int
    total_50year: int
    bill_features: Dict[str, Any]
    selection_reason: str
    cta_clicked: Optional[str] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None

class AnalyticsService:
    def __init__(self):
        self.log_file = "logs/analytics.jsonl"
        self.error_log_file = "logs/errors.jsonl"
        self.ensure_log_directories()
    
    def ensure_log_directories(self):
        """ログディレクトリを作成"""
        os.makedirs("logs", exist_ok=True)
        os.makedirs("outputs", exist_ok=True)
    
    def log_analysis(self, 
                    user_id: str,
                    phone_number: Optional[str],
                    ocr_result: Dict,
                    bill_data: Dict,
                    recommended_plan: Dict,
                    comparison_result: Dict,
                    processing_time: float,
                    error: Optional[str] = None) -> str:
        """解析結果をログに記録"""
        try:
            log_id = str(uuid.uuid4())
            
            # ユーザーIDをハッシュ化
            user_id_hash = self._hash_user_id(user_id)
            
            # 電話番号をマスク
            phone_masked = self._mask_phone_number(phone_number) if phone_number else None
            
            # ログデータを作成
            log_data = AnalysisLog(
                log_id=log_id,
                timestamp=datetime.now().isoformat(),
                user_id_hash=user_id_hash,
                phone_number_masked=phone_masked,
                ocr_confidence=ocr_result.get('confidence', 0.0),
                ocr_method=ocr_result.get('method', 'unknown'),
                current_cost=bill_data.get('total_cost', 0),
                recommended_plan=recommended_plan.get('name', ''),
                monthly_saving=comparison_result.get('monthly_saving', 0),
                yearly_saving=comparison_result.get('yearly_saving', 0),
                total_50year=comparison_result.get('total_50year', 0),
                bill_features=self._extract_bill_features(bill_data),
                selection_reason=recommended_plan.get('selection_reason', ''),
                processing_time=processing_time,
                error_message=error
            )
            
            # ログファイルに書き込み
            self._write_log(self.log_file, asdict(log_data))
            
            logger.info(f"Analysis logged: {log_id}")
            return log_id
            
        except Exception as e:
            logger.error(f"Error logging analysis: {str(e)}")
            return ""
    
    def log_cta_click(self, log_id: str, cta_type: str):
        """CTAクリックをログに記録"""
        try:
            # 既存のログを更新
            self._update_log_field(log_id, 'cta_clicked', cta_type)
            logger.info(f"CTA click logged: {log_id} - {cta_type}")
            
        except Exception as e:
            logger.error(f"Error logging CTA click: {str(e)}")
    
    def log_error(self, error_type: str, error_message: str, context: Dict = None):
        """エラーをログに記録"""
        try:
            error_log = {
                'timestamp': datetime.now().isoformat(),
                'error_type': error_type,
                'error_message': error_message,
                'context': context or {}
            }
            
            self._write_log(self.error_log_file, error_log)
            logger.error(f"Error logged: {error_type} - {error_message}")
            
        except Exception as e:
            logger.error(f"Error logging error: {str(e)}")
    
    def get_analytics_summary(self, days: int = 30) -> Dict:
        """解析サマリーを取得"""
        try:
            logs = self._read_logs(self.log_file, days)
            
            if not logs:
                return self._empty_summary()
            
            # 基本統計
            total_analyses = len(logs)
            successful_analyses = len([log for log in logs if not log.get('error_message')])
            error_rate = (total_analyses - successful_analyses) / total_analyses * 100 if total_analyses > 0 else 0
            
            # 平均処理時間
            processing_times = [log.get('processing_time', 0) for log in logs if log.get('processing_time')]
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            
            # OCR信頼度
            ocr_confidences = [log.get('ocr_confidence', 0) for log in logs]
            avg_ocr_confidence = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0
            
            # プラン選択統計
            plan_counts = {}
            for log in logs:
                plan = log.get('recommended_plan', '')
                plan_counts[plan] = plan_counts.get(plan, 0) + 1
            
            # 平均節約額
            monthly_savings = [log.get('monthly_saving', 0) for log in logs]
            avg_monthly_saving = sum(monthly_savings) / len(monthly_savings) if monthly_savings else 0
            
            # CTAクリック統計
            cta_clicks = [log.get('cta_clicked') for log in logs if log.get('cta_clicked')]
            cta_stats = {}
            for cta in cta_clicks:
                cta_stats[cta] = cta_stats.get(cta, 0) + 1
            
            return {
                'period_days': days,
                'total_analyses': total_analyses,
                'successful_analyses': successful_analyses,
                'error_rate': round(error_rate, 2),
                'avg_processing_time': round(avg_processing_time, 2),
                'avg_ocr_confidence': round(avg_ocr_confidence, 3),
                'avg_monthly_saving': round(avg_monthly_saving),
                'plan_distribution': plan_counts,
                'cta_click_stats': cta_stats,
                'cta_click_rate': len(cta_clicks) / total_analyses * 100 if total_analyses > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return self._empty_summary()
    
    def get_plan_selection_insights(self, days: int = 30) -> Dict:
        """プラン選択のインサイトを取得"""
        try:
            logs = self._read_logs(self.log_file, days)
            
            if not logs:
                return {}
            
            # 特徴量とプラン選択の関係を分析
            insights = {}
            
            for log in logs:
                features = log.get('bill_features', {})
                plan = log.get('recommended_plan', '')
                
                if not features or not plan:
                    continue
                
                # 各特徴量ごとのプラン選択傾向を記録
                for feature, value in features.items():
                    if feature not in insights:
                        insights[feature] = {}
                    
                    if value not in insights[feature]:
                        insights[feature][value] = {}
                    
                    if plan not in insights[feature][value]:
                        insights[feature][value][plan] = 0
                    
                    insights[feature][value][plan] += 1
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting plan selection insights: {str(e)}")
            return {}
    
    def _hash_user_id(self, user_id: str) -> str:
        """ユーザーIDをハッシュ化"""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]
    
    def _mask_phone_number(self, phone_number: str) -> str:
        """電話番号をマスク"""
        if not phone_number or len(phone_number) < 8:
            return phone_number
        
        # 中間4桁をマスク
        if len(phone_number) >= 11:
            return phone_number[:3] + "****" + phone_number[7:]
        else:
            return phone_number[:3] + "****" + phone_number[7:]
    
    def _extract_bill_features(self, bill_data: Dict) -> Dict:
        """請求書から特徴量を抽出"""
        breakdown = bill_data.get('breakdown', {})
        current_cost = bill_data.get('total_cost', 0)
        
        return {
            'current_cost_level': 'high' if current_cost > 5000 else 'medium' if current_cost > 3000 else 'low',
            'has_voice_option': breakdown.get('voice_option', 0) > 0,
            'has_discount': breakdown.get('discount', 0) < 0,
            'voice_cost_high': breakdown.get('voice', 0) > 2000,
            'data_cost_high': breakdown.get('data', 0) > 3000,
            'confidence': bill_data.get('confidence', 0.0)
        }
    
    def _write_log(self, filepath: str, data: Dict):
        """ログファイルに書き込み"""
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def _read_logs(self, filepath: str, days: int) -> List[Dict]:
        """ログファイルから読み込み"""
        if not os.path.exists(filepath):
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        logs = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_data = json.loads(line.strip())
                    log_date = datetime.fromisoformat(log_data.get('timestamp', ''))
                    
                    if log_date >= cutoff_date:
                        logs.append(log_data)
                        
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Invalid log line: {line.strip()}")
                    continue
        
        return logs
    
    def _update_log_field(self, log_id: str, field: str, value: Any):
        """ログの特定フィールドを更新"""
        # 簡易実装：全ログを読み込んで更新
        if not os.path.exists(self.log_file):
            return
        
        logs = []
        updated = False
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    log_data = json.loads(line.strip())
                    if log_data.get('log_id') == log_id:
                        log_data[field] = value
                        updated = True
                    logs.append(log_data)
                except json.JSONDecodeError:
                    continue
        
        if updated:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                for log_data in logs:
                    f.write(json.dumps(log_data, ensure_ascii=False) + '\n')
    
    def _empty_summary(self) -> Dict:
        """空のサマリーを返す"""
        return {
            'period_days': 0,
            'total_analyses': 0,
            'successful_analyses': 0,
            'error_rate': 0,
            'avg_processing_time': 0,
            'avg_ocr_confidence': 0,
            'avg_monthly_saving': 0,
            'plan_distribution': {},
            'cta_click_stats': {},
            'cta_click_rate': 0
        }

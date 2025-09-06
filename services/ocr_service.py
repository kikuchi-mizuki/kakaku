import os
import logging
from typing import Dict, List, Optional
from google.cloud import vision
import pytesseract
from PIL import Image
import cv2
import numpy as np
from config import Config

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        self.vision_client = None
        self._init_google_vision()
    
    def _init_google_vision(self):
        """Google Cloud Vision APIの初期化"""
        try:
            if Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
                self.vision_client = vision.ImageAnnotatorClient()
                logger.info("Google Cloud Vision API initialized successfully")
            else:
                logger.warning("Google Cloud Vision API credentials not found, using Tesseract fallback")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud Vision API: {str(e)}")
    
    def extract_text(self, image_path: str) -> Dict:
        """画像からテキストを抽出"""
        try:
            # 画像前処理
            processed_image_path = self._preprocess_image(image_path)
            
            # OCR実行（Google Vision API優先、Tesseractフォールバック）
            if self.vision_client:
                ocr_result = self._extract_with_google_vision(processed_image_path)
            else:
                ocr_result = self._extract_with_tesseract(processed_image_path)
            
            # 一時ファイルを削除
            if processed_image_path != image_path and os.path.exists(processed_image_path):
                os.remove(processed_image_path)
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'blocks': [],
                'error': str(e)
            }
    
    def _preprocess_image(self, image_path: str) -> str:
        """画像前処理（台形補正、傾き補正、二値化、ノイズ除去）"""
        try:
            # 画像を読み込み
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError("Could not load image")
            
            # グレースケール変換
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # ノイズ除去
            denoised = cv2.medianBlur(gray, 3)
            
            # 傾き補正
            corrected = self._correct_skew(denoised)
            
            # 二値化
            binary = cv2.adaptiveThreshold(
                corrected, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # 台形補正（簡易版）
            perspective_corrected = self._correct_perspective(binary)
            
            # 処理済み画像を保存
            processed_path = image_path.replace('.', '_processed.')
            cv2.imwrite(processed_path, perspective_corrected)
            
            return processed_path
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return image_path  # 元の画像を返す
    
    def _correct_skew(self, image: np.ndarray) -> np.ndarray:
        """傾き補正"""
        try:
            # エッジ検出
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            
            # 直線検出
            lines = cv2.HoughLines(edges, 1, np.pi/180, threshold=100)
            
            if lines is not None:
                # 角度を計算
                angles = []
                for line in lines:
                    rho, theta = line[0]
                    angle = theta * 180 / np.pi
                    if 45 < angle < 135:  # 水平線に近い角度
                        angles.append(angle - 90)
                
                if angles:
                    # 平均角度を計算
                    median_angle = np.median(angles)
                    
                    # 回転補正
                    if abs(median_angle) > 0.5:  # 0.5度以上の傾きがある場合
                        h, w = image.shape
                        center = (w // 2, h // 2)
                        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        corrected = cv2.warpAffine(image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                        return corrected
            
            return image
            
        except Exception as e:
            logger.error(f"Error correcting skew: {str(e)}")
            return image
    
    def _correct_perspective(self, image: np.ndarray) -> np.ndarray:
        """台形補正（簡易版）"""
        try:
            h, w = image.shape
            
            # 四角形の角を検出
            contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # 最大の輪郭を取得
                largest_contour = max(contours, key=cv2.contourArea)
                
                # 輪郭の近似
                epsilon = 0.02 * cv2.arcLength(largest_contour, True)
                approx = cv2.approxPolyDP(largest_contour, epsilon, True)
                
                if len(approx) == 4:
                    # 四角形の角を取得
                    points = approx.reshape(4, 2)
                    
                    # 台形補正
                    rect = cv2.minAreaRect(largest_contour)
                    box = cv2.boxPoints(rect)
                    box = np.int0(box)
                    
                    # 変換行列を計算
                    src_points = points.astype(np.float32)
                    dst_points = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
                    
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    corrected = cv2.warpPerspective(image, matrix, (w, h))
                    
                    return corrected
            
            return image
            
        except Exception as e:
            logger.error(f"Error correcting perspective: {str(e)}")
            return image
    
    def _extract_with_google_vision(self, image_path: str) -> Dict:
        """Google Cloud Vision APIでテキスト抽出"""
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)
            
            if response.error.message:
                raise Exception(f"Google Vision API error: {response.error.message}")
            
            texts = response.text_annotations
            if not texts:
                return {
                    'text': '',
                    'confidence': 0.0,
                    'blocks': [],
                    'method': 'google_vision'
                }
            
            # 全テキストを結合
            full_text = texts[0].description
            
            # ブロック情報を抽出
            blocks = []
            for text in texts[1:]:  # 最初の要素は全テキストなのでスキップ
                block = {
                    'text': text.description,
                    'bounding_box': [(vertex.x, vertex.y) for vertex in text.bounding_poly.vertices],
                    'confidence': getattr(text, 'confidence', 0.9)  # Google Vision APIは信頼度を提供しない場合がある
                }
                blocks.append(block)
            
            return {
                'text': full_text,
                'confidence': 0.9,  # Google Vision APIのデフォルト信頼度
                'blocks': blocks,
                'method': 'google_vision'
            }
            
        except Exception as e:
            logger.error(f"Error with Google Vision API: {str(e)}")
            # フォールバック
            return self._extract_with_tesseract(image_path)
    
    def _extract_with_tesseract(self, image_path: str) -> Dict:
        """Tesseractでテキスト抽出"""
        try:
            # 画像を読み込み
            image = Image.open(image_path)
            
            # OCR実行
            text = pytesseract.image_to_string(image, lang='jpn+eng')
            
            # 信頼度を取得
            data = pytesseract.image_to_data(image, lang='jpn+eng', output_type=pytesseract.Output.DICT)
            
            # 平均信頼度を計算
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
            
            # ブロック情報を抽出
            blocks = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:  # 信頼度が0より大きい場合のみ
                    block = {
                        'text': data['text'][i],
                        'bounding_box': [
                            (data['left'][i], data['top'][i]),
                            (data['left'][i] + data['width'][i], data['top'][i]),
                            (data['left'][i] + data['width'][i], data['top'][i] + data['height'][i]),
                            (data['left'][i], data['top'][i] + data['height'][i])
                        ],
                        'confidence': int(data['conf'][i]) / 100.0
                    }
                    blocks.append(block)
            
            return {
                'text': text,
                'confidence': avg_confidence,
                'blocks': blocks,
                'method': 'tesseract'
            }
            
        except Exception as e:
            logger.error(f"Error with Tesseract: {str(e)}")
            return {
                'text': '',
                'confidence': 0.0,
                'blocks': [],
                'method': 'tesseract',
                'error': str(e)
            }

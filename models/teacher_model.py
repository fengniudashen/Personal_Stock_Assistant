"""
预训练分类器包装器
包装 CNN/Transformer 分类模型，用于弱监督管道中的模型预测路
"""
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class TeacherModel:
    """预训练教师模型包装器
    
    支持:
    1. ONNX 格式模型推理
    2. PyTorch 模型推理
    3. 占位符模式（首轮训练前）
    """

    # 主标签（发声机制，互斥）
    LABELS = [
        'StrongMix', 'LightMix', 'Falsetto', 'Chest',
        'Head', 'Breathy', 'Strained', 'Neutral', 'Invalid'
    ]

    SECONDARY_TAGS = [
        'Pharyngeal', 'Twang', 'HighRange', 'SuperHighRange',
        'VowelMod', 'Vibrato', 'Glissando', 'Runs',
        'Demo_Correct', 'Demo_Error'
    ]

    def __init__(self, model_path: Optional[str] = None, model_type: str = 'onnx'):
        """
        Args:
            model_path: 模型文件路径 (ONNX/PyTorch)
            model_type: 'onnx', 'pytorch', 或 'placeholder'
        """
        self.model_path = model_path
        self.model_type = model_type
        self._model = None
        self._session = None

        if model_path and Path(model_path).exists():
            self._load_model()
        else:
            logger.info("使用占位符模式（模型尚未训练）")
            self.model_type = 'placeholder'

    def _load_model(self):
        """加载模型"""
        if self.model_type == 'onnx':
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(
                    self.model_path,
                    providers=['CPUExecutionProvider']
                )
                logger.info(f"✅ ONNX 模型加载: {self.model_path}")
            except Exception as e:
                logger.warning(f"ONNX 加载失败: {e}，降级为占位符")
                self.model_type = 'placeholder'

        elif self.model_type == 'pytorch':
            try:
                import torch
                self._model = torch.load(self.model_path, map_location='cpu')
                self._model.eval()
                logger.info(f"✅ PyTorch 模型加载: {self.model_path}")
            except Exception as e:
                logger.warning(f"PyTorch 加载失败: {e}，降级为占位符")
                self.model_type = 'placeholder'

    def predict(self, mel_spectrogram: np.ndarray) -> Dict[str, float]:
        """
        对单个 Mel 频谱图进行分类
        
        Args:
            mel_spectrogram: shape (n_mels, time_frames)
            
        Returns:
            {label: probability}
        """
        if self.model_type == 'placeholder':
            return self._placeholder_predict()

        if self.model_type == 'onnx':
            return self._onnx_predict(mel_spectrogram)

        elif self.model_type == 'pytorch':
            return self._pytorch_predict(mel_spectrogram)

        return self._placeholder_predict()

    def _onnx_predict(self, mel: np.ndarray) -> Dict[str, float]:
        """ONNX 推理"""
        try:
            # 预处理
            if mel.ndim == 2:
                mel = mel[np.newaxis, np.newaxis, :, :]  # (1, 1, n_mels, T)

            input_name = self._session.get_inputs()[0].name
            output_name = self._session.get_outputs()[0].name

            result = self._session.run(
                [output_name],
                {input_name: mel.astype(np.float32)}
            )[0]

            # Softmax
            probs = self._softmax(result[0])

            return {self.LABELS[i]: float(probs[i]) for i in range(min(len(probs), len(self.LABELS)))}

        except Exception as e:
            logger.error(f"ONNX 推理失败: {e}")
            return self._placeholder_predict()

    def _pytorch_predict(self, mel: np.ndarray) -> Dict[str, float]:
        """PyTorch 推理"""
        try:
            import torch

            if mel.ndim == 2:
                tensor = torch.FloatTensor(mel).unsqueeze(0).unsqueeze(0)
            else:
                tensor = torch.FloatTensor(mel)

            with torch.no_grad():
                output = self._model(tensor)
                probs = torch.softmax(output, dim=-1).numpy()[0]

            return {self.LABELS[i]: float(probs[i]) for i in range(min(len(probs), len(self.LABELS)))}

        except Exception as e:
            logger.error(f"PyTorch 推理失败: {e}")
            return self._placeholder_predict()

    def _placeholder_predict(self) -> Dict[str, float]:
        """占位符预测（均匀分布）"""
        n = len(self.LABELS)
        return {label: 1.0 / n for label in self.LABELS}

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Softmax"""
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def batch_predict(self, mel_paths: List[str]) -> Dict[str, Dict[str, float]]:
        """
        批量预测
        
        Args:
            mel_paths: Mel频谱图 .npy 文件路径列表
            
        Returns:
            {clip_id: {label: probability}}
        """
        results = {}

        for mel_path in mel_paths:
            clip_id = Path(mel_path).stem.replace('_mel', '')

            try:
                mel = np.load(mel_path)
                probs = self.predict(mel)
                results[clip_id] = probs
            except Exception as e:
                logger.error(f"预测失败: {mel_path} - {e}")
                results[clip_id] = self._placeholder_predict()

        return results


class ModelEnsemble:
    """模型集成：多模型投票"""

    def __init__(self, models: List[TeacherModel], weights: Optional[List[float]] = None):
        self.models = models
        if weights:
            self.weights = weights
        else:
            self.weights = [1.0 / len(models)] * len(models)

    def predict(self, mel_spectrogram: np.ndarray) -> Dict[str, float]:
        """加权集成预测"""
        from collections import defaultdict

        all_probs = defaultdict(float)

        for model, weight in zip(self.models, self.weights):
            probs = model.predict(mel_spectrogram)
            for label, prob in probs.items():
                all_probs[label] += weight * prob

        # 归一化
        total = sum(all_probs.values())
        if total > 0:
            all_probs = {k: v / total for k, v in all_probs.items()}

        return dict(all_probs)

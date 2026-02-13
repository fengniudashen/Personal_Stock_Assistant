"""
VibeSing Label Studio ML Backend
提供AI预标签服务，对接Label Studio
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logger = logging.getLogger(__name__)

# 尝试导入 Label Studio ML SDK
try:
    from label_studio_ml.model import LabelStudioMLBase
    HAS_LS_ML = True
except ImportError:
    logger.warning("label-studio-ml 未安装，使用占位基类")
    HAS_LS_ML = False
    class LabelStudioMLBase:
        """占位基类"""
        def __init__(self, **kwargs):
            self.parsed_label_config = {}
        def predict(self, tasks, **kwargs):
            return []
        def fit(self, event, data, **kwargs):
            pass


CONFIG_PATH = Path(__file__).parent.parent.parent / 'config_advanced.yaml'
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        APP_CONFIG = yaml.safe_load(f)
else:
    APP_CONFIG = {}

# 主标签（发声机制，互斥）
PRIMARY_LABELS = [
    'StrongMix', 'LightMix', 'Falsetto', 'Chest',
    'Head', 'Breathy', 'Strained', 'Neutral', 'Invalid'
]

# 辅标签（共鸣/色彩，可叠加）
SECONDARY_TAGS = [
    'Pharyngeal', 'Twang', 'HighRange', 'SuperHighRange',
    'VowelMod', 'Vibrato', 'Glissando', 'Runs',
    'Demo_Correct', 'Demo_Error'
]

QUALITY_FLAGS = [
    'LowSNR', 'HighReverb', 'Clipping', 'Unstable',
    'MultiVoice', 'Distortion'
]

# 向后兼容
LABEL_NAMES = PRIMARY_LABELS


class VibeSingMLBackend(LabelStudioMLBase):
    """
    VibeSing AI预标签后端
    
    为Label Studio提供自动预标签能力：
    1. 加载弱标签或教师模型预测
    2. 返回AI建议标签 + 置信度
    3. 接收标注结果用于模型更新
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = None
        self.labels_cache = {}
        self._load_model()
        self._load_cached_labels()

    def _load_model(self):
        """加载教师模型（如果可用）"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from models.teacher_model import TeacherModel
            model_path = APP_CONFIG.get('paths', {}).get('models', 'data/models')
            self.model = TeacherModel(APP_CONFIG)
            logger.info("教师模型已加载")
        except Exception as e:
            logger.warning(f"教师模型加载失败（将使用缓存标签）: {e}")
            self.model = None

    def _load_cached_labels(self):
        """加载预计算的弱标签"""
        cache_dir = Path(APP_CONFIG.get('paths', {}).get('labels', 'data/labels'))
        for json_file in cache_dir.glob('*.json') if cache_dir.exists() else []:
            try:
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    clip_id = json_file.stem
                    self.labels_cache[clip_id] = data
            except Exception:
                pass
        logger.info(f"已加载 {len(self.labels_cache)} 条缓存标签")

    def predict(self, tasks: List[Dict], **kwargs) -> List[Dict]:
        """
        为任务列表生成预标签
        
        Args:
            tasks: Label Studio 任务列表
            
        Returns:
            预测结果列表
        """
        predictions = []

        for task in tasks:
            audio_url = task.get('data', {}).get('audio_url', '')
            clip_id = Path(audio_url).stem if audio_url else ''

            # 方案1: 使用教师模型推理
            if self.model and audio_url:
                try:
                    result = self._predict_with_model(audio_url, clip_id)
                    if result:
                        predictions.append(result)
                        continue
                except Exception as e:
                    logger.warning(f"模型推理失败: {e}")

            # 方案2: 使用缓存的弱标签
            if clip_id in self.labels_cache:
                result = self._predict_from_cache(clip_id)
                predictions.append(result)
                continue

            # 方案3: 无预测
            predictions.append({
                'result': [],
                'score': 0.0,
                'model_version': 'none'
            })

        return predictions

    def _predict_with_model(self, audio_url: str, clip_id: str) -> Optional[Dict]:
        """使用教师模型进行推理"""
        # 提取特征
        try:
            import librosa
            import numpy as np

            audio_path = self._resolve_audio_path(audio_url)
            if not audio_path or not Path(audio_path).exists():
                return None

            y, sr = librosa.load(audio_path, sr=44100)
            mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
            mel_db = librosa.power_to_db(mel, ref=np.max)

            # 模型预测
            probabilities = self.model.predict_proba(mel_db)
            if probabilities is None:
                return None

            top_idx = int(np.argmax(probabilities))
            top_label = PRIMARY_LABELS[top_idx] if top_idx < len(PRIMARY_LABELS) else 'Neutral'
            confidence = float(probabilities[top_idx])

            result_items = [{
                'from_name': 'primary_label',
                'to_name': 'audio',
                'type': 'choices',
                'value': {'choices': [top_label]}
            }]

            return {
                'result': result_items,
                'score': confidence,
                'model_version': 'teacher_v2'
            }
        except Exception as e:
            logger.error(f"模型推理异常: {e}")
            return None

    def _predict_from_cache(self, clip_id: str) -> Dict:
        """从缓存的弱标签生成预测"""
        cached = self.labels_cache.get(clip_id, {})
        primary = cached.get('primary_label', 'Neutral')
        confidence = cached.get('confidence', 0.5)
        secondary = cached.get('secondary_tags', cached.get('secondary_labels', []))
        quality = cached.get('quality_flags', [])

        result_items = [{
            'from_name': 'primary_label',
            'to_name': 'audio',
            'type': 'choices',
            'value': {'choices': [primary]}
        }]

        if secondary:
            result_items.append({
                'from_name': 'secondary_tags',
                'to_name': 'audio',
                'type': 'choices',
                'value': {'choices': secondary}
            })

        if quality:
            result_items.append({
                'from_name': 'quality_flags',
                'to_name': 'audio',
                'type': 'choices',
                'value': {'choices': quality}
            })

        return {
            'result': result_items,
            'score': confidence,
            'model_version': 'weak_labels_v2'
        }

    def _resolve_audio_path(self, audio_url: str) -> Optional[str]:
        """解析音频URL到本地路径"""
        clips_dir = Path(APP_CONFIG.get('paths', {}).get('clips', 'data/clips'))
        filename = Path(audio_url).name
        local = clips_dir / filename
        if local.exists():
            return str(local)
        return None

    def fit(self, event, data, **kwargs):
        """
        接收标注完成事件，用于模型更新
        
        Args:
            event: 事件类型 (ANNOTATION_CREATED, etc.)
            data: 标注数据
        """
        if event == 'ANNOTATION_CREATED':
            annotation = data.get('annotation', {})
            task = data.get('task', {})
            clip_id = Path(task.get('data', {}).get('audio_url', '')).stem

            logger.info(f"收到标注: {clip_id} ({event})")

            # 提取标注的标签
            results = annotation.get('result', [])
            for r in results:
                if r.get('from_name') == 'primary_label':
                    label = r.get('value', {}).get('choices', [None])[0]
                    logger.info(f"  主标签: {label}")

            # TODO: 累计足够标注后触发模型重训练


# Label Studio ML Backend 入口
if __name__ == '__main__':
    if HAS_LS_ML:
        from label_studio_ml.api import init_app
        app = init_app(model_cls=VibeSingMLBackend)
        app.run(host='0.0.0.0', port=9090, debug=True)
    else:
        logger.error("请先安装: pip install label-studio-ml")
        print("Usage: pip install label-studio-ml && python ml_backend.py")

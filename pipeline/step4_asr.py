"""
Step 4: Whisper ASR 转录 + 关键词对齐
使用语音识别提取教学视频中的关键词，进行弱监督自动标注
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class ASRAnnotator:
    """ASR 转录 + 关键词匹配标注器"""

    def __init__(self, config: dict):
        self.config = config
        self.keywords = config['keywords']
        self.whisper_model = config['whisper']['model']
        self.language = config['whisper']['language']
        self.device = config['whisper']['device']
        self.use_faster = config['whisper'].get('use_faster_whisper', True)
        self._model = None

    def _load_model(self):
        """懒加载 Whisper 模型"""
        if self._model is not None:
            return

        if self.use_faster:
            try:
                from faster_whisper import WhisperModel
                logger.info(f"加载 faster-whisper 模型: {self.whisper_model}")
                compute_type = "float16" if self.device == "cuda" else "int8"
                self._model = WhisperModel(
                    self.whisper_model,
                    device=self.device,
                    compute_type=compute_type
                )
                self._model_type = "faster"
                logger.info("✅ faster-whisper 模型加载完成")
                return
            except ImportError:
                logger.warning("faster-whisper 未安装，尝试使用 openai-whisper")
            except Exception as e:
                logger.warning(f"faster-whisper 加载失败: {e}")

        try:
            import whisper
            logger.info(f"加载 openai-whisper 模型: {self.whisper_model}")
            self._model = whisper.load_model(self.whisper_model, device=self.device)
            self._model_type = "openai"
            logger.info("✅ openai-whisper 模型加载完成")
        except ImportError:
            logger.error("Whisper 未安装！请运行: pip install faster-whisper 或 openai-whisper")
            self._model = None
            self._model_type = None

    def transcribe(self, audio_path: str) -> Optional[Dict]:
        """
        转录音频文件
        
        Args:
            audio_path: 音频路径
            
        Returns:
            {text, segments: [{start, end, text}]}
        """
        self._load_model()
        if self._model is None:
            return None

        try:
            if self._model_type == "faster":
                segments, info = self._model.transcribe(
                    audio_path,
                    language=self.language,
                    beam_size=5,
                    word_timestamps=True
                )
                seg_list = []
                full_text = ""
                for seg in segments:
                    seg_list.append({
                        'start': seg.start,
                        'end': seg.end,
                        'text': seg.text.strip()
                    })
                    full_text += seg.text
                return {'text': full_text.strip(), 'segments': seg_list}
            else:
                result = self._model.transcribe(
                    audio_path,
                    language=self.language
                )
                seg_list = []
                for seg in result.get('segments', []):
                    seg_list.append({
                        'start': seg['start'],
                        'end': seg['end'],
                        'text': seg['text'].strip()
                    })
                return {'text': result['text'].strip(), 'segments': seg_list}

        except Exception as e:
            logger.error(f"转录失败: {audio_path} - {e}")
            return None

    def match_keywords(self, text: str) -> Dict[str, float]:
        """
        在文本中匹配关键词，返回各标签的概率分布
        
        Args:
            text: 转录文本
            
        Returns:
            {label: probability} 概率字典
        """
        if not text:
            return {}

        text_lower = text.lower()
        scores = {}

        for label, keyword_list in self.keywords.items():
            score = 0.0
            for keyword in keyword_list:
                keyword_lower = keyword.lower()
                # 精确匹配
                count = text_lower.count(keyword_lower)
                if count > 0:
                    score += count * 1.0
                # 模糊匹配（关键词在文本中出现部分）
                elif len(keyword_lower) >= 2:
                    for i in range(len(text_lower) - len(keyword_lower) + 1):
                        substring = text_lower[i:i + len(keyword_lower)]
                        if self._char_similarity(keyword_lower, substring) > 0.8:
                            score += 0.5
                            break

            if score > 0:
                scores[label] = score

        # 归一化为概率
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    @staticmethod
    def _char_similarity(s1: str, s2: str) -> float:
        """简单的字符相似度"""
        if not s1 or not s2:
            return 0.0
        matches = sum(1 for a, b in zip(s1, s2) if a == b)
        return matches / max(len(s1), len(s2))

    def align_clips_with_asr(self, clips_metadata: List[Dict],
                              source_transcription: Dict) -> Dict[str, Dict]:
        """
        将切片与ASR结果对齐
        
        通过时间戳匹配切片和转录文本，提取关键词标签
        
        Args:
            clips_metadata: 切片元数据列表
            source_transcription: 源音频的完整转录结果
            
        Returns:
            {clip_id: {label: probability}}
        """
        if not source_transcription or 'segments' not in source_transcription:
            return {}

        asr_segments = source_transcription['segments']
        clip_labels = {}

        for clip in clips_metadata:
            clip_id = clip['clip_id']
            clip_start = clip['t0']
            clip_end = clip['t1']

            # 找到时间重叠的ASR段
            relevant_text = ""
            for seg in asr_segments:
                seg_start = seg['start']
                seg_end = seg['end']

                # 时间重叠判断
                overlap_start = max(clip_start, seg_start)
                overlap_end = min(clip_end, seg_end)

                if overlap_start < overlap_end:
                    relevant_text += " " + seg['text']

            # 扩展上下文：也匹配前后5秒的文本
            context_text = ""
            for seg in asr_segments:
                if (seg['start'] >= clip_start - 5) and (seg['end'] <= clip_end + 5):
                    context_text += " " + seg['text']

            # 匹配关键词
            combined_text = relevant_text + " " + context_text
            label_probs = self.match_keywords(combined_text)

            if label_probs:
                clip_labels[clip_id] = label_probs

        return clip_labels

    def process_all_sources(self, clips_metadata_path: str,
                            audio_raw_dir: str) -> Dict:
        """
        处理所有源音频的ASR标注
        
        Args:
            clips_metadata_path: 切片元数据JSON路径
            audio_raw_dir: 原始音频目录
            
        Returns:
            所有切片的ASR预测结果
        """
        with open(clips_metadata_path, encoding='utf-8') as f:
            all_clips = json.load(f)

        audio_dir = Path(audio_raw_dir)
        all_predictions = {}

        # 按源文件分组
        source_groups = {}
        for clip in all_clips:
            source = clip.get('source', '')
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(clip)

        logger.info(f"共 {len(source_groups)} 个源文件需要转录")

        for source_path, clips in source_groups.items():
            source_file = Path(source_path)
            logger.info(f"🗣️ 转录: {source_file.name}")

            # 转录源文件
            transcription = self.transcribe(source_path)

            if transcription:
                logger.info(f"  文本长度: {len(transcription['text'])} 字")
                logger.info(f"  片段数: {len(transcription['segments'])}")

                # 对齐切片
                clip_labels = self.align_clips_with_asr(clips, transcription)
                all_predictions.update(clip_labels)

                logger.info(f"  匹配到 {len(clip_labels)} 个切片")

        return all_predictions


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    annotator = ASRAnnotator(config)

    clips_metadata_path = 'data/clips_metadata.json'
    audio_raw_dir = config['paths']['audio_raw']

    if not Path(clips_metadata_path).exists():
        logger.error("切片元数据不存在！请先运行 step3_slice.py")
        return

    # 处理
    predictions = annotator.process_all_sources(clips_metadata_path, audio_raw_dir)

    # 保存
    output_path = 'data/asr_predictions.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ ASR标注完成: {len(predictions)} 个切片")
    logger.info(f"📝 保存到: {output_path}")

    # 统计
    label_counts = {}
    for clip_id, probs in predictions.items():
        top_label = max(probs, key=probs.get) if probs else "Unknown"
        label_counts[top_label] = label_counts.get(top_label, 0) + 1

    logger.info("\n📊 标签分布:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {label}: {count}")


if __name__ == "__main__":
    main()

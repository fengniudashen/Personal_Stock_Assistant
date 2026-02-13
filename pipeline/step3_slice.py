"""
Step 3: 混合切片策略 - VAD + 能量检测 + 智能分段
将长音频切成 2.5-6 秒的标准片段用于标注
"""
import librosa
import numpy as np
import soundfile as sf
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from scipy.ndimage import median_filter
from scipy.signal import find_peaks
import yaml
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class HybridSlicer:
    """混合切片器：结合VAD和能量检测"""

    def __init__(self, config: dict):
        self.config = config
        self.sr = config['audio']['sample_rate']
        self.min_dur = config['slicing']['min_duration']
        self.max_dur = config['slicing']['max_duration']
        self.target_dur = config['slicing']['target_duration']
        self.overlap = config['slicing']['overlap']
        self.fade_dur = config['slicing']['fade_duration']
        self.silence_threshold = config['slicing']['silence_threshold']
        self.min_silence_dur = config['slicing']['min_silence_duration']

        # 尝试加载 webrtcvad
        self._vad = None
        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(config['vad']['aggressiveness'])
            self._vad_frame_ms = config['vad']['frame_duration_ms']
            self._vad_padding_ms = config['vad']['padding_duration_ms']
        except ImportError:
            logger.warning("webrtcvad 未安装，将仅使用能量检测切片")

    def vad_detect(self, audio_path: str) -> List[Tuple[float, float]]:
        """VAD(Voice Activity Detection)检测活动语音段"""
        if self._vad is None:
            return self._energy_vad_fallback(audio_path)

        import webrtcvad

        # VAD 需要 16kHz 16-bit PCM
        y, sr = librosa.load(audio_path, sr=16000)
        frame_duration = self._vad_frame_ms
        frame_length = int(sr * frame_duration / 1000)
        padding = self._vad_padding_ms / 1000

        # 逐帧检测
        frames = []
        for i in range(0, len(y) - frame_length, frame_length):
            frame = y[i:i + frame_length]
            frame_bytes = (frame * 32767).astype(np.int16).tobytes()
            try:
                is_speech = self._vad.is_speech(frame_bytes, sr)
            except Exception:
                is_speech = False
            frames.append((i / sr, is_speech))

        # 合并相邻活动段
        segments = []
        start = None

        for time_pos, is_speech in frames:
            if is_speech and start is None:
                start = max(0, time_pos - padding)
            elif not is_speech and start is not None:
                end = time_pos + padding
                if end - start >= self.min_dur:
                    segments.append((start, min(end, len(y) / sr)))
                start = None

        # 处理结尾
        if start is not None:
            end = len(y) / sr
            if end - start >= self.min_dur:
                segments.append((start, end))

        return segments

    def _energy_vad_fallback(self, audio_path: str) -> List[Tuple[float, float]]:
        """基于能量的VAD降级方案"""
        y, sr = librosa.load(audio_path, sr=self.sr)
        duration = len(y) / sr

        # 计算RMS能量
        frame_length = 2048
        hop_length = 512
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        # 转dB
        rms_db = librosa.amplitude_to_db(rms, ref=np.max)

        # 阈值
        threshold = self.silence_threshold
        is_active = rms_db > threshold

        # 合并连续活动帧
        segments = []
        start = None
        times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

        for i, active in enumerate(is_active):
            if active and start is None:
                start = times[i]
            elif not active and start is not None:
                end = times[i]
                if end - start >= self.min_dur:
                    segments.append((start, end))
                start = None

        if start is not None:
            if duration - start >= self.min_dur:
                segments.append((start, duration))

        return segments

    def energy_slice(self, y: np.ndarray, sr: int) -> List[Tuple[int, int]]:
        """基于能量的智能切片"""
        frame_length = 2048
        hop_length = 512
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        # 动态阈值
        threshold = np.percentile(rms, 30)

        # 平滑
        rms_smooth = median_filter(rms, size=5)

        # 寻找能量峰值
        peaks, properties = find_peaks(
            rms_smooth,
            height=threshold,
            distance=int(self.target_dur * sr / hop_length * 0.5)
        )

        # 基于峰值生成切片窗口
        target_frames = int(self.target_dur * sr / hop_length)
        segments = []

        for peak in peaks:
            start_frame = max(0, peak - target_frames // 2)
            end_frame = min(len(rms), peak + target_frames // 2)

            start_sample = start_frame * hop_length
            end_sample = min(end_frame * hop_length, len(y))

            segments.append((start_sample, end_sample))

        # 如果峰值法失败，使用固定窗口滑动
        if not segments:
            segments = self._fixed_window_slice(y, sr)

        return segments

    def _fixed_window_slice(self, y: np.ndarray, sr: int) -> List[Tuple[int, int]]:
        """固定窗口滑动切片（降级方案）"""
        target_samples = int(self.target_dur * sr)
        hop_samples = int((self.target_dur - self.overlap) * sr)
        segments = []

        for start in range(0, len(y) - target_samples, hop_samples):
            end = start + target_samples
            segments.append((start, end))

        return segments

    def _apply_fade(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """应用淡入淡出防止爆音"""
        fade_samples = int(self.fade_dur * sr)
        if fade_samples > 0 and len(audio) > 2 * fade_samples:
            audio = audio.copy()
            audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
            audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        return audio

    def slice_audio(self, audio_path: str, output_dir: Path) -> List[Dict]:
        """
        执行混合切片
        
        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录
            
        Returns:
            切片元数据列表
        """
        y, sr = librosa.load(audio_path, sr=self.sr, mono=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: VAD 粗切分
        vad_segments = self.vad_detect(audio_path)

        all_clips = []

        if not vad_segments:
            # VAD 无结果，直接用固定窗口
            logger.warning(f"VAD无检测结果，使用固定窗口: {Path(audio_path).name}")
            energy_segs = self._fixed_window_slice(y, sr)
            for seg_start, seg_end in energy_segs:
                clip_info = self._save_clip(
                    y, sr, seg_start, seg_end, 0,
                    audio_path, output_dir
                )
                if clip_info:
                    all_clips.append(clip_info)
        else:
            # Step 2: 每个VAD段内做能量细切分
            for vad_start, vad_end in vad_segments:
                start_sample = int(vad_start * sr)
                end_sample = min(int(vad_end * sr), len(y))
                segment_y = y[start_sample:end_sample]

                segment_duration = len(segment_y) / sr

                if segment_duration <= self.max_dur:
                    # 段本身够短，直接保存
                    clip_info = self._save_clip(
                        y, sr, start_sample, end_sample, 0,
                        audio_path, output_dir
                    )
                    if clip_info:
                        all_clips.append(clip_info)
                else:
                    # 段太长，用能量切片进一步分割
                    energy_segs = self.energy_slice(segment_y, sr)

                    for seg_start, seg_end in energy_segs:
                        global_start = start_sample + seg_start
                        global_end = start_sample + seg_end

                        clip_info = self._save_clip(
                            y, sr, global_start, global_end, 0,
                            audio_path, output_dir
                        )
                        if clip_info:
                            all_clips.append(clip_info)

        return all_clips

    def _save_clip(self, y: np.ndarray, sr: int,
                   start: int, end: int, offset: int,
                   source_path: str, output_dir: Path) -> Optional[Dict]:
        """保存单个切片并计算元信息"""
        end = min(end, len(y))
        clip_y = y[start:end]
        duration = len(clip_y) / sr

        # 过滤时长
        if not (self.min_dur <= duration <= self.max_dur):
            return None

        # 淡入淡出
        clip_y = self._apply_fade(clip_y, sr)

        # 文件名
        source_stem = Path(source_path).stem
        clip_name = f"{source_stem}_{start:08d}_{end:08d}.wav"
        clip_path = output_dir / clip_name

        # 保存
        sf.write(str(clip_path), clip_y, sr)

        # 计算元信息
        rms_val = float(np.sqrt(np.mean(clip_y ** 2)))
        zcr = float(np.mean(librosa.zero_crossings(clip_y)))

        # 简单音高估计
        pitches, magnitudes = librosa.piptrack(y=clip_y, sr=sr)
        valid_pitches = pitches[pitches > 0]
        pitch_mean = float(np.mean(valid_pitches)) if len(valid_pitches) > 0 else 0.0
        pitch_std = float(np.std(valid_pitches)) if len(valid_pitches) > 0 else 0.0

        return {
            'clip_id': clip_name.replace('.wav', ''),
            'path': str(clip_path),
            'source': str(source_path),
            't0': start / sr,
            't1': end / sr,
            'duration': duration,
            'rms': rms_val,
            'zcr': zcr,
            'pitch_mean': pitch_mean,
            'pitch_std': pitch_std
        }


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    slicer = HybridSlicer(config)

    # 收集所有清洗后的音频
    clean_dir = Path(config['paths']['audio_clean'])
    output_dir = Path(config['paths']['clips'])
    output_dir.mkdir(parents=True, exist_ok=True)

    all_clips = []

    # 搜索所有wav文件
    audio_files = list(clean_dir.rglob('*.wav'))

    if not audio_files:
        logger.warning(f"未找到音频文件: {clean_dir}")
        logger.info("尝试从 audio_raw 目录加载...")
        audio_files = list(Path(config['paths']['audio_raw']).glob('*.wav'))

    if not audio_files:
        logger.error("没有找到任何音频文件！请先运行 step1 和 step2。")
        return

    logger.info(f"找到 {len(audio_files)} 个音频文件")

    for idx, audio_file in enumerate(audio_files, 1):
        logger.info(f"[{idx}/{len(audio_files)}] 🔪 切片: {audio_file.name}")
        clips = slicer.slice_audio(str(audio_file), output_dir)
        all_clips.extend(clips)
        logger.info(f"  -> 生成 {len(clips)} 个片段")

    # 保存元数据
    metadata_path = Path('data') / 'clips_metadata.json'
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(all_clips, f, ensure_ascii=False, indent=2)

    logger.info(f"\n✅ 切片完成! 共生成 {len(all_clips)} 个片段")
    logger.info(f"📝 元数据已保存: {metadata_path}")


if __name__ == "__main__":
    main()

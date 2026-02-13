"""
Step 5: 多维特征提取
提取 Mel频谱、音高、声学参数（H1-H2、Jitter、Shimmer、HNR）和深度嵌入
"""
import numpy as np
import librosa
import soundfile as sf
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class FeatureExtractor:
    """多维音频特征提取器"""

    def __init__(self, config: dict):
        self.config = config
        self.sr = config['audio']['sample_rate']
        self.mel_config = config['features']['mel']
        self.pitch_config = config['features']['pitch']
        self.heuristic_config = config['features']['heuristics']
        self.output_dir = Path(config['paths']['features'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_mel_spectrogram(self, y: np.ndarray) -> np.ndarray:
        """提取Mel频谱图"""
        mel = librosa.feature.melspectrogram(
            y=y,
            sr=self.sr,
            n_mels=self.mel_config['n_mels'],
            n_fft=self.mel_config.get('n_fft', 2048),
            hop_length=self.mel_config.get('hop_length', 512),
            fmax=self.mel_config['fmax']
        )
        mel_db = librosa.power_to_db(mel, ref=np.max)
        return mel_db

    def extract_pitch(self, y: np.ndarray) -> Dict[str, Any]:
        """提取音高特征"""
        method = self.pitch_config['method']

        if method == 'pyin':
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=self.sr
            )
        elif method == 'crepe':
            try:
                import crepe
                _, f0, confidence, _ = crepe.predict(
                    y, self.sr,
                    viterbi=True,
                    model_capacity=self.pitch_config.get('model_capacity', 'tiny'),
                    step_size=10  # ms
                )
                voiced_flag = confidence > 0.5
                voiced_probs = confidence
            except ImportError:
                logger.warning("crepe 未安装，降级使用 pyin")
                f0, voiced_flag, voiced_probs = librosa.pyin(
                    y, fmin=librosa.note_to_hz('C2'),
                    fmax=librosa.note_to_hz('C7'),
                    sr=self.sr
                )
        else:
            # 默认 pyin
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y, fmin=librosa.note_to_hz('C2'),
                fmax=librosa.note_to_hz('C7'),
                sr=self.sr
            )

        # 处理NaN
        f0_clean = f0[~np.isnan(f0)] if f0 is not None else np.array([])

        result = {
            'f0_mean': float(np.mean(f0_clean)) if len(f0_clean) > 0 else 0.0,
            'f0_std': float(np.std(f0_clean)) if len(f0_clean) > 0 else 0.0,
            'f0_min': float(np.min(f0_clean)) if len(f0_clean) > 0 else 0.0,
            'f0_max': float(np.max(f0_clean)) if len(f0_clean) > 0 else 0.0,
            'f0_range': float(np.ptp(f0_clean)) if len(f0_clean) > 0 else 0.0,
            'voiced_ratio': float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0,
        }

        # 音高MIDI转换
        if len(f0_clean) > 0:
            midi_vals = librosa.hz_to_midi(f0_clean[f0_clean > 0])
            if len(midi_vals) > 0:
                result['midi_mean'] = float(np.mean(midi_vals))
                result['midi_max'] = float(np.max(midi_vals))
                # 判断是否高音区 (C5 = MIDI 72)
                result['is_high_range'] = bool(np.max(midi_vals) >= 72)

        return result

    def extract_spectral_features(self, y: np.ndarray) -> Dict[str, float]:
        """提取频谱特征"""
        # 频谱质心
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=self.sr)[0]

        # 频谱带宽
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=self.sr)[0]

        # 频谱滚降
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=self.sr)[0]

        # 频谱平坦度
        spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]

        # 色度特征
        chroma = librosa.feature.chroma_stft(y=y, sr=self.sr)

        # MFCC
        mfcc = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13)

        return {
            'spectral_centroid_mean': float(np.mean(spectral_centroid)),
            'spectral_centroid_std': float(np.std(spectral_centroid)),
            'spectral_bandwidth_mean': float(np.mean(spectral_bandwidth)),
            'spectral_rolloff_mean': float(np.mean(spectral_rolloff)),
            'spectral_flatness_mean': float(np.mean(spectral_flatness)),
            'chroma_mean': [float(x) for x in np.mean(chroma, axis=1)],
            'mfcc_mean': [float(x) for x in np.mean(mfcc, axis=1)],
            'mfcc_std': [float(x) for x in np.std(mfcc, axis=1)],
        }

    def extract_heuristic_features(self, y: np.ndarray) -> Dict[str, float]:
        """提取启发式声学特征（用于音色分类的先验知识）"""
        features = {}

        # RMS 能量
        rms = np.sqrt(np.mean(y ** 2))
        features['rms'] = float(rms)

        # 过零率
        zcr = np.mean(librosa.zero_crossings(y))
        features['zcr'] = float(zcr)

        # H1-H2（第一谐波与第二谐波差）- 气声度指标
        if self.heuristic_config.get('enable_h1h2', True):
            try:
                h1_h2 = self._compute_h1_h2(y)
                features['h1_h2'] = h1_h2
                # H1-H2 > 0 偏向气声, < 0 偏向紧张/挤卡
            except Exception:
                features['h1_h2'] = 0.0

        # 频谱倾斜 - 区分胸声/头声
        if self.heuristic_config.get('enable_spectral_tilt', True):
            try:
                tilt = self._compute_spectral_tilt(y)
                features['spectral_tilt'] = tilt
            except Exception:
                features['spectral_tilt'] = 0.0

        # Jitter (音高微扰) - 声音质量指标
        if self.heuristic_config.get('enable_jitter', True):
            try:
                import parselmouth
                snd = parselmouth.Sound(y, sampling_frequency=self.sr)
                point_process = parselmouth.praat.call(snd, "To PointProcess (periodic, cc)", 75, 600)
                jitter = parselmouth.praat.call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
                features['jitter'] = float(jitter) if not np.isnan(jitter) else 0.0
            except (ImportError, Exception):
                features['jitter'] = 0.0

        # Shimmer (振幅微扰)
        if self.heuristic_config.get('enable_shimmer', True):
            try:
                import parselmouth
                snd = parselmouth.Sound(y, sampling_frequency=self.sr)
                point_process = parselmouth.praat.call(snd, "To PointProcess (periodic, cc)", 75, 600)
                shimmer = parselmouth.praat.call(
                    [snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6
                )
                features['shimmer'] = float(shimmer) if not np.isnan(shimmer) else 0.0
            except (ImportError, Exception):
                features['shimmer'] = 0.0

        # HNR (谐波噪声比)
        if self.heuristic_config.get('enable_hnr', True):
            try:
                import parselmouth
                snd = parselmouth.Sound(y, sampling_frequency=self.sr)
                harmonicity = parselmouth.praat.call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
                hnr = parselmouth.praat.call(harmonicity, "Get mean", 0, 0)
                features['hnr'] = float(hnr) if not np.isnan(hnr) else 0.0
                # HNR高 = 干净声音, HNR低 = 气声/沙哑
            except (ImportError, Exception):
                features['hnr'] = 0.0

        return features

    def _compute_h1_h2(self, y: np.ndarray) -> float:
        """计算H1-H2（第一和第二谐波振幅差）"""
        # 使用FFT
        n_fft = 4096
        S = np.abs(np.fft.rfft(y, n=n_fft))
        freqs = np.fft.rfftfreq(n_fft, d=1.0 / self.sr)

        # 估算基频
        f0_est, _, _ = librosa.pyin(y, fmin=80, fmax=600, sr=self.sr)
        f0_clean = f0_est[~np.isnan(f0_est)]
        if len(f0_clean) == 0:
            return 0.0

        f0 = np.median(f0_clean)

        # 查找H1和H2振幅
        h1_idx = np.argmin(np.abs(freqs - f0))
        h2_idx = np.argmin(np.abs(freqs - 2 * f0))

        h1_amp = 20 * np.log10(S[h1_idx] + 1e-10)
        h2_amp = 20 * np.log10(S[h2_idx] + 1e-10)

        return float(h1_amp - h2_amp)

    def _compute_spectral_tilt(self, y: np.ndarray) -> float:
        """计算频谱倾斜度"""
        S = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=self.sr)

        # 对数频率上的线性回归斜率
        log_freqs = np.log10(freqs[1:] + 1e-10)
        log_S = np.log10(np.mean(S[1:], axis=1) + 1e-10)

        # 线性回归
        coeffs = np.polyfit(log_freqs, log_S, 1)
        return float(coeffs[0])

    def extract_all(self, audio_path: str) -> Dict:
        """提取所有特征"""
        y, sr = librosa.load(audio_path, sr=self.sr)

        result = {}

        # Mel频谱（保存为npy）
        mel = self.extract_mel_spectrogram(y)
        mel_path = self.output_dir / f"{Path(audio_path).stem}_mel.npy"
        np.save(str(mel_path), mel)
        result['mel_path'] = str(mel_path)
        result['mel_shape'] = list(mel.shape)

        # 音高
        pitch_features = self.extract_pitch(y)
        result.update(pitch_features)

        # 频谱特征
        spectral_features = self.extract_spectral_features(y)
        result.update(spectral_features)

        # 启发式特征
        heuristic_features = self.extract_heuristic_features(y)
        result.update(heuristic_features)

        return result

    def batch_extract(self, clips_metadata_path: str) -> List[Dict]:
        """批量提取特征"""
        with open(clips_metadata_path, encoding='utf-8') as f:
            clips = json.load(f)

        logger.info(f"开始提取 {len(clips)} 个切片的特征...")

        results = []
        for idx, clip in enumerate(clips, 1):
            clip_path = clip['path']
            clip_id = clip['clip_id']

            if idx % 50 == 0 or idx == 1:
                logger.info(f"[{idx}/{len(clips)}] 提取特征: {clip_id}")

            try:
                features = self.extract_all(clip_path)
                features['clip_id'] = clip_id
                features['path'] = clip_path
                results.append(features)
            except Exception as e:
                logger.error(f"特征提取失败: {clip_id} - {e}")
                results.append({'clip_id': clip_id, 'error': str(e)})

        return results


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    extractor = FeatureExtractor(config)

    clips_metadata_path = 'data/clips_metadata.json'
    if not Path(clips_metadata_path).exists():
        logger.error("切片元数据不存在！请先运行 step3_slice.py")
        return

    results = extractor.batch_extract(clips_metadata_path)

    # 保存特征元数据
    output_path = 'data/features_metadata.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 保存启发式分数（供弱监督使用）
    heuristic_scores = {}
    for r in results:
        if 'error' not in r:
            clip_id = r['clip_id']
            heuristic_scores[clip_id] = {
                'h1_h2': r.get('h1_h2', 0),
                'spectral_tilt': r.get('spectral_tilt', 0),
                'jitter': r.get('jitter', 0),
                'shimmer': r.get('shimmer', 0),
                'hnr': r.get('hnr', 0),
                'zcr': r.get('zcr', 0),
                'rms': r.get('rms', 0),
            }

    with open('data/heuristic_scores.json', 'w', encoding='utf-8') as f:
        json.dump(heuristic_scores, f, indent=2)

    valid_count = sum(1 for r in results if 'error' not in r)
    logger.info(f"\n✅ 特征提取完成: {valid_count}/{len(results)} 成功")
    logger.info(f"📝 保存到: {output_path}")


if __name__ == "__main__":
    main()

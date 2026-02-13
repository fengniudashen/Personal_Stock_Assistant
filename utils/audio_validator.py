"""
音频质量验证器
检查音频文件的采样率、时长、信噪比、削波失真等指标
"""
import numpy as np
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class AudioValidator:
    """音频质量验证器"""

    def __init__(self, config: dict):
        self.config = config
        filters = config.get('filters', {})
        slicing = config.get('slicing', {})

        self.min_sr = filters.get('min_sample_rate', 22050)
        self.min_dur = slicing.get('min_duration', 2.5)
        self.max_dur = slicing.get('max_duration', 6.0)
        self.min_snr = 10  # 最低信噪比(dB)
        self.max_clipping = 0.01  # 最大削波比例

    def validate(self, audio_path: str) -> Dict:
        """
        验证音频质量
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            {valid: bool, reason: str, metrics: {...}}
        """
        try:
            import librosa

            y, sr = librosa.load(audio_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)

            # 检查采样率
            if sr < self.min_sr:
                return {
                    'valid': False,
                    'reason': f'采样率过低: {sr}Hz (最低{self.min_sr}Hz)',
                    'sample_rate': sr
                }

            # 检查时长
            if not (self.min_dur <= duration <= self.max_dur):
                return {
                    'valid': False,
                    'reason': f'时长不符: {duration:.1f}s (要求{self.min_dur}-{self.max_dur}s)',
                    'duration': duration
                }

            # 计算信噪比
            rms = np.sqrt(np.mean(y ** 2))
            noise_floor = np.percentile(np.abs(y), 10)
            snr = 20 * np.log10(rms / (noise_floor + 1e-10))

            if snr < self.min_snr:
                return {
                    'valid': False,
                    'reason': f'SNR过低: {snr:.1f}dB (最低{self.min_snr}dB)',
                    'snr': float(snr)
                }

            # 检查削波失真
            clipping_ratio = np.sum(np.abs(y) > 0.99) / len(y)
            if clipping_ratio > self.max_clipping:
                return {
                    'valid': False,
                    'reason': f'削波失真: {clipping_ratio:.2%}',
                    'clipping_ratio': float(clipping_ratio)
                }

            # 检查是否为静音
            if rms < 0.001:
                return {
                    'valid': False,
                    'reason': '音频几乎静音',
                    'rms': float(rms)
                }

            # 检查是否为纯噪声（过零率极高）
            zcr = np.mean(librosa.zero_crossings(y))
            if zcr > 0.5:
                return {
                    'valid': False,
                    'reason': f'疑似纯噪声(ZCR={zcr:.3f})',
                    'zcr': float(zcr)
                }

            return {
                'valid': True,
                'sample_rate': sr,
                'duration': float(duration),
                'snr': float(snr),
                'rms': float(rms),
                'clipping_ratio': float(clipping_ratio),
                'zcr': float(zcr)
            }

        except Exception as e:
            return {'valid': False, 'reason': f'读取失败: {e}'}

    def validate_batch(self, audio_dir: str, pattern: str = '*.wav') -> Dict:
        """
        批量验证目录下的音频文件
        
        Returns:
            {valid: [...], invalid: [...], summary: {...}}
        """
        audio_dir = Path(audio_dir)
        valid_clips = []
        invalid_clips = []

        audio_files = list(audio_dir.glob(pattern))
        if not audio_files:
            logger.warning(f"未找到音频文件: {audio_dir}/{pattern}")
            return {'valid': [], 'invalid': [], 'summary': {'total': 0}}

        logger.info(f"验证 {len(audio_files)} 个音频文件...")

        for idx, audio_file in enumerate(audio_files, 1):
            if idx % 100 == 0:
                logger.info(f"  [{idx}/{len(audio_files)}]")

            result = self.validate(str(audio_file))
            result['path'] = str(audio_file)
            result['filename'] = audio_file.name

            if result['valid']:
                valid_clips.append(result)
            else:
                invalid_clips.append(result)

        total = len(valid_clips) + len(invalid_clips)
        summary = {
            'total': total,
            'valid_count': len(valid_clips),
            'invalid_count': len(invalid_clips),
            'valid_ratio': len(valid_clips) / total if total > 0 else 0
        }

        # 无效原因统计
        if invalid_clips:
            reasons = {}
            for clip in invalid_clips:
                reason = clip.get('reason', 'Unknown')
                # 简化原因
                simple_reason = reason.split(':')[0] if ':' in reason else reason
                reasons[simple_reason] = reasons.get(simple_reason, 0) + 1
            summary['invalid_reasons'] = reasons

        logger.info(f"\n✅ 验证完成: {len(valid_clips)} 有效 / {len(invalid_clips)} 无效")
        if invalid_clips:
            logger.info("无效原因分布:")
            for reason, count in sorted(summary.get('invalid_reasons', {}).items(), key=lambda x: -x[1]):
                logger.info(f"  {reason}: {count}")

        return {
            'valid': valid_clips,
            'invalid': invalid_clips,
            'summary': summary
        }


def main():
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    validator = AudioValidator(config)

    clips_dir = config['paths']['clips']
    results = validator.validate_batch(clips_dir)

    output_path = 'data/validation_report.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"📝 验证报告已保存: {output_path}")


if __name__ == "__main__":
    main()

"""
音频去重工具
基于 MFCC/嵌入 余弦相似度检测重复音频
"""
import numpy as np
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class AudioDeduplicator:
    """音频去重器"""

    def __init__(self, config: dict):
        self.config = config
        self.threshold = config.get('clustering', {}).get('dedup_threshold', 0.95)

    def compute_fingerprint(self, audio_path: str) -> Optional[np.ndarray]:
        """计算音频指纹（MFCC统计量）"""
        try:
            import librosa
            y, sr = librosa.load(audio_path, sr=22050)
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
            # 取均值和标准差作为指纹
            fingerprint = np.concatenate([
                np.mean(mfcc, axis=1),
                np.std(mfcc, axis=1),
            ])
            return fingerprint
        except Exception as e:
            logger.error(f"指纹计算失败: {audio_path} - {e}")
            return None

    def find_duplicates_from_fingerprints(
        self, fingerprints: np.ndarray, ids: List[str]
    ) -> List[Tuple[str, str, float]]:
        """从指纹矩阵中查找重复对"""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
        except ImportError:
            logger.error("sklearn 未安装")
            return []

        sim_matrix = cosine_similarity(fingerprints)
        duplicates = []

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                similarity = float(sim_matrix[i][j])
                if similarity >= self.threshold:
                    duplicates.append((ids[i], ids[j], similarity))

        duplicates.sort(key=lambda x: -x[2])
        return duplicates

    def find_duplicates_in_dir(self, audio_dir: str, pattern: str = '*.wav') -> List[Tuple]:
        """在目录中查找重复音频"""
        audio_dir = Path(audio_dir)
        audio_files = sorted(audio_dir.glob(pattern))

        if len(audio_files) < 2:
            return []

        logger.info(f"计算 {len(audio_files)} 个音频的指纹...")

        ids = []
        fingerprints = []

        for idx, f in enumerate(audio_files, 1):
            if idx % 100 == 0:
                logger.info(f"  [{idx}/{len(audio_files)}]")

            fp = self.compute_fingerprint(str(f))
            if fp is not None:
                ids.append(f.name)
                fingerprints.append(fp)

        if len(fingerprints) < 2:
            return []

        fingerprints_array = np.vstack(fingerprints)
        duplicates = self.find_duplicates_from_fingerprints(fingerprints_array, ids)

        logger.info(f"发现 {len(duplicates)} 对重复 (阈值={self.threshold})")
        return duplicates

    def remove_duplicates(self, audio_dir: str,
                           duplicates: List[Tuple],
                           dry_run: bool = True) -> List[str]:
        """
        移除重复文件（保留每对中的第一个）
        
        Args:
            audio_dir: 音频目录
            duplicates: 重复对列表
            dry_run: 仅模拟，不实际删除
            
        Returns:
            要删除的文件列表
        """
        to_remove = set()

        for id1, id2, sim in duplicates:
            # 保留第一个，标记第二个删除
            if id2 not in to_remove:
                to_remove.add(id2)

        if dry_run:
            logger.info(f"[DRY RUN] 将删除 {len(to_remove)} 个重复文件")
            for f in sorted(to_remove)[:20]:
                logger.info(f"  待删除: {f}")
            if len(to_remove) > 20:
                logger.info(f"  ... 还有 {len(to_remove) - 20} 个")
        else:
            audio_dir = Path(audio_dir)
            removed = []
            for filename in to_remove:
                file_path = audio_dir / filename
                if file_path.exists():
                    file_path.unlink()
                    removed.append(filename)
            logger.info(f"已删除 {len(removed)} 个重复文件")

        return list(to_remove)


def main():
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    dedup = AudioDeduplicator(config)

    clips_dir = config['paths']['clips']
    duplicates = dedup.find_duplicates_in_dir(clips_dir)

    if duplicates:
        with open('data/duplicates_detail.json', 'w', encoding='utf-8') as f:
            json.dump(
                [{'file1': d[0], 'file2': d[1], 'similarity': d[2]} for d in duplicates],
                f, indent=2
            )
        logger.info(f"📝 重复报告已保存: data/duplicates_detail.json")

        # 模拟删除
        dedup.remove_duplicates(clips_dir, duplicates, dry_run=True)


if __name__ == "__main__":
    main()

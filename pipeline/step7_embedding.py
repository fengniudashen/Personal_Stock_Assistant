"""
Step 7: 音频嵌入提取 + FAISS 索引构建
使用 OpenL3/MFCC 提取音频嵌入向量，构建 FAISS 索引用于去重和近邻搜索
"""
import numpy as np
import librosa
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class EmbeddingExtractor:
    """音频嵌入提取器"""

    def __init__(self, config: dict):
        self.config = config
        self.sr = config['audio']['sample_rate']
        self.embedding_config = config['features']['embedding']
        self.output_dir = Path(config['paths']['features'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._use_openl3 = False

    def _load_model(self):
        """加载嵌入模型"""
        if self._model is not None:
            return

        model_name = self.embedding_config.get('model', 'mfcc')

        if model_name == 'openl3':
            try:
                import openl3
                self._model = openl3
                self._use_openl3 = True
                logger.info("✅ OpenL3 模型加载完成")
                return
            except ImportError:
                logger.warning("OpenL3 未安装，使用 MFCC 嵌入替代")

        # 降级：使用 MFCC 均值作为嵌入
        self._model = "mfcc_fallback"
        self._use_openl3 = False
        logger.info("使用 MFCC 嵌入")

    def extract_embedding(self, audio_path: str) -> Optional[np.ndarray]:
        """
        提取单个音频的嵌入向量
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            嵌入向量 (numpy array)
        """
        self._load_model()

        try:
            y, sr = librosa.load(audio_path, sr=self.sr)

            if self._use_openl3:
                import openl3
                embedding, ts = openl3.get_audio_embedding(
                    y, sr,
                    content_type=self.embedding_config.get('content_type', 'music'),
                    embedding_size=self.embedding_config.get('embedding_size', 512),
                    hop_size=self.embedding_config.get('hop_size', 0.1)
                )
                # 取时间维度的均值
                return np.mean(embedding, axis=0)
            else:
                # MFCC嵌入：取统计量组合
                mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
                chroma = librosa.feature.chroma_stft(y=y, sr=sr)
                spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
                spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)

                # 拼接统计量
                features = np.concatenate([
                    np.mean(mfcc, axis=1),       # 40
                    np.std(mfcc, axis=1),        # 40
                    np.mean(chroma, axis=1),     # 12
                    np.std(chroma, axis=1),      # 12
                    [np.mean(spectral_centroid)], # 1
                    [np.std(spectral_centroid)],  # 1
                    [np.mean(spectral_bandwidth)], # 1
                    [np.std(spectral_bandwidth)],  # 1
                ])

                return features  # 108维

        except Exception as e:
            logger.error(f"嵌入提取失败: {audio_path} - {e}")
            return None

    def batch_extract(self, clips_metadata_path: str) -> Dict:
        """
        批量提取嵌入
        
        Returns:
            {clip_ids, embeddings(np.array), failed_ids}
        """
        with open(clips_metadata_path, encoding='utf-8') as f:
            clips = json.load(f)

        logger.info(f"开始提取 {len(clips)} 个切片的嵌入...")

        clip_ids = []
        embeddings = []
        failed_ids = []

        for idx, clip in enumerate(clips, 1):
            clip_id = clip['clip_id']
            clip_path = clip['path']

            if idx % 100 == 0 or idx == 1:
                logger.info(f"[{idx}/{len(clips)}] 嵌入提取...")

            emb = self.extract_embedding(clip_path)
            if emb is not None:
                clip_ids.append(clip_id)
                embeddings.append(emb)
            else:
                failed_ids.append(clip_id)

        if embeddings:
            embeddings_array = np.vstack(embeddings)
        else:
            embeddings_array = np.array([])

        logger.info(f"✅ 嵌入提取完成: {len(clip_ids)}/{len(clips)} 成功")
        logger.info(f"  嵌入维度: {embeddings_array.shape if len(embeddings_array) > 0 else '空'}")

        return {
            'clip_ids': clip_ids,
            'embeddings': embeddings_array,
            'failed_ids': failed_ids
        }

    def build_faiss_index(self, embeddings: np.ndarray, index_path: str):
        """构建 FAISS 索引"""
        try:
            import faiss

            d = embeddings.shape[1]
            n = embeddings.shape[0]

            logger.info(f"构建 FAISS 索引: {n} 向量, {d} 维")

            # 选择索引类型
            if n < 1000:
                # 小数据集用精确搜索
                index = faiss.IndexFlatL2(d)
            else:
                # 大数据集用IVF索引
                nlist = min(int(np.sqrt(n)), 256)
                quantizer = faiss.IndexFlatL2(d)
                index = faiss.IndexIVFFlat(quantizer, d, nlist)
                index.train(embeddings.astype(np.float32))

            index.add(embeddings.astype(np.float32))

            # 保存
            faiss.write_index(index, index_path)
            logger.info(f"✅ FAISS 索引已保存: {index_path}")

            return index

        except ImportError:
            logger.warning("FAISS 未安装，跳过索引构建")
            logger.info("可以使用: pip install faiss-cpu")
            return None

    def find_duplicates(self, embeddings: np.ndarray, clip_ids: List[str],
                        threshold: float = 0.95) -> List[tuple]:
        """
        使用嵌入查找重复/相似样本
        
        Returns:
            重复对列表 [(clip_id_1, clip_id_2, similarity)]
        """
        if len(embeddings) == 0:
            return []

        try:
            from sklearn.metrics.pairwise import cosine_similarity

            # 计算余弦相似度
            sim_matrix = cosine_similarity(embeddings)

            duplicates = []
            for i in range(len(clip_ids)):
                for j in range(i + 1, len(clip_ids)):
                    if sim_matrix[i][j] >= threshold:
                        duplicates.append((
                            clip_ids[i],
                            clip_ids[j],
                            float(sim_matrix[i][j])
                        ))

            logger.info(f"发现 {len(duplicates)} 对重复/高度相似样本 (阈值={threshold})")
            return duplicates

        except ImportError:
            logger.warning("sklearn 未安装，跳过去重检测")
            return []


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    extractor = EmbeddingExtractor(config)

    clips_metadata_path = 'data/clips_metadata.json'
    if not Path(clips_metadata_path).exists():
        logger.error("切片元数据不存在！请先运行前置步骤。")
        return

    # 提取嵌入
    result = extractor.batch_extract(clips_metadata_path)

    clip_ids = result['clip_ids']
    embeddings = result['embeddings']

    if len(embeddings) == 0:
        logger.error("没有成功提取任何嵌入！")
        return

    # 保存嵌入
    embeddings_path = Path(config['paths']['features']) / 'embeddings.npy'
    np.save(str(embeddings_path), embeddings)
    logger.info(f"📦 嵌入已保存: {embeddings_path}")

    # 保存ID映射
    id_map_path = Path(config['paths']['features']) / 'clip_ids.json'
    with open(id_map_path, 'w', encoding='utf-8') as f:
        json.dump(clip_ids, f)

    # 构建FAISS索引
    faiss_path = config['paths']['faiss_index']
    Path(faiss_path).parent.mkdir(parents=True, exist_ok=True)
    extractor.build_faiss_index(embeddings, faiss_path)

    # 去重检测
    dedup_threshold = config['clustering'].get('dedup_threshold', 0.95)
    duplicates = extractor.find_duplicates(embeddings, clip_ids, dedup_threshold)

    if duplicates:
        with open('data/duplicates.json', 'w', encoding='utf-8') as f:
            json.dump(duplicates, f, indent=2)
        logger.info(f"📝 重复对已保存: data/duplicates.json")


if __name__ == "__main__":
    main()

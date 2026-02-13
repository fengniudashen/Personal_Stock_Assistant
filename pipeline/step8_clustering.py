"""
Step 8: 相似片段聚类
使用 HDBSCAN 对音频嵌入进行聚类，便于批量标注相似样本
"""
import numpy as np
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter, defaultdict
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class AudioClusterer:
    """音频片段聚类器"""

    def __init__(self, config: dict):
        self.config = config
        self.method = config['clustering']['method']
        self.min_cluster_size = config['clustering']['min_cluster_size']
        self.min_samples = config['clustering'].get('min_samples', 2)

    def cluster_hdbscan(self, embeddings: np.ndarray) -> np.ndarray:
        """使用 HDBSCAN 聚类"""
        try:
            import hdbscan

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=self.min_samples,
                metric='euclidean',
                cluster_selection_method='eom'
            )

            labels = clusterer.fit_predict(embeddings.astype(np.float64))
            probabilities = clusterer.probabilities_

            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)

            logger.info(f"HDBSCAN 聚类结果:")
            logger.info(f"  聚类数: {n_clusters}")
            logger.info(f"  噪声点: {n_noise}")

            return labels

        except ImportError:
            logger.warning("HDBSCAN 未安装，使用 KMeans 替代")
            return self.cluster_kmeans(embeddings)

    def cluster_kmeans(self, embeddings: np.ndarray, n_clusters: int = 20) -> np.ndarray:
        """使用 KMeans 聚类（降级方案）"""
        from sklearn.cluster import KMeans

        # 自适应簇数
        n_samples = len(embeddings)
        n_clusters = min(n_clusters, n_samples // max(self.min_cluster_size, 2))
        n_clusters = max(n_clusters, 2)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        logger.info(f"KMeans 聚类结果: {n_clusters} 个簇")
        return labels

    def cluster(self, embeddings: np.ndarray) -> np.ndarray:
        """执行聚类"""
        if self.method == 'hdbscan':
            return self.cluster_hdbscan(embeddings)
        elif self.method == 'kmeans':
            return self.cluster_kmeans(embeddings)
        else:
            logger.warning(f"未知聚类方法: {self.method}，使用 HDBSCAN")
            return self.cluster_hdbscan(embeddings)

    def analyze_clusters(self, cluster_labels: np.ndarray,
                          clip_ids: List[str],
                          fused_labels: List[Dict]) -> List[Dict]:
        """
        分析聚类结果，统计每个簇的标签分布
        
        Returns:
            簇信息列表
        """
        # 构建 fused_labels 查找表
        fused_lookup = {item['clip_id']: item for item in fused_labels}

        # 按簇分组
        clusters_info = []
        unique_labels = sorted(set(cluster_labels))

        for cluster_id in unique_labels:
            if cluster_id == -1:
                continue  # 跳过噪声点

            indices = np.where(cluster_labels == cluster_id)[0]
            cluster_clip_ids = [clip_ids[i] for i in indices]

            # 统计簇内标签分布
            label_distribution = Counter()
            confidences = []

            for cid in cluster_clip_ids:
                if cid in fused_lookup:
                    item = fused_lookup[cid]
                    label_distribution[item['suggested_label']] += 1
                    confidences.append(item['confidence'])

            # 簇内一致性
            total = sum(label_distribution.values())
            dominant_label = label_distribution.most_common(1)[0] if label_distribution else ('Unknown', 0)
            consistency = dominant_label[1] / total if total > 0 else 0

            clusters_info.append({
                'cluster_id': int(cluster_id),
                'size': len(cluster_clip_ids),
                'clip_ids': cluster_clip_ids,
                'dominant_label': dominant_label[0],
                'consistency': float(consistency),
                'avg_confidence': float(np.mean(confidences)) if confidences else 0.0,
                'label_distribution': dict(label_distribution)
            })

        # 按大小排序
        clusters_info.sort(key=lambda x: x['size'], reverse=True)

        return clusters_info

    def propagate_labels(self, cluster_labels: np.ndarray,
                          clip_ids: List[str],
                          fused_labels: List[Dict]) -> Dict:
        """
        簇内标签传播（近邻传播）
        
        对于簇内尚未被其他方法覆盖的样本，
        使用簇内已有高置信度标签进行传播
        
        Returns:
            {clip_id: {label: probability}}
        """
        fused_lookup = {item['clip_id']: item for item in fused_labels}
        propagated = {}

        unique_labels = sorted(set(cluster_labels))

        for cluster_id in unique_labels:
            if cluster_id == -1:
                continue

            indices = np.where(cluster_labels == cluster_id)[0]
            cluster_clip_ids = [clip_ids[i] for i in indices]

            # 收集簇内已有的高置信度标签
            high_conf_labels = Counter()
            for cid in cluster_clip_ids:
                if cid in fused_lookup:
                    item = fused_lookup[cid]
                    if item['confidence'] >= 0.6:
                        high_conf_labels[item['suggested_label']] += 1

            if not high_conf_labels:
                continue

            # 将分布作为近邻传播结果
            total = sum(high_conf_labels.values())
            label_probs = {k: v / total for k, v in high_conf_labels.items()}

            for cid in cluster_clip_ids:
                propagated[cid] = label_probs

        logger.info(f"近邻传播覆盖 {len(propagated)} 个样本")
        return propagated


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    clusterer = AudioClusterer(config)

    # 加载嵌入
    embeddings_path = Path(config['paths']['features']) / 'embeddings.npy'
    clip_ids_path = Path(config['paths']['features']) / 'clip_ids.json'

    if not embeddings_path.exists() or not clip_ids_path.exists():
        logger.error("嵌入数据不存在！请先运行 step7_embedding.py")
        return

    embeddings = np.load(str(embeddings_path))
    with open(clip_ids_path, encoding='utf-8') as f:
        clip_ids = json.load(f)

    logger.info(f"加载 {len(clip_ids)} 个嵌入，维度 {embeddings.shape}")

    # 聚类
    cluster_labels = clusterer.cluster(embeddings)

    # 保存聚类结果
    cluster_map = {clip_ids[i]: int(cluster_labels[i]) for i in range(len(clip_ids))}
    with open('data/cluster_assignments.json', 'w', encoding='utf-8') as f:
        json.dump(cluster_map, f, indent=2)

    # 分析（如果有融合标签）
    fused_path = Path('data/fused_labels.json')
    if fused_path.exists():
        with open(fused_path, encoding='utf-8') as f:
            fused_labels = json.load(f)

        clusters_info = clusterer.analyze_clusters(cluster_labels, clip_ids, fused_labels)

        with open('data/clusters_info.json', 'w', encoding='utf-8') as f:
            json.dump(clusters_info, f, indent=2, ensure_ascii=False)

        # 近邻传播
        propagated = clusterer.propagate_labels(cluster_labels, clip_ids, fused_labels)

        with open('data/neighbor_propagation.json', 'w', encoding='utf-8') as f:
            json.dump(propagated, f, indent=2)

        logger.info(f"\n📊 聚类统计:")
        for info in clusters_info[:10]:
            logger.info(
                f"  簇#{info['cluster_id']}: {info['size']}样本, "
                f"主标签={info['dominant_label']}({info['consistency']:.0%}), "
                f"平均置信度={info['avg_confidence']:.2f}"
            )

    logger.info(f"\n✅ 聚类完成")


if __name__ == "__main__":
    main()

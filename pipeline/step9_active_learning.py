"""
Step 9: 主动学习调度
选择最有价值的样本优先标注：不确定性 + 多样性混合策略
"""
import numpy as np
import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class ActiveLearningScheduler:
    """主动学习调度器：不确定性 + 多样性混合采样"""

    def __init__(self, config: dict):
        self.config = config
        self.uncertainty_weight = config['active_learning']['uncertainty_weight']
        self.batch_size = config['active_learning']['batch_size']
        self.diversity_lambda = config['active_learning'].get('diversity_lambda', 0.1)
        self.conflict_bonus = config['active_learning'].get('conflict_bonus', 0.3)

    def uncertainty_sampling(self, fused_labels: List[Dict]) -> np.ndarray:
        """基于不确定性的采样分数"""
        scores = []

        for item in fused_labels:
            # 1. 熵
            probs = [p['prob'] for p in item.get('top3_labels', []) if p['prob'] > 0]
            if probs:
                entropy = -sum(p * np.log(p + 1e-10) for p in probs)
            else:
                entropy = 0.0

            # 2. Margin（top1与top2差距越小越不确定）
            margin_inv = 1 - item.get('margin', 0)

            # 3. 冲突度
            conflict = item.get('conflict_score', 0)

            # 4. 需人工复审标记加分
            review_bonus = 0.2 if item.get('needs_review', False) else 0.0

            # 加权组合
            score = (
                0.35 * entropy +
                0.25 * margin_inv +
                0.25 * conflict +
                0.15 * review_bonus
            )
            scores.append(score)

        return np.array(scores)

    def diversity_sampling(self, embeddings: np.ndarray,
                           selected_indices: List[int]) -> np.ndarray:
        """基于多样性的 K-Center 贪心采样"""
        from sklearn.metrics import pairwise_distances

        n_samples = len(embeddings)

        if not selected_indices:
            return np.ones(n_samples)

        # 计算每个样本到已选样本的最小距离
        selected_embeddings = embeddings[selected_indices]
        distances = pairwise_distances(embeddings, selected_embeddings)
        min_distances = distances.min(axis=1)

        return min_distances

    def schedule(self, fused_labels: List[Dict],
                 embeddings: np.ndarray,
                 already_labeled: Set[str]) -> List[int]:
        """
        混合策略：不确定性 + 多样性
        
        Returns:
            推荐标注的样本索引列表
        """
        # 构建映射
        clip_id_to_idx = {item['clip_id']: i for i, item in enumerate(fused_labels)}

        # 过滤已标注的
        unlabeled_indices = [
            i for i, item in enumerate(fused_labels)
            if item['clip_id'] not in already_labeled
        ]

        if not unlabeled_indices:
            logger.info("所有样本已标注！")
            return []

        if len(unlabeled_indices) <= self.batch_size:
            return unlabeled_indices

        # 计算不确定性分数
        all_uncertainty = self.uncertainty_sampling(fused_labels)
        uncertainty_scores = all_uncertainty[unlabeled_indices]

        # 归一化
        u_min, u_max = uncertainty_scores.min(), uncertainty_scores.max()
        if u_max > u_min:
            uncertainty_scores = (uncertainty_scores - u_min) / (u_max - u_min)
        else:
            uncertainty_scores = np.ones_like(uncertainty_scores) * 0.5

        # 贪心选择：平衡不确定性与多样性
        selected = []
        available = list(range(len(unlabeled_indices)))

        # 先选最不确定的一个
        first = available[np.argmax(uncertainty_scores)]
        selected.append(unlabeled_indices[first])
        available.remove(first)

        while len(selected) < self.batch_size and available:
            # 多样性分数
            try:
                unlabeled_embeddings = embeddings[unlabeled_indices]
                selected_in_unlabeled = [
                    unlabeled_indices.index(s) for s in selected
                    if s in unlabeled_indices
                ]
                diversity_scores = self.diversity_sampling(
                    unlabeled_embeddings, selected_in_unlabeled
                )
                diversity_scores = diversity_scores[available]

                # 归一化
                d_min, d_max = diversity_scores.min(), diversity_scores.max()
                if d_max > d_min:
                    diversity_scores = (diversity_scores - d_min) / (d_max - d_min)
                else:
                    diversity_scores = np.ones_like(diversity_scores) * 0.5
            except Exception:
                diversity_scores = np.ones(len(available)) * 0.5

            # 组合分数
            combined = (
                self.uncertainty_weight * uncertainty_scores[available] +
                (1 - self.uncertainty_weight) * diversity_scores
            )

            # 选得分最高
            best_local = available[np.argmax(combined)]
            best_global = unlabeled_indices[best_local]

            selected.append(best_global)
            available.remove(best_local)

        return selected

    def create_annotation_queue(self, fused_labels: List[Dict],
                                 selected_indices: List[int],
                                 cluster_info: Optional[Dict] = None) -> List[Dict]:
        """
        创建标注任务队列
        
        为每个选中样本附加上下文信息，便于标注
        """
        queue = []

        for idx in selected_indices:
            item = fused_labels[idx]

            task = {
                'clip_id': item['clip_id'],
                'suggested_label': item['suggested_label'],
                'confidence': item['confidence'],
                'margin': item['margin'],
                'conflict_score': item.get('conflict_score', 0),
                'needs_review': item.get('needs_review', False),
                'top3_labels': item.get('top3_labels', []),
                'source_probs': item.get('source_probs', {}),
                'priority': len(selected_indices) - len(queue),  # 优先级
            }

            # 附加聚类信息
            if cluster_info:
                cluster_id = cluster_info.get(item['clip_id'])
                if cluster_id is not None:
                    task['cluster_id'] = cluster_id

            queue.append(task)

        # 按优先级排序：不确定性高的排前面
        queue.sort(key=lambda x: x.get('conflict_score', 0), reverse=True)

        return queue


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    scheduler = ActiveLearningScheduler(config)

    # 加载融合标签
    fused_path = Path('data/fused_labels.json')
    if not fused_path.exists():
        logger.error("融合标签不存在！请先运行 step6_weak_labels.py")
        return

    with open(fused_path, encoding='utf-8') as f:
        fused_labels = json.load(f)

    # 加载嵌入
    embeddings_path = Path(config['paths']['features']) / 'embeddings.npy'
    if embeddings_path.exists():
        embeddings = np.load(str(embeddings_path))
    else:
        logger.warning("嵌入文件不存在，使用随机嵌入")
        embeddings = np.random.randn(len(fused_labels), 64)

    # 加载已标注列表
    labeled_path = Path('data/labeled_clips.txt')
    if labeled_path.exists():
        with open(labeled_path, encoding='utf-8') as f:
            already_labeled = set(f.read().splitlines())
    else:
        already_labeled = set()

    logger.info(f"总样本: {len(fused_labels)}, 已标注: {len(already_labeled)}")

    # 调度
    batch_indices = scheduler.schedule(fused_labels, embeddings, already_labeled)

    # 加载聚类信息
    cluster_info = None
    cluster_path = Path('data/cluster_assignments.json')
    if cluster_path.exists():
        with open(cluster_path, encoding='utf-8') as f:
            cluster_info = json.load(f)

    # 创建标注队列
    task_queue = scheduler.create_annotation_queue(
        fused_labels, batch_indices, cluster_info
    )

    # 保存
    output_path = 'data/annotation_queue.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(task_queue, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✅ 生成标注队列，共 {len(task_queue)} 个任务")

    if task_queue:
        avg_conf = np.mean([t['confidence'] for t in task_queue])
        high_conflict = sum(1 for t in task_queue if t.get('conflict_score', 0) > 0.5)
        review_count = sum(1 for t in task_queue if t.get('needs_review', False))

        logger.info(f"📊 队列统计:")
        logger.info(f"  平均置信度: {avg_conf:.3f}")
        logger.info(f"  高冲突样本: {high_conflict}")
        logger.info(f"  需复审样本: {review_count}")


if __name__ == "__main__":
    main()

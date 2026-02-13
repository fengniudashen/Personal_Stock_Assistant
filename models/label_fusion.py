"""
标签融合算法模块
独立的融合逻辑，供 step6 和其他模块调用
"""
import numpy as np
from typing import Dict, List
from collections import defaultdict


class SnorkelStyleFuser:
    """受 Snorkel 启发的标签融合算法
    
    支持:
    1. 加权投票 (Weighted Voting)
    2. 贝叶斯融合 (Bayesian Fusion)
    3. 基于质量的自适应权重 (Quality-Adaptive Weighting)
    """

    def __init__(self, labels: List[str],
                 source_weights: Dict[str, float] = None):
        self.labels = labels
        self.source_weights = source_weights or {
            'asr': 0.4,
            'heuristic': 0.2,
            'model': 0.3,
            'neighbor': 0.1
        }
        # 动态权重（根据历史校正率调整）
        self.source_accuracy = {k: 0.5 for k in self.source_weights}

    def weighted_vote(self, source_predictions: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        """加权投票融合"""
        fused = defaultdict(float)

        for source_name, probs in source_predictions.items():
            weight = self.source_weights.get(source_name, 0.1)

            for label, prob in probs.items():
                if label in self.labels:
                    fused[label] += weight * prob

        # 归一化
        total = sum(fused.values())
        if total > 0:
            return {k: v / total for k, v in fused.items()}
        return {label: 1.0 / len(self.labels) for label in self.labels}

    def bayesian_fusion(self, source_predictions: Dict[str, Dict[str, float]],
                        prior: Dict[str, float] = None) -> Dict[str, float]:
        """贝叶斯融合（考虑先验分布）"""
        # 默认先验：均匀分布
        if prior is None:
            prior = {label: 1.0 / len(self.labels) for label in self.labels}

        # 后验 ∝ 先验 × 似然
        posterior = {}
        for label in self.labels:
            log_prob = np.log(prior.get(label, 1e-10))

            for source_name, probs in source_predictions.items():
                accuracy = self.source_accuracy.get(source_name, 0.5)
                p = probs.get(label, 1e-10)
                # 根据源准确率加权似然
                weighted_p = accuracy * p + (1 - accuracy) * (1.0 / len(self.labels))
                log_prob += np.log(weighted_p + 1e-10)

            posterior[label] = np.exp(log_prob)

        # 归一化
        total = sum(posterior.values())
        if total > 0:
            return {k: v / total for k, v in posterior.items()}
        return prior

    def adaptive_fusion(self, source_predictions: Dict[str, Dict[str, float]],
                        clip_features: Dict = None) -> Dict[str, float]:
        """
        自适应权重融合
        根据各源对当前样本的置信度动态调整权重
        """
        # 计算每个源的置信度（熵的反比）
        source_confidences = {}
        for source_name, probs in source_predictions.items():
            if probs:
                values = np.array(list(probs.values()))
                entropy = -np.sum(values * np.log(values + 1e-10))
                max_entropy = np.log(len(values))
                confidence = 1 - (entropy / (max_entropy + 1e-10))
                source_confidences[source_name] = confidence
            else:
                source_confidences[source_name] = 0.0

        # 基础权重 × 置信度 = 自适应权重
        adaptive_weights = {}
        for source_name in source_predictions:
            base_weight = self.source_weights.get(source_name, 0.1)
            confidence = source_confidences.get(source_name, 0.5)
            adaptive_weights[source_name] = base_weight * (0.5 + confidence)

        # 归一化权重
        total_weight = sum(adaptive_weights.values())
        if total_weight > 0:
            adaptive_weights = {k: v / total_weight for k, v in adaptive_weights.items()}

        # 加权融合
        fused = defaultdict(float)
        for source_name, probs in source_predictions.items():
            weight = adaptive_weights.get(source_name, 0.1)
            for label, prob in probs.items():
                if label in self.labels:
                    fused[label] += weight * prob

        total = sum(fused.values())
        if total > 0:
            return {k: v / total for k, v in fused.items()}
        return {label: 1.0 / len(self.labels) for label in self.labels}

    def update_source_accuracy(self, source_name: str, was_correct: bool):
        """根据人工标注结果更新源准确率（EMA）"""
        alpha = 0.1  # 学习率
        current = self.source_accuracy.get(source_name, 0.5)
        self.source_accuracy[source_name] = (
            (1 - alpha) * current + alpha * (1.0 if was_correct else 0.0)
        )

    def get_consensus_label(self, source_predictions: Dict[str, Dict[str, float]]) -> Dict:
        """
        获取共识标签及详细信息
        
        Returns:
            {
                'label': str,
                'confidence': float,
                'method': str,
                'details': {...}
            }
        """
        # 尝试三种融合方法
        weighted = self.weighted_vote(source_predictions)
        bayesian = self.bayesian_fusion(source_predictions)
        adaptive = self.adaptive_fusion(source_predictions)

        # 投票：三种方法的Top-1
        top_weighted = max(weighted, key=weighted.get)
        top_bayesian = max(bayesian, key=bayesian.get)
        top_adaptive = max(adaptive, key=adaptive.get)

        # 如果三种方法一致，置信度更高
        if top_weighted == top_bayesian == top_adaptive:
            return {
                'label': top_weighted,
                'confidence': max(weighted[top_weighted], bayesian[top_bayesian], adaptive[top_adaptive]),
                'method': 'consensus',
                'agreement': 3,
                'details': {
                    'weighted': dict(weighted),
                    'bayesian': dict(bayesian),
                    'adaptive': dict(adaptive)
                }
            }
        else:
            # 使用自适应融合的结果（通常最优）
            top_label = top_adaptive
            return {
                'label': top_label,
                'confidence': adaptive[top_label],
                'method': 'adaptive',
                'agreement': sum(1 for t in [top_weighted, top_bayesian, top_adaptive] if t == top_label),
                'details': {
                    'weighted': dict(weighted),
                    'bayesian': dict(bayesian),
                    'adaptive': dict(adaptive)
                }
            }

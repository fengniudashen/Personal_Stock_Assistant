"""
Step 6: 多路弱监督融合
融合 ASR关键词、启发式规则、模型预测、近邻传播 四路标签
使用加权贝叶斯融合生成最终弱标签
"""
import numpy as np
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class HeuristicClassifier:
    """基于声学启发式规则的分类器"""

    def __init__(self, labels: List[str]):
        self.labels = labels

    def predict(self, features: Dict) -> Dict[str, float]:
        """
        基于声学特征规则推断标签概率
        
        规则来源于声乐教学理论:
        - H1-H2 高 → 气声(Breathy)
        - H1-H2 低 → 挤卡(Strained)
        - HNR 高 → 干净混声
        - Jitter/Shimmer 高 → 声音不稳定
        - 频谱倾斜陡 → 胸声倾向
        """
        probs = defaultdict(float)

        h1_h2 = features.get('h1_h2', 0)
        hnr = features.get('hnr', 0)
        jitter = features.get('jitter', 0)
        shimmer = features.get('shimmer', 0)
        spectral_tilt = features.get('spectral_tilt', 0)
        zcr = features.get('zcr', 0)
        rms = features.get('rms', 0)

        # 气声规则: H1-H2 大, HNR 低
        if h1_h2 > 5:
            probs['Breathy'] += 0.6
        elif h1_h2 > 2:
            probs['Breathy'] += 0.3

        # 挤卡规则: H1-H2 很负, Jitter/Shimmer高
        if h1_h2 < -3:
            probs['Strained'] += 0.4
        if jitter > 0.02 or shimmer > 0.1:
            probs['Strained'] += 0.3

        # 干净混声: HNR高, Jitter低
        if hnr > 15 and jitter < 0.01:
            probs['StrongMix'] += 0.4
        elif hnr > 10:
            probs['LightMix'] += 0.3

        # 假声: 高频谱质心, 低RMS
        if zcr > 0.1 and rms < 0.05:
            probs['Falsetto'] += 0.4

        # 胸声: 频谱倾斜陡, 低频能量大
        if spectral_tilt < -2:
            probs['Chest'] += 0.3

        # 头声: 频谱倾斜缓
        if spectral_tilt > -0.5:
            probs['Head'] += 0.3

        # 正常: 所有指标都在中间范围
        if abs(h1_h2) < 2 and 8 < hnr < 20 and jitter < 0.015:
            probs['Neutral'] += 0.3

        # 归一化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}

        return dict(probs)


class LabelFuser:
    """多路标签融合器"""

    def __init__(self, config: dict):
        self.config = config
        self.weights = {
            'asr': config['weak_supervision']['asr_weight'],
            'heuristic': config['weak_supervision']['heuristic_weight'],
            'model': config['weak_supervision']['model_weight'],
            'neighbor': config['weak_supervision']['neighbor_weight']
        }
        self.labels = config['labels']['primary']
        self.confidence_threshold = config['weak_supervision']['confidence_threshold']
        self.min_agreement = config['weak_supervision'].get('min_agreement', 2)

    def fuse_labels(self, clip_id: str,
                    asr_probs: Dict[str, float],
                    heuristic_probs: Dict[str, float],
                    model_probs: Dict[str, float],
                    neighbor_probs: Dict[str, float],
                    secondary_tags: Dict[str, float] = None,
                    quality_flags: List[str] = None) -> Dict:
        """贝叶斯融合多路标签"""

        def normalize(probs):
            if not probs:
                return {}
            total = sum(probs.values()) or 1.0
            return {k: v / total for k, v in probs.items()}

        asr_probs = normalize(asr_probs)
        heuristic_probs = normalize(heuristic_probs)
        model_probs = normalize(model_probs)
        neighbor_probs = normalize(neighbor_probs)

        # 计算来源数量（有多少路提供了有效信息）
        source_count = sum(1 for p in [asr_probs, heuristic_probs, model_probs, neighbor_probs] if p)

        # 加权融合
        fused = defaultdict(float)
        for label in self.labels:
            fused[label] = (
                self.weights['asr'] * asr_probs.get(label, 0) +
                self.weights['heuristic'] * heuristic_probs.get(label, 0) +
                self.weights['model'] * model_probs.get(label, 0) +
                self.weights['neighbor'] * neighbor_probs.get(label, 0)
            )

        # 归一化
        total = sum(fused.values())
        if total > 0:
            fused = {k: v / total for k, v in fused.items()}
        else:
            # 所有路都没有信息，默认Unknown
            fused = {label: 1.0 / len(self.labels) for label in self.labels}

        # 排序
        sorted_labels = sorted(fused.items(), key=lambda x: x[1], reverse=True)

        top_label, top_conf = sorted_labels[0]
        second_conf = sorted_labels[1][1] if len(sorted_labels) > 1 else 0

        # Margin
        margin = top_conf - second_conf

        # 冲突度
        conflict_score = self._calculate_conflict(asr_probs, heuristic_probs, model_probs)

        # 来源一致性
        agreement = self._calculate_agreement(
            asr_probs, heuristic_probs, model_probs, neighbor_probs
        )

        return {
            'clip_id': clip_id,
            'suggested_label': top_label,
            'confidence': float(top_conf),
            'margin': float(margin),
            'conflict_score': float(conflict_score),
            'source_count': source_count,
            'agreement': agreement,
            'needs_review': (top_conf < self.confidence_threshold or
                             conflict_score > 0.5 or
                             source_count < self.min_agreement),
            'secondary_tags': secondary_tags or {},
            'quality_flags': quality_flags or [],
            'top3_labels': [
                {'label': label, 'prob': float(prob)}
                for label, prob in sorted_labels[:3]
            ],
            'source_probs': {
                'asr': dict(asr_probs) if asr_probs else {},
                'heuristic': dict(heuristic_probs) if heuristic_probs else {},
                'model': dict(model_probs) if model_probs else {},
                'neighbor': dict(neighbor_probs) if neighbor_probs else {},
            }
        }

    def _calculate_conflict(self, *prob_dicts) -> float:
        """计算多路标签冲突程度"""
        valid_dicts = [d for d in prob_dicts if d]
        if len(valid_dicts) < 2:
            return 0.0

        try:
            from scipy.stats import entropy

            conflicts = []
            for i in range(len(valid_dicts)):
                for j in range(i + 1, len(valid_dicts)):
                    p = np.array([valid_dicts[i].get(l, 1e-10) for l in self.labels])
                    q = np.array([valid_dicts[j].get(l, 1e-10) for l in self.labels])

                    # 归一化
                    p = p / (p.sum() + 1e-10)
                    q = q / (q.sum() + 1e-10)

                    # 对称KL散度
                    kl = 0.5 * (entropy(p, q) + entropy(q, p))
                    conflicts.append(min(kl, 10.0))  # 限制最大值

            return float(np.mean(conflicts)) if conflicts else 0.0
        except ImportError:
            # scipy不可用，简单计算最大标签不一致
            top_labels = []
            for d in valid_dicts:
                if d:
                    top_labels.append(max(d, key=d.get))
            unique = len(set(top_labels))
            return (unique - 1) / max(len(top_labels) - 1, 1)

    def _calculate_agreement(self, *prob_dicts) -> Dict:
        """计算来源一致性"""
        top_labels = []
        for name, d in zip(['asr', 'heuristic', 'model', 'neighbor'], prob_dicts):
            if d:
                top_label = max(d, key=d.get)
                top_labels.append((name, top_label))

        if not top_labels:
            return {'count': 0, 'label': None}

        # 统计最多同意的标签
        from collections import Counter
        label_counter = Counter(label for _, label in top_labels)
        most_common = label_counter.most_common(1)[0]

        return {
            'count': most_common[1],
            'label': most_common[0],
            'sources': {name: label for name, label in top_labels}
        }


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 加载各路预测结果
    asr_preds = {}
    heuristic_scores = {}
    model_preds = {}
    neighbor_preds = {}

    # ASR预测
    asr_path = Path('data/asr_predictions.json')
    if asr_path.exists():
        with open(asr_path, encoding='utf-8') as f:
            asr_preds = json.load(f)
        logger.info(f"加载 ASR 预测: {len(asr_preds)} 条")

    # 启发式特征 → 启发式分类（主标签 + 辅标签）
    heuristic_path = Path('data/heuristic_scores.json')
    secondary_tags_map = {}  # clip_id -> {tag: prob}
    quality_flags_map = {}   # clip_id -> [flag, ...]
    if heuristic_path.exists():
        with open(heuristic_path, encoding='utf-8') as f:
            raw_scores = json.load(f)

        classifier = HeuristicClassifier(config['labels']['primary'])

        # 导入完整分类器用于辅标签和质量检测
        try:
            from models.heuristics import VocalHeuristicClassifier
            full_classifier = VocalHeuristicClassifier()
        except ImportError:
            full_classifier = None

        for clip_id, features in raw_scores.items():
            heuristic_scores[clip_id] = classifier.predict(features)
            if full_classifier:
                secondary_tags_map[clip_id] = full_classifier.detect_secondary(features)
                quality_flags_map[clip_id] = full_classifier.detect_quality_flags(features)
        logger.info(f"加载启发式分类: {len(heuristic_scores)} 条")

    # 模型预测（第一轮可能没有）
    model_path = Path('data/model_predictions.json')
    if model_path.exists():
        with open(model_path, encoding='utf-8') as f:
            model_preds = json.load(f)
        logger.info(f"加载模型预测: {len(model_preds)} 条")
    else:
        logger.info("模型预测不存在（第一轮正常）")

    # 近邻传播（第一轮可能没有）
    neighbor_path = Path('data/neighbor_propagation.json')
    if neighbor_path.exists():
        with open(neighbor_path, encoding='utf-8') as f:
            neighbor_preds = json.load(f)
        logger.info(f"加载近邻传播: {len(neighbor_preds)} 条")
    else:
        logger.info("近邻传播不存在（第一轮正常）")

    # 收集所有clip_id
    all_clip_ids = set()
    all_clip_ids.update(asr_preds.keys())
    all_clip_ids.update(heuristic_scores.keys())
    all_clip_ids.update(model_preds.keys())
    all_clip_ids.update(neighbor_preds.keys())

    if not all_clip_ids:
        logger.error("没有任何预测数据！请先运行 step4 和 step5。")
        return

    # 融合
    fuser = LabelFuser(config)
    fused_results = []

    for clip_id in all_clip_ids:
        result = fuser.fuse_labels(
            clip_id,
            asr_preds.get(clip_id, {}),
            heuristic_scores.get(clip_id, {}),
            model_preds.get(clip_id, {}),
            neighbor_preds.get(clip_id, {}),
            secondary_tags=secondary_tags_map.get(clip_id, {}),
            quality_flags=quality_flags_map.get(clip_id, [])
        )
        fused_results.append(result)

    # 保存
    output_path = 'data/fused_labels.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(fused_results, f, indent=2, ensure_ascii=False)

    # 统计
    logger.info(f"\n✅ 融合完成，共 {len(fused_results)} 条")

    label_counts = defaultdict(int)
    needs_review_count = 0
    high_confidence_count = 0

    for r in fused_results:
        label_counts[r['suggested_label']] += 1
        if r['needs_review']:
            needs_review_count += 1
        if r['confidence'] >= 0.7:
            high_confidence_count += 1

    logger.info(f"\n📊 标签分布:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {label}: {count}")

    logger.info(f"\n📈 质量统计:")
    logger.info(f"  高置信度(≥0.7): {high_confidence_count} ({high_confidence_count/len(fused_results)*100:.1f}%)")
    logger.info(f"  需人工复审: {needs_review_count} ({needs_review_count/len(fused_results)*100:.1f}%)")


if __name__ == "__main__":
    main()

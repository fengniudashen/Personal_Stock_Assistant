"""
启发式规则分类器
基于声乐理论的声学特征规则，用于弱监督标注
"""
import numpy as np
from typing import Dict, List
from collections import defaultdict


class VocalHeuristicClassifier:
    """基于声乐理论的启发式音色分类器
    
    利用声学参数的先验知识进行分类：
    - H1-H2 (第一谐波与第二谐波差): 衡量声门开合程度
      > 大值 → 声门开，气声(Breathy)
      > 小值/负值 → 声门紧，挤卡(Strained)
    - HNR (谐波噪声比): 声音清晰度
      > 高 → 干净混声
      > 低 → 气声/沙哑
    - Jitter/Shimmer: 音高/振幅微扰
      > 高 → 声音不稳定，发声技术问题
    - Spectral Tilt: 频谱衰减特征
      > 陡 → 低频为主（胸声）
      > 缓/平 → 高频成分多（头声/假声）
    """

    # 主标签（发声机制，互斥）
    PRIMARY_LABELS = [
        'StrongMix', 'LightMix', 'Falsetto', 'Chest',
        'Head', 'Breathy', 'Strained', 'Neutral', 'Invalid'
    ]

    # 辅标签（共鸣/色彩，可叠加）
    SECONDARY_TAGS = [
        'Pharyngeal', 'Twang', 'HighRange', 'SuperHighRange',
        'VowelMod', 'Vibrato', 'Glissando', 'Runs',
        'Demo_Correct', 'Demo_Error'
    ]

    # 质量旗标
    QUALITY_FLAGS = [
        'LowSNR', 'HighReverb', 'Clipping', 'Unstable',
        'MultiVoice', 'Distortion'
    ]

    # 向后兼容
    LABELS = PRIMARY_LABELS

    def __init__(self, sensitivity: float = 1.0):
        """
        Args:
            sensitivity: 规则灵敏度系数 (0.5-2.0)
        """
        self.sensitivity = sensitivity

    def classify(self, features: Dict) -> Dict[str, float]:
        """
        基于声学特征的规则推断
        
        Args:
            features: 声学特征字典
                - h1_h2: float, 第一与第二谐波差
                - hnr: float, 谐波噪声比
                - jitter: float, 音高微扰
                - shimmer: float, 振幅微扰
                - spectral_tilt: float, 频谱倾斜度
                - zcr: float, 过零率
                - rms: float, 均方根能量
                - f0_mean: float, 平均基频 (可选)
                - f0_range: float, 基频范围 (可选)
                
        Returns:
            {label: probability}
        """
        scores = defaultdict(float)
        s = self.sensitivity

        h1_h2 = features.get('h1_h2', 0)
        hnr = features.get('hnr', 0)
        jitter = features.get('jitter', 0)
        shimmer = features.get('shimmer', 0)
        tilt = features.get('spectral_tilt', 0)
        zcr = features.get('zcr', 0)
        rms = features.get('rms', 0)
        f0_mean = features.get('f0_mean', 0)
        f0_range = features.get('f0_range', 0)

        # ========== 规则1: 气声 (Breathy) ==========
        # 声门开大 → H1-H2高, HNR低, 气声多
        if h1_h2 > 5 * s:
            scores['Breathy'] += 0.7
        elif h1_h2 > 2 * s:
            scores['Breathy'] += 0.4
        if hnr < 5:
            scores['Breathy'] += 0.3

        # ========== 规则2: 挤卡 (Strained) ==========
        # 声门紧 → H1-H2负, 高Jitter/Shimmer
        if h1_h2 < -3 * s:
            scores['Strained'] += 0.5
        if jitter > 0.02 * s:
            scores['Strained'] += 0.3
        if shimmer > 0.1 * s:
            scores['Strained'] += 0.2
        # 高能量 + 高音区 → 更可能挤卡
        if rms > 0.1 and f0_mean > 400:
            scores['Strained'] += 0.2

        # ========== 规则3: 强混声 (StrongMix) ==========
        # 干净 + 有力 + HNR高
        if hnr > 15 and jitter < 0.01 and rms > 0.05:
            scores['StrongMix'] += 0.5
        if abs(h1_h2) < 3 and hnr > 12:
            scores['StrongMix'] += 0.3

        # ========== 规则4: 弱混声 (LightMix) ==========
        if hnr > 10 and rms < 0.05:
            scores['LightMix'] += 0.4
        if abs(h1_h2) < 2 and jitter < 0.015:
            scores['LightMix'] += 0.3

        # ========== 规则5: 假声 (Falsetto) ==========
        # 高频占主导, 低能量, 高过零率
        if zcr > 0.1 and rms < 0.04:
            scores['Falsetto'] += 0.5
        if tilt > -0.5:
            scores['Falsetto'] += 0.3
        if f0_mean > 500:
            scores['Falsetto'] += 0.2

        # ========== 规则6: 胸声 (Chest) ==========
        if tilt < -2 * s:
            scores['Chest'] += 0.4
        if f0_mean > 0 and f0_mean < 300:
            scores['Chest'] += 0.3
        if rms > 0.06:
            scores['Chest'] += 0.2

        # ========== 规则7: 头声 (Head) ==========
        if tilt > -1:
            scores['Head'] += 0.3
        if f0_mean > 350:
            scores['Head'] += 0.3

        # ========== 规则8: 正常/标准 ==========
        if abs(h1_h2) < 2 and 8 < hnr < 20 and jitter < 0.015 and shimmer < 0.08:
            scores['Neutral'] += 0.4

        # ========== 规则11: 无效 ==========
        if rms < 0.005:
            scores['Invalid'] += 0.8
        if hnr < 0:
            scores['Invalid'] += 0.3

        # 归一化为概率
        total = sum(scores.values())
        if total > 0:
            probs = {k: v / total for k, v in scores.items()}
        else:
            probs = {'Neutral': 1.0}

        return dict(probs)

    def detect_secondary(self, features: Dict) -> Dict[str, float]:
        """
        检测辅标签（共鸣/色彩技术）
        辅标签与主标签正交，可叠加
        
        Returns:
            {tag: probability} — 仅包含 prob > 0 的辅标签
        """
        tags = {}
        s = self.sensitivity

        h1_h2 = features.get('h1_h2', 0)
        hnr = features.get('hnr', 0)
        tilt = features.get('spectral_tilt', 0)
        f0_mean = features.get('f0_mean', 0)
        f0_std = features.get('f0_std', 0)
        jitter = features.get('jitter', 0)

        # 咽音 Pharyngeal: 明亮穿透、持续稳定、3-5kHz增强
        if h1_h2 < -5 * s and hnr > 10 and jitter < 0.015:
            tags['Pharyngeal'] = 0.7
        elif h1_h2 < -3 * s and hnr > 8:
            tags['Pharyngeal'] = 0.4

        # Twang: 鼻咽收窄、2-4kHz增强
        if tilt > -0.3 and hnr > 8:
            tags['Twang'] = 0.5

        # 高音区 HighRange: C5(523Hz)+
        if f0_mean >= 523:
            tags['HighRange'] = min(1.0, (f0_mean - 400) / 300)

        # 超高音区 SuperHighRange: C6(1047Hz)+
        if f0_mean >= 1047:
            tags['SuperHighRange'] = min(1.0, (f0_mean - 900) / 300)

        # 颤音 Vibrato: f0标准差在合理范围内的周期性波动
        if f0_std and 15 < f0_std < 80:
            tags['Vibrato'] = 0.6

        return tags

    def detect_quality_flags(self, features: Dict) -> List[str]:
        """
        检测音频质量问题
        
        Returns:
            质量旗标列表
        """
        flags = []
        rms = features.get('rms', 0)
        hnr = features.get('hnr', 0)
        jitter = features.get('jitter', 0)
        shimmer = features.get('shimmer', 0)
        clipping_ratio = features.get('clipping_ratio', 0)

        if hnr < 5:
            flags.append('LowSNR')
        if clipping_ratio > 0.01:
            flags.append('Clipping')
        if jitter > 0.04 and shimmer > 0.15:
            flags.append('Unstable')

        return flags

    def full_classify(self, features: Dict) -> Dict:
        """
        完整分类：主标签 + 辅标签 + 质量旗标
        
        Returns:
            {
                'primary_probs': {label: prob},
                'secondary_tags': {tag: prob},
                'quality_flags': [flag, ...]
            }
        """
        return {
            'primary_probs': self.classify(features),
            'secondary_tags': self.detect_secondary(features),
            'quality_flags': self.detect_quality_flags(features)
        }

    def batch_classify(self, features_list: List[Dict]) -> List[Dict]:
        """批量分类（主标签）"""
        return [self.classify(f) for f in features_list]

    def batch_full_classify(self, features_list: List[Dict]) -> List[Dict]:
        """批量完整分类"""
        return [self.full_classify(f) for f in features_list]

    def explain(self, features: Dict) -> str:
        """生成分类解释（人类可读）"""
        probs = self.classify(features)
        sorted_labels = sorted(probs.items(), key=lambda x: -x[1])

        h1_h2 = features.get('h1_h2', 0)
        hnr = features.get('hnr', 0)

        lines = [f"预测: {sorted_labels[0][0]} ({sorted_labels[0][1]:.1%})"]

        if h1_h2 > 5:
            lines.append("原因: H1-H2偏高，声门开合不完全 → 可能漏气")
        elif h1_h2 < -3:
            lines.append("原因: H1-H2偏低，声门过紧 → 可能挤卡")

        if hnr > 15:
            lines.append("HNR高，声音干净")
        elif hnr < 5:
            lines.append("HNR低，声音含噪声/气声")

        return "\n".join(lines)

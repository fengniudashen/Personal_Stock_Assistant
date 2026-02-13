"""
VibeSing 多任务模型
三头架构: 主标签 (softmax) + 辅标签 (sigmoid) + 质量旗标 (sigmoid)
"""
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# 标签定义
PRIMARY_LABELS = [
    'StrongMix', 'LightMix', 'Falsetto', 'Chest',
    'Head', 'Breathy', 'Strained', 'Neutral', 'Invalid'
]

SECONDARY_TAGS = [
    'Pharyngeal', 'Twang', 'HighRange', 'SuperHighRange',
    'VowelMod', 'Vibrato', 'Glissando', 'Runs',
    'Demo_Correct', 'Demo_Error'
]

QUALITY_FLAGS = [
    'LowSNR', 'HighReverb', 'Clipping', 'Unstable',
    'MultiVoice', 'Distortion'
]

NUM_PRIMARY = len(PRIMARY_LABELS)    # 9
NUM_SECONDARY = len(SECONDARY_TAGS)  # 10
NUM_QUALITY = len(QUALITY_FLAGS)     # 6

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch 未安装，模型仅支持占位符模式")


if HAS_TORCH:
    class ConvBlock(nn.Module):
        """卷积块: Conv2d → BN → ReLU → MaxPool"""
        def __init__(self, in_ch, out_ch, pool_size=(2, 2)):
            super().__init__()
            self.conv = nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1)
            self.bn = nn.BatchNorm2d(out_ch)
            self.pool = nn.MaxPool2d(pool_size)

        def forward(self, x):
            return self.pool(F.relu(self.bn(self.conv(x))))


    class VibeSingEncoder(nn.Module):
        """共享 CNN 特征编码器
        
        输入: (batch, 1, n_mels, time_frames) Mel频谱图
        输出: (batch, feature_dim) 特征向量
        """
        def __init__(self, n_mels: int = 128, feature_dim: int = 256):
            super().__init__()
            self.feature_dim = feature_dim

            self.conv_layers = nn.Sequential(
                ConvBlock(1, 32),       # (B,32, H/2, T/2)
                ConvBlock(32, 64),      # (B,64, H/4, T/4)
                ConvBlock(64, 128),     # (B,128, H/8, T/8)
                ConvBlock(128, 256),    # (B,256, H/16, T/16)
            )

            # 自适应池化 → 固定尺寸
            self.pool = nn.AdaptiveAvgPool2d((4, 4))
            self.flatten = nn.Flatten()
            self.fc = nn.Sequential(
                nn.Linear(256 * 4 * 4, 512),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(512, feature_dim),
                nn.ReLU(),
                nn.Dropout(0.2),
            )

        def forward(self, x):
            # x: (B, 1, n_mels, T)
            x = self.conv_layers(x)
            x = self.pool(x)
            x = self.flatten(x)
            x = self.fc(x)
            return x  # (B, feature_dim)


    class VibeSingMultiTaskModel(nn.Module):
        """多任务音色分类模型
        
        架构:
            共享编码器 → 三个分类头:
            1. 主标签头 (softmax, 9类) — 权重 0.7
            2. 辅标签头 (sigmoid, 10标签) — 权重 0.2
            3. 质量旗标头 (sigmoid, 6标签) — 权重 0.1
        """

        def __init__(self, n_mels: int = 128, feature_dim: int = 256,
                     primary_class_weights: Optional[Dict[str, float]] = None):
            super().__init__()
            self.encoder = VibeSingEncoder(n_mels=n_mels, feature_dim=feature_dim)

            # 主标签头 (互斥 → softmax)
            self.primary_head = nn.Sequential(
                nn.Linear(feature_dim, 128),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(128, NUM_PRIMARY)
            )

            # 辅标签头 (多标签 → sigmoid)
            self.secondary_head = nn.Sequential(
                nn.Linear(feature_dim, 64),
                nn.ReLU(),
                nn.Dropout(0.2),
                nn.Linear(64, NUM_SECONDARY)
            )

            # 质量旗标头 (多标签 → sigmoid)
            self.quality_head = nn.Sequential(
                nn.Linear(feature_dim, 32),
                nn.ReLU(),
                nn.Linear(32, NUM_QUALITY)
            )

            # 损失函数
            if primary_class_weights:
                weights = torch.tensor([primary_class_weights.get(l, 1.0) for l in PRIMARY_LABELS])
                self.primary_criterion = nn.CrossEntropyLoss(weight=weights)
            else:
                self.primary_criterion = nn.CrossEntropyLoss()

            self.secondary_criterion = nn.BCEWithLogitsLoss()
            self.quality_criterion = nn.BCEWithLogitsLoss()

        def forward(self, x) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            """
            Args:
                x: (B, 1, n_mels, T)
            Returns:
                primary_logits: (B, 9) — 主标签 logits
                secondary_logits: (B, 10) — 辅标签 logits
                quality_logits: (B, 6) — 质量 logits
            """
            features = self.encoder(x)
            primary_logits = self.primary_head(features)
            secondary_logits = self.secondary_head(features)
            quality_logits = self.quality_head(features)
            return primary_logits, secondary_logits, quality_logits

        def compute_loss(self, x, primary_targets, secondary_targets, quality_targets,
                         loss_weights=(0.7, 0.2, 0.1)):
            """
            计算多任务损失
            
            Args:
                x: 输入 Mel 频谱
                primary_targets: (B,) LongTensor 主标签索引
                secondary_targets: (B, 10) FloatTensor 辅标签二值
                quality_targets: (B, 6) FloatTensor 质量旗标二值
                loss_weights: (primary_w, secondary_w, quality_w)
            
            Returns:
                total_loss, {loss_name: value}
            """
            p_logits, s_logits, q_logits = self.forward(x)

            loss_p = self.primary_criterion(p_logits, primary_targets)
            loss_s = self.secondary_criterion(s_logits, secondary_targets)
            loss_q = self.quality_criterion(q_logits, quality_targets)

            total = loss_weights[0] * loss_p + loss_weights[1] * loss_s + loss_weights[2] * loss_q

            return total, {
                'primary_loss': loss_p.item(),
                'secondary_loss': loss_s.item(),
                'quality_loss': loss_q.item(),
                'total_loss': total.item()
            }

        def predict(self, x) -> Dict:
            """
            推理：返回标签概率
            
            Args:
                x: (1, 1, n_mels, T) 或 (n_mels, T) Mel频谱
            
            Returns:
                {
                    'primary': {label: prob},
                    'primary_label': str,
                    'secondary': {tag: prob},
                    'quality': {flag: prob}
                }
            """
            self.eval()
            with torch.no_grad():
                if x.ndim == 2:
                    x = x.unsqueeze(0).unsqueeze(0)
                elif x.ndim == 3:
                    x = x.unsqueeze(0)

                p_logits, s_logits, q_logits = self.forward(x)

                p_probs = F.softmax(p_logits, dim=-1)[0].cpu().numpy()
                s_probs = torch.sigmoid(s_logits)[0].cpu().numpy()
                q_probs = torch.sigmoid(q_logits)[0].cpu().numpy()

            primary_dict = {PRIMARY_LABELS[i]: float(p_probs[i]) for i in range(NUM_PRIMARY)}
            primary_label = PRIMARY_LABELS[int(np.argmax(p_probs))]

            secondary_dict = {SECONDARY_TAGS[i]: float(s_probs[i]) for i in range(NUM_SECONDARY)}
            quality_dict = {QUALITY_FLAGS[i]: float(q_probs[i]) for i in range(NUM_QUALITY)}

            return {
                'primary': primary_dict,
                'primary_label': primary_label,
                'primary_confidence': float(p_probs.max()),
                'secondary': secondary_dict,
                'secondary_tags': [t for t, p in secondary_dict.items() if p > 0.5],
                'quality': quality_dict,
                'quality_flags': [f for f, p in quality_dict.items() if p > 0.5],
            }

    def train_epoch(model: VibeSingMultiTaskModel, dataloader, optimizer,
                    device='cpu', loss_weights=(0.7, 0.2, 0.1)):
        """
        训练一个 epoch
        
        Args:
            model: 多任务模型
            dataloader: 提供 (mel, primary_target, secondary_target, quality_target) 的数据加载器
            optimizer: 优化器
            device: 'cpu' 或 'cuda'
            loss_weights: 三头损失权重
        
        Returns:
            epoch 平均损失字典
        """
        model.train()
        model.to(device)

        epoch_losses = {'primary_loss': 0, 'secondary_loss': 0, 'quality_loss': 0, 'total_loss': 0}
        n_batches = 0

        for batch in dataloader:
            mel, p_target, s_target, q_target = [b.to(device) for b in batch]

            optimizer.zero_grad()
            total_loss, losses = model.compute_loss(mel, p_target, s_target, q_target, loss_weights)
            total_loss.backward()
            optimizer.step()

            for k, v in losses.items():
                epoch_losses[k] += v
            n_batches += 1

        if n_batches > 0:
            epoch_losses = {k: v / n_batches for k, v in epoch_losses.items()}

        return epoch_losses

    def evaluate(model: VibeSingMultiTaskModel, dataloader, device='cpu'):
        """
        评估模型
        
        Returns:
            {
                'primary_accuracy': float,
                'secondary_f1': float,
                'quality_f1': float,
                'avg_loss': float
            }
        """
        model.eval()
        model.to(device)

        correct = 0
        total = 0
        all_s_preds = []
        all_s_targets = []
        all_q_preds = []
        all_q_targets = []
        total_loss = 0
        n_batches = 0

        with torch.no_grad():
            for batch in dataloader:
                mel, p_target, s_target, q_target = [b.to(device) for b in batch]

                loss, _ = model.compute_loss(mel, p_target, s_target, q_target)
                total_loss += loss.item()
                n_batches += 1

                p_logits, s_logits, q_logits = model(mel)

                # 主标签准确率
                preds = p_logits.argmax(dim=-1)
                correct += (preds == p_target).sum().item()
                total += p_target.size(0)

                # 辅标签
                s_pred = (torch.sigmoid(s_logits) > 0.5).cpu().numpy()
                all_s_preds.append(s_pred)
                all_s_targets.append(s_target.cpu().numpy())

                # 质量旗标
                q_pred = (torch.sigmoid(q_logits) > 0.5).cpu().numpy()
                all_q_preds.append(q_pred)
                all_q_targets.append(q_target.cpu().numpy())

        primary_acc = correct / total if total > 0 else 0

        # 计算F1
        def multilabel_f1(preds_list, targets_list):
            preds = np.concatenate(preds_list, axis=0)
            targets = np.concatenate(targets_list, axis=0)
            try:
                from sklearn.metrics import f1_score
                return float(f1_score(targets, preds, average='macro', zero_division=0))
            except ImportError:
                # 简易计算
                tp = ((preds == 1) & (targets == 1)).sum()
                fp = ((preds == 1) & (targets == 0)).sum()
                fn = ((preds == 0) & (targets == 1)).sum()
                precision = tp / (tp + fp + 1e-10)
                recall = tp / (tp + fn + 1e-10)
                return float(2 * precision * recall / (precision + recall + 1e-10))

        secondary_f1 = multilabel_f1(all_s_preds, all_s_targets) if all_s_preds else 0
        quality_f1 = multilabel_f1(all_q_preds, all_q_targets) if all_q_preds else 0

        return {
            'primary_accuracy': primary_acc,
            'secondary_f1': secondary_f1,
            'quality_f1': quality_f1,
            'avg_loss': total_loss / max(n_batches, 1)
        }

else:
    # 无 PyTorch 时的占位符
    class VibeSingMultiTaskModel:
        """占位符 — PyTorch 未安装"""
        def __init__(self, **kwargs):
            logger.warning("VibeSingMultiTaskModel: PyTorch 未安装，使用占位符")

        def predict(self, mel) -> Dict:
            n = NUM_PRIMARY
            return {
                'primary': {l: 1.0 / n for l in PRIMARY_LABELS},
                'primary_label': 'Neutral',
                'primary_confidence': 1.0 / n,
                'secondary': {t: 0.0 for t in SECONDARY_TAGS},
                'secondary_tags': [],
                'quality': {f: 0.0 for f in QUALITY_FLAGS},
                'quality_flags': [],
            }

    def train_epoch(*args, **kwargs):
        raise RuntimeError("PyTorch 未安装")

    def evaluate(*args, **kwargs):
        raise RuntimeError("PyTorch 未安装")

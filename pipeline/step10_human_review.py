"""
Step 10: 人工审核
管理音频切片的人工审核状态，确保训练数据质量。
所有切片在进入最终训练集前必须经过人工确认（通过/拒绝）。

审核数据流:
  fused_labels.json  ──>  人工审核  ──>  review_results.json
                                              |
                                              v
                                     仅 approved 切片  ──>  导出训练集

用法:
  manager = HumanReviewManager(CONFIG)
  clips = manager.load_clips_for_review()
  manager.submit_review(clip_id, 'approved', primary_label='StrongMix', ...)
  approved = manager.get_approved_clips()
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 审核状态常量
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"

DEFAULT_REVIEW_FILE = 'data/review_results.json'
DEFAULT_FUSED_FILE = 'data/fused_labels.json'


class HumanReviewManager:
    """
    人工审核管理器
    
    负责:
    - 加载待审核切片（从 fused_labels.json）
    - 维护审核状态（review_results.json）
    - 提交审核结果（通过/拒绝 + 标签修正）
    - 导出仅审核通过的切片
    - 批量操作（高置信度自动通过等）
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        paths_cfg = self.config.get('paths', {})
        review_cfg = self.config.get('human_review', {})

        self.review_path = Path(review_cfg.get('review_file', DEFAULT_REVIEW_FILE))
        self.fused_path = Path(review_cfg.get('fused_file', DEFAULT_FUSED_FILE))
        self.clips_dir = Path(paths_cfg.get('clips', 'data/clips'))

        # 批量通过阈值
        self.auto_approve_threshold = review_cfg.get('auto_approve_confidence', 0.92)

        # 审核数据: { clip_id: { review_status, final_primary_label, ... } }
        self.reviews: Dict[str, dict] = {}
        self._load_reviews()

    def _load_reviews(self):
        """从磁盘加载审核结果"""
        if self.review_path.exists():
            try:
                with open(self.review_path, 'r', encoding='utf-8') as f:
                    self.reviews = json.load(f)
                logger.info(f"已加载 {len(self.reviews)} 条审核记录")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"审核文件加载失败: {e}")
                self.reviews = {}
        else:
            self.reviews = {}

    def _save_reviews(self):
        """持久化审核结果"""
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.review_path, 'w', encoding='utf-8') as f:
            json.dump(self.reviews, f, indent=2, ensure_ascii=False)

    def load_fused_labels(self) -> List[dict]:
        """加载原始融合标签数据"""
        if not self.fused_path.exists():
            logger.warning(f"融合标签文件不存在: {self.fused_path}")
            return []

        with open(self.fused_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_clips_for_review(
        self,
        status_filter: Optional[str] = None,
        label_filter: Optional[str] = None,
        min_conf: float = 0.0,
        max_conf: float = 1.0,
        needs_review_only: bool = False,
    ) -> List[dict]:
        """
        加载切片列表，附带审核状态信息
        
        Args:
            status_filter: 仅返回指定状态 (pending/approved/rejected)
            label_filter: 仅返回指定主标签
            min_conf: 最低置信度
            max_conf: 最高置信度
            needs_review_only: 仅返回需要人工复审的
            
        Returns:
            带有审核信息的切片列表
        """
        fused = self.load_fused_labels()
        if not fused:
            return []

        results = []
        for item in fused:
            clip_id = item['clip_id']
            review = self.reviews.get(clip_id, {})

            # 合并审核状态
            item['review_status'] = review.get('review_status', PENDING)
            item['final_primary_label'] = review.get(
                'final_primary_label', item.get('suggested_label', 'Unknown')
            )

            # secondary_tags 在 fused 中是 dict {tag: prob}，转为 list
            auto_secondary = list(item.get('secondary_tags', {}).keys()) if isinstance(
                item.get('secondary_tags'), dict
            ) else item.get('secondary_tags', [])
            item['final_secondary_tags'] = review.get('final_secondary_tags', auto_secondary)

            item['final_quality_flags'] = review.get(
                'final_quality_flags', item.get('quality_flags', [])
            )
            item['reviewer_notes'] = review.get('reviewer_notes', '')
            item['reviewed_at'] = review.get('reviewed_at', '')

            # 推断文件路径
            if 'file_path' not in item:
                wav_path = self.clips_dir / f"{clip_id}.wav"
                item['file_path'] = str(wav_path) if wav_path.exists() else ''

            # 过滤
            if status_filter and item['review_status'] != status_filter:
                continue
            if label_filter and item.get('suggested_label') != label_filter:
                continue
            conf = item.get('confidence', 0)
            if conf < min_conf or conf > max_conf:
                continue
            if needs_review_only and not item.get('needs_review', False):
                continue

            results.append(item)

        return results

    def submit_review(
        self,
        clip_id: str,
        status: str,
        primary_label: Optional[str] = None,
        secondary_tags: Optional[List[str]] = None,
        quality_flags: Optional[List[str]] = None,
        notes: str = '',
    ):
        """
        提交单条审核结果
        
        Args:
            clip_id: 切片ID
            status: 审核状态 (approved/rejected)
            primary_label: 最终主标签（可修正自动标签）
            secondary_tags: 最终辅标签列表
            quality_flags: 最终质量旗标列表
            notes: 审核备注
        """
        self.reviews[clip_id] = {
            'review_status': status,
            'final_primary_label': primary_label,
            'final_secondary_tags': secondary_tags or [],
            'final_quality_flags': quality_flags or [],
            'reviewer_notes': notes,
            'reviewed_at': datetime.now().isoformat(),
        }
        self._save_reviews()
        logger.info(f"审核提交: {clip_id} → {status} ({primary_label})")

    def reset_review(self, clip_id: str):
        """重置某条审核结果为待审核"""
        if clip_id in self.reviews:
            del self.reviews[clip_id]
            self._save_reviews()
            logger.info(f"审核重置: {clip_id}")

    def get_stats(self) -> dict:
        """获取审核进度统计"""
        fused = self.load_fused_labels()
        total = len(fused)

        if total == 0:
            return {'total': 0, 'pending': 0, 'approved': 0, 'rejected': 0, 'progress_pct': 0}

        approved = sum(1 for r in self.reviews.values()
                       if r.get('review_status') == APPROVED)
        rejected = sum(1 for r in self.reviews.values()
                       if r.get('review_status') == REJECTED)
        pending = total - approved - rejected

        return {
            'total': total,
            'pending': max(0, pending),
            'approved': approved,
            'rejected': rejected,
            'progress_pct': round((approved + rejected) / total * 100, 1) if total > 0 else 0,
        }

    def get_label_distribution(self) -> dict:
        """获取审核通过切片的最终标签分布"""
        approved = [r for r in self.reviews.values()
                    if r.get('review_status') == APPROVED]
        return dict(Counter(r.get('final_primary_label', 'Unknown') for r in approved))

    def get_approved_clips(self) -> List[dict]:
        """
        获取所有审核通过的切片，用于导出训练集
        
        Returns:
            包含最终标签信息的切片列表
        """
        fused = self.load_fused_labels()
        fused_lookup = {item['clip_id']: item for item in fused}

        result = []
        for clip_id, review in self.reviews.items():
            if review.get('review_status') != APPROVED:
                continue

            fused_item = fused_lookup.get(clip_id, {})

            # 推断文件路径
            file_path = fused_item.get('file_path', '')
            if not file_path:
                wav = self.clips_dir / f"{clip_id}.wav"
                file_path = str(wav) if wav.exists() else f"data/clips/{clip_id}.wav"

            result.append({
                'clip_id': clip_id,
                'file_path': file_path,
                'primary_label': review.get('final_primary_label'),
                'secondary_tags': review.get('final_secondary_tags', []),
                'quality_flags': review.get('final_quality_flags', []),
                'confidence': fused_item.get('confidence', 0),
                'reviewer_notes': review.get('reviewer_notes', ''),
                'reviewed_at': review.get('reviewed_at', ''),
                'duration': fused_item.get('duration'),
                'pitch_mean': fused_item.get('pitch_mean'),
            })

        return result

    def batch_approve_high_confidence(self, min_confidence: float = None) -> int:
        """
        批量通过高置信度、无冲突的切片
        
        Args:
            min_confidence: 最低置信度阈值（默认使用配置值 0.92）
            
        Returns:
            通过的数量
        """
        threshold = min_confidence or self.auto_approve_threshold
        pending = self.load_clips_for_review(status_filter=PENDING)

        count = 0
        for clip in pending:
            conf = clip.get('confidence', 0)
            has_conflict = clip.get('needs_review', False)

            if conf >= threshold and not has_conflict:
                auto_secondary = list(clip.get('secondary_tags', {}).keys()) if isinstance(
                    clip.get('secondary_tags'), dict
                ) else clip.get('secondary_tags', [])

                self.reviews[clip['clip_id']] = {
                    'review_status': APPROVED,
                    'final_primary_label': clip.get('suggested_label'),
                    'final_secondary_tags': auto_secondary,
                    'final_quality_flags': clip.get('quality_flags', []),
                    'reviewer_notes': f'[自动通过] conf={conf:.3f} ≥ {threshold}',
                    'reviewed_at': datetime.now().isoformat(),
                }
                count += 1

        if count > 0:
            self._save_reviews()
            logger.info(f"批量自动通过: {count} 条 (阈值 ≥ {threshold})")

        return count

    def batch_reject_invalid(self) -> int:
        """批量拒绝 Invalid/低质量切片"""
        pending = self.load_clips_for_review(status_filter=PENDING)
        count = 0
        for clip in pending:
            label = clip.get('suggested_label', '')
            flags = clip.get('quality_flags', [])

            # 自动拒绝 Invalid 或有多项严重质量问题的
            should_reject = (
                label == 'Invalid' or
                (len(flags) >= 3) or
                ('MultiVoice' in flags and 'Clipping' in flags)
            )

            if should_reject:
                self.reviews[clip['clip_id']] = {
                    'review_status': REJECTED,
                    'final_primary_label': label,
                    'final_secondary_tags': [],
                    'final_quality_flags': flags,
                    'reviewer_notes': f'[自动拒绝] label={label}, flags={flags}',
                    'reviewed_at': datetime.now().isoformat(),
                }
                count += 1

        if count > 0:
            self._save_reviews()
            logger.info(f"批量自动拒绝: {count} 条")

        return count


def main():
    """命令行入口: 显示审核统计并运行批量操作"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    import yaml
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    manager = HumanReviewManager(config)
    stats = manager.get_stats()

    print("\n" + "=" * 50)
    print("  🔍 VibeSing 人工审核 - 状态报告")
    print("=" * 50)
    print(f"  总切片数:   {stats['total']}")
    print(f"  ⏳ 待审核:  {stats['pending']}")
    print(f"  ✅ 已通过:  {stats['approved']}")
    print(f"  ❌ 已拒绝:  {stats['rejected']}")
    print(f"  进度:       {stats['progress_pct']:.1f}%")
    print("=" * 50)

    if stats['approved'] > 0:
        dist = manager.get_label_distribution()
        print("\n📊 已通过切片标签分布:")
        for label, count in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"  {label}: {count}")

    # 命令行参数: --auto-approve / --auto-reject
    if '--auto-approve' in sys.argv:
        count = manager.batch_approve_high_confidence()
        print(f"\n✅ 批量自动通过: {count} 条")

    if '--auto-reject' in sys.argv:
        count = manager.batch_reject_invalid()
        print(f"\n❌ 批量自动拒绝: {count} 条")


if __name__ == "__main__":
    main()

"""
导出标注数据集
将已标注数据导出为训练所需格式
"""
import sys
import json
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def export_dataset(
    output_dir: str = 'data/export',
    format: str = 'json',
    min_confidence: float = 0.6,
    only_verified: bool = False,
    only_approved: bool = False
):
    """
    导出已标注数据
    
    Args:
        output_dir: 输出目录
        format: 导出格式 (json, csv, manifest)
        min_confidence: 最低置信度过滤
        only_verified: 仅导出人工验证的
        only_approved: 仅导出人工审核通过的切片 (推荐)
    """
    from database.models import SessionLocal, AudioClip

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 优先模式: 仅导出人工审核通过的切片
    # ------------------------------------------------------------------
    if only_approved:
        try:
            from pipeline.step10_human_review import HumanReviewManager
            import yaml
            cfg_path = ROOT / 'config_advanced.yaml'
            with open(cfg_path, encoding='utf-8') as f:
                config = yaml.safe_load(f)
            manager = HumanReviewManager(config)
            exported = manager.get_approved_clips()
            logger.info(f"审核通过切片: {len(exported)} 条")
        except Exception as e:
            logger.error(f"加载审核结果失败: {e}，回退到数据库查询")
            only_approved = False

    if not only_approved:
        session = SessionLocal()
        try:
            query = session.query(AudioClip)

            if only_verified:
                query = query.filter(AudioClip.human_label.isnot(None))

            clips = query.all()
            logger.info(f"查询到 {len(clips)} 条记录")

            exported = []
            for clip in clips:
                label = clip.human_label or clip.weak_label
                confidence = clip.label_confidence or 0.0

                if not label or confidence < min_confidence:
                    continue

                record = {
                    'clip_id': clip.clip_id,
                    'file_path': clip.file_path,
                    'primary_label': label,
                    'secondary_tags': clip.secondary_labels or [],
                    'quality_flags': clip.quality_flags or [],
                    'confidence': round(confidence, 4),
                    'is_human_verified': clip.human_label is not None,
                    'pitch_mean': clip.pitch_mean,
                    'pitch_std': clip.pitch_std,
                    'hnr_mean': clip.hnr_mean,
                    'duration': clip.duration,
                    'source_platform': clip.source_platform,
                }
                exported.append(record)

            logger.info(f"过滤后: {len(exported)} 条 (min_conf={min_confidence})")
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 公共输出逻辑 (两种模式共用)
    # ------------------------------------------------------------------
    if not exported:
        logger.warning("没有可导出的数据")
        return None

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = '_approved' if only_approved else ''

    if format == 'json':
        out_file = output_dir / f'dataset{suffix}_{timestamp}.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(exported, f, indent=2, ensure_ascii=False)

    elif format == 'csv':
        out_file = output_dir / f'dataset{suffix}_{timestamp}.csv'
        if exported:
            with open(out_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=exported[0].keys())
                writer.writeheader()
                writer.writerows(exported)

    elif format == 'manifest':
        out_file = output_dir / f'dataset{suffix}_{timestamp}.manifest'
        with open(out_file, 'w', encoding='utf-8') as f:
            for rec in exported:
                manifest_entry = {
                    'audio_filepath': rec.get('file_path', ''),
                    'label': rec.get('primary_label', ''),
                    'secondary_tags': rec.get('secondary_tags', []),
                    'quality_flags': rec.get('quality_flags', []),
                    'duration': rec.get('duration') or 0,
                }
                f.write(json.dumps(manifest_entry, ensure_ascii=False) + '\n')
    else:
        logger.error(f"不支持的格式: {format}")
        return None

    logger.info(f"已导出: {out_file} ({len(exported)} 条)")

    # 标签分布统计
    from collections import Counter
    label_key = 'primary_label'
    label_dist = Counter(r.get(label_key, 'Unknown') for r in exported)
    logger.info("标签分布:")
    for label, count in label_dist.most_common():
        logger.info(f"  {label}: {count}")

    return str(out_file)


def export_approved_only(
    output_dir: str = 'data/export',
    format: str = 'json',
):
    """
    便捷方法: 仅导出人工审核通过的切片
    等同于 export_dataset(only_approved=True)
    """
    return export_dataset(output_dir=output_dir, format=format, only_approved=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='导出标注数据集')
    parser.add_argument('--output', default='data/export', help='输出目录')
    parser.add_argument('--format', choices=['json', 'csv', 'manifest'], default='json')
    parser.add_argument('--min-confidence', type=float, default=0.6)
    parser.add_argument('--only-verified', action='store_true')
    parser.add_argument('--only-approved', action='store_true',
                        help='仅导出人工审核通过的切片 (推荐)')
    args = parser.parse_args()

    export_dataset(
        output_dir=args.output,
        format=args.format,
        min_confidence=args.min_confidence,
        only_verified=args.only_verified,
        only_approved=args.only_approved,
    )

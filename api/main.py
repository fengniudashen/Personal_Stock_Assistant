"""
VibeSing API - FastAPI 主入口
提供 REST API 接口管理数据管道和标注系统
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yaml

# 加载配置
CONFIG_PATH = Path(__file__).parent.parent / 'config_advanced.yaml'
with open(CONFIG_PATH, encoding='utf-8') as f:
    CONFIG = yaml.safe_load(f)

# 创建 FastAPI 应用
app = FastAPI(
    title="VibeSing 高音觉醒 - 标注系统 API",
    description="AI驱动的声乐音色标注与分析系统",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（音频切片）
clips_dir = Path(CONFIG['paths']['clips'])
if clips_dir.exists():
    app.mount("/audio", StaticFiles(directory=str(clips_dir)), name="audio")


# ========== 数据模型 ==========

class ClipInfo(BaseModel):
    clip_id: str
    path: str
    duration: float
    suggested_label: Optional[str] = None
    confidence: Optional[float] = None
    human_label: Optional[str] = None
    is_verified: bool = False


class AnnotationSubmit(BaseModel):
    clip_id: str
    primary_label: str
    secondary_labels: Optional[List[str]] = []
    quality_flags: Optional[List[str]] = []
    notes: Optional[str] = ""


class PipelineStatus(BaseModel):
    step: str
    status: str
    progress: float
    message: str


class ReviewSubmit(BaseModel):
    clip_id: str
    status: str  # approved / rejected
    primary_label: Optional[str] = None
    secondary_tags: Optional[List[str]] = []
    quality_flags: Optional[List[str]] = []
    notes: Optional[str] = ""


# ========== API 路由 ==========

@app.get("/")
async def root():
    return {
        "app": "VibeSing 高音觉醒",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    clips_dir = Path(CONFIG['paths']['clips'])
    clip_count = len(list(clips_dir.glob('*.wav'))) if clips_dir.exists() else 0

    # 加载融合标签统计
    fused_path = Path('data/fused_labels.json')
    label_stats = {}
    if fused_path.exists():
        with open(fused_path, encoding='utf-8') as f:
            fused = json.load(f)
        for item in fused:
            label = item.get('suggested_label', 'Unknown')
            label_stats[label] = label_stats.get(label, 0) + 1

    # 已标注数
    labeled_path = Path('data/labeled_clips.txt')
    labeled_count = 0
    if labeled_path.exists():
        with open(labeled_path) as f:
            labeled_count = len(f.read().splitlines())

    return {
        "total_clips": clip_count,
        "labeled_clips": labeled_count,
        "unlabeled_clips": clip_count - labeled_count,
        "label_distribution": label_stats,
        "progress_pct": (labeled_count / clip_count * 100) if clip_count > 0 else 0
    }


@app.get("/api/clips", response_model=List[ClipInfo])
async def get_clips(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    label: Optional[str] = None,
    unlabeled_only: bool = False
):
    """获取切片列表"""
    clips_metadata_path = Path('data/clips_metadata.json')
    if not clips_metadata_path.exists():
        return []

    with open(clips_metadata_path, encoding='utf-8') as f:
        all_clips = json.load(f)

    # 加载融合标签
    fused_lookup = {}
    fused_path = Path('data/fused_labels.json')
    if fused_path.exists():
        with open(fused_path, encoding='utf-8') as f:
            for item in json.load(f):
                fused_lookup[item['clip_id']] = item

    # 过滤
    result = []
    for clip in all_clips:
        clip_id = clip['clip_id']
        fused = fused_lookup.get(clip_id, {})

        info = ClipInfo(
            clip_id=clip_id,
            path=clip['path'],
            duration=clip.get('duration', 0),
            suggested_label=fused.get('suggested_label'),
            confidence=fused.get('confidence'),
        )

        if label and fused.get('suggested_label') != label:
            continue
        result.append(info)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size

    return result[start:end]


@app.get("/api/queue")
async def get_annotation_queue(limit: int = 50):
    """获取标注任务队列"""
    queue_path = Path('data/annotation_queue.json')
    if not queue_path.exists():
        return []

    with open(queue_path, encoding='utf-8') as f:
        queue = json.load(f)

    return queue[:limit]


@app.post("/api/annotate")
async def submit_annotation(annotation: AnnotationSubmit):
    """提交人工标注"""
    # 保存到 labeled_clips
    labeled_path = Path('data/labeled_clips.txt')
    with open(labeled_path, 'a') as f:
        f.write(annotation.clip_id + '\n')

    # 保存标注详情
    annotations_path = Path('data/annotations.jsonl')
    record = {
        'clip_id': annotation.clip_id,
        'primary_label': annotation.primary_label,
        'secondary_labels': annotation.secondary_labels,
        'quality_flags': annotation.quality_flags,
        'notes': annotation.notes,
        'annotated_at': datetime.utcnow().isoformat()
    }
    with open(annotations_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    return {"status": "ok", "clip_id": annotation.clip_id}


@app.post("/api/pipeline/run/{step}")
async def run_pipeline_step(step: str):
    """触发管道步骤执行"""
    valid_steps = [
        'extract', 'separate', 'slice', 'asr',
        'features', 'weak_labels', 'embedding',
        'clustering', 'active_learning', 'human_review'
    ]

    if step not in valid_steps:
        raise HTTPException(400, f"无效步骤: {step}. 可选: {valid_steps}")

    # 这里可以接入Celery异步任务
    return {
        "step": step,
        "status": "triggered",
        "message": f"步骤 {step} 已触发（使用 Celery worker 处理）"
    }


@app.get("/api/labels")
async def get_label_definitions():
    """获取标签体系定义"""
    return {
        "primary": CONFIG['labels']['primary'],
        "secondary": CONFIG['labels']['secondary'],
        "quality_flags": CONFIG['labels']['quality_flags'],
        "keywords": CONFIG['keywords']
    }


# ========== 人工审核 API (Step 10) ==========

@app.get("/api/review/stats")
async def get_review_stats():
    """获取人工审核进度统计"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    return manager.get_stats()


@app.get("/api/review/clips")
async def get_review_clips(
    status: Optional[str] = None,
    label: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """获取待审核切片列表"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    clips = manager.load_clips_for_review(
        status_filter=status,
        label_filter=label,
    )
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": len(clips),
        "page": page,
        "clips": clips[start:end],
    }


@app.post("/api/review/submit")
async def submit_review(review: ReviewSubmit):
    """提交单条人工审核结果"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    manager.submit_review(
        clip_id=review.clip_id,
        status=review.status,
        primary_label=review.primary_label,
        secondary_tags=review.secondary_tags,
        quality_flags=review.quality_flags,
        notes=review.notes,
    )
    return {"status": "ok", "clip_id": review.clip_id, "review_status": review.status}


@app.post("/api/review/batch-approve")
async def batch_approve(min_confidence: float = 0.92):
    """批量通过高置信度切片"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    count = manager.batch_approve_high_confidence(min_confidence=min_confidence)
    return {"status": "ok", "approved_count": count}


@app.post("/api/review/batch-reject")
async def batch_reject():
    """批量拒绝无效切片"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    count = manager.batch_reject_invalid()
    return {"status": "ok", "rejected_count": count}


@app.get("/api/review/approved")
async def get_approved_clips():
    """获取所有审核通过的切片（用于导出训练集）"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    return manager.get_approved_clips()


@app.get("/api/review/distribution")
async def get_review_distribution():
    """获取审核通过切片的标签分布"""
    from pipeline.step10_human_review import HumanReviewManager
    manager = HumanReviewManager(CONFIG)
    return manager.get_label_distribution()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

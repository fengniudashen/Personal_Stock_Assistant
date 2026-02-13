"""
VibeSing 数据库模型 - SQLAlchemy ORM
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    JSON, ForeignKey, Enum, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import enum

Base = declarative_base()


class PrimaryLabelEnum(enum.Enum):
    """ 主标签：发声机制（互斥单选）"""
    StrongMix = "StrongMix"
    LightMix = "LightMix"
    Falsetto = "Falsetto"
    Chest = "Chest"
    Head = "Head"
    Breathy = "Breathy"
    Strained = "Strained"
    Neutral = "Neutral"
    Invalid = "Invalid"


class SecondaryTagEnum(enum.Enum):
    """ 辅标签：共鸣/色彩技术（可叠加多选）"""
    Pharyngeal = "Pharyngeal"
    Twang = "Twang"
    HighRange = "HighRange"
    SuperHighRange = "SuperHighRange"
    VowelMod = "VowelMod"
    Vibrato = "Vibrato"
    Glissando = "Glissando"
    Runs = "Runs"
    Demo_Correct = "Demo_Correct"
    Demo_Error = "Demo_Error"


class QualityFlagEnum(enum.Enum):
    """ 质量旗标 """
    LowSNR = "LowSNR"
    HighReverb = "HighReverb"
    Clipping = "Clipping"
    Unstable = "Unstable"
    MultiVoice = "MultiVoice"
    Distortion = "Distortion"


class ReviewStatusEnum(enum.Enum):
    """ 人工审核状态 """
    pending = "pending"      # 待审核
    approved = "approved"    # 审核通过
    rejected = "rejected"    # 审核拒绝


# 向后兼容
LabelEnum = PrimaryLabelEnum


class SourceTypeEnum(enum.Enum):
    bilibili = "bilibili"
    youtube = "youtube"
    tieba = "tieba"
    douyin = "douyin"
    course = "course"
    song = "song"
    dataset = "dataset"
    other = "other"


class AudioSource(Base):
    """音频来源表"""
    __tablename__ = 'audio_sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(50), nullable=False)
    url = Column(Text, nullable=True)
    title = Column(String(500), nullable=True)
    artist = Column(String(200), nullable=True)
    duration = Column(Float, nullable=True)
    local_path = Column(Text, nullable=True)
    clean_path = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    clips = relationship("AudioClip", back_populates="source")


class AudioClip(Base):
    """音频切片表"""
    __tablename__ = 'audio_clips'

    id = Column(Integer, primary_key=True, autoincrement=True)
    clip_id = Column(String(200), unique=True, nullable=False, index=True)
    source_id = Column(Integer, ForeignKey('audio_sources.id'), nullable=True)
    file_path = Column(Text, nullable=False)
    t0 = Column(Float, nullable=True)  # 源音频中的起始时间
    t1 = Column(Float, nullable=True)  # 源音频中的结束时间
    duration = Column(Float, nullable=True)
    sample_rate = Column(Integer, default=44100)

    # 音频特征
    rms = Column(Float, nullable=True)
    zcr = Column(Float, nullable=True)
    pitch_mean = Column(Float, nullable=True)
    pitch_std = Column(Float, nullable=True)
    h1_h2 = Column(Float, nullable=True)
    hnr = Column(Float, nullable=True)
    jitter = Column(Float, nullable=True)
    shimmer = Column(Float, nullable=True)

    # 嵌入存储
    embedding_path = Column(Text, nullable=True)
    cluster_id = Column(Integer, nullable=True)

    # 弱标签
    suggested_label = Column(String(50), nullable=True)
    weak_confidence = Column(Float, nullable=True)
    asr_label = Column(String(50), nullable=True)
    heuristic_label = Column(String(50), nullable=True)
    model_label = Column(String(50), nullable=True)
    conflict_score = Column(Float, nullable=True)

    # 人工标注
    human_label = Column(String(50), nullable=True)
    secondary_labels = Column(JSON, nullable=True)
    quality_flags = Column(JSON, nullable=True)
    annotator_notes = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    annotated_at = Column(DateTime, nullable=True)
    annotator = Column(String(100), nullable=True)

    # 人工审核 (Step 10)
    review_status = Column(String(20), default='pending')  # pending/approved/rejected
    review_primary_label = Column(String(50), nullable=True)  # 审核确认/修正后的主标签
    review_secondary_tags = Column(JSON, nullable=True)       # 审核确认/修正后的辅标签
    review_quality_flags = Column(JSON, nullable=True)        # 审核确认/修正后的质量旗标
    reviewer_notes = Column(Text, nullable=True)              # 审核备注
    reviewed_at = Column(DateTime, nullable=True)             # 审核时间

    # 状态
    needs_review = Column(Boolean, default=False)
    is_exported = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    source = relationship("AudioSource", back_populates="clips")


class AnnotationSession(Base):
    """标注会话记录"""
    __tablename__ = 'annotation_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotator = Column(String(100), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    clips_annotated = Column(Integer, default=0)
    clips_skipped = Column(Integer, default=0)
    avg_time_per_clip = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)


class PipelineRun(Base):
    """管道运行记录"""
    __tablename__ = 'pipeline_runs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_name = Column(String(100), nullable=False)
    status = Column(String(20), default='running')  # running, completed, failed
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    items_processed = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    config_snapshot = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)


class ModelVersion(Base):
    """模型版本表"""
    __tablename__ = 'model_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False)
    model_type = Column(String(50), nullable=False)  # onnx, pytorch
    model_path = Column(Text, nullable=False)
    training_data_count = Column(Integer, nullable=True)
    accuracy = Column(Float, nullable=True)
    metrics_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=False)


# ========== 数据库工具函数 ==========

def get_engine(connection_string: str):
    """创建数据库引擎"""
    if connection_string.startswith('sqlite'):
        return create_engine(connection_string, echo=False)
    else:
        return create_engine(connection_string, pool_size=5, max_overflow=10, echo=False)


def get_session(connection_string: str):
    """创建数据库会话"""
    engine = get_engine(connection_string)
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(connection_string: str):
    """初始化数据库（创建所有表）"""
    engine = get_engine(connection_string)
    Base.metadata.create_all(engine)
    return engine

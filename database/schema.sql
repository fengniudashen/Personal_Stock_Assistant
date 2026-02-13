-- ============================================================
-- VibeSing Database Schema (PostgreSQL / SQLite compatible)
-- ============================================================

CREATE TABLE IF NOT EXISTS audio_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type VARCHAR(50) NOT NULL,
    url TEXT,
    title VARCHAR(500),
    artist VARCHAR(200),
    duration REAL,
    local_path TEXT,
    clean_path TEXT,
    metadata_json TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audio_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clip_id VARCHAR(200) UNIQUE NOT NULL,
    source_id INTEGER REFERENCES audio_sources(id),
    file_path TEXT NOT NULL,
    t0 REAL,
    t1 REAL,
    duration REAL,
    sample_rate INTEGER DEFAULT 44100,

    -- 声学特征
    rms REAL,
    zcr REAL,
    pitch_mean REAL,
    pitch_std REAL,
    h1_h2 REAL,
    hnr REAL,
    jitter REAL,
    shimmer REAL,

    -- 嵌入
    embedding_path TEXT,
    cluster_id INTEGER,

    -- 弱标签
    suggested_label VARCHAR(50),
    weak_confidence REAL,
    asr_label VARCHAR(50),
    heuristic_label VARCHAR(50),
    model_label VARCHAR(50),
    conflict_score REAL,

    -- 人工标注
    human_label VARCHAR(50),
    secondary_labels TEXT,  -- JSON
    quality_flags TEXT,     -- JSON
    annotator_notes TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    annotated_at TIMESTAMP,
    annotator VARCHAR(100),

    -- 状态
    needs_review BOOLEAN DEFAULT FALSE,
    is_exported BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clips_clip_id ON audio_clips(clip_id);
CREATE INDEX IF NOT EXISTS idx_clips_label ON audio_clips(human_label);
CREATE INDEX IF NOT EXISTS idx_clips_suggested ON audio_clips(suggested_label);
CREATE INDEX IF NOT EXISTS idx_clips_cluster ON audio_clips(cluster_id);
CREATE INDEX IF NOT EXISTS idx_clips_review ON audio_clips(needs_review);

CREATE TABLE IF NOT EXISTS annotation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotator VARCHAR(100) NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    clips_annotated INTEGER DEFAULT 0,
    clips_skipped INTEGER DEFAULT 0,
    avg_time_per_clip REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'running',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    items_processed INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    config_snapshot TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version VARCHAR(50) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    model_path TEXT NOT NULL,
    training_data_count INTEGER,
    accuracy REAL,
    metrics_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE
);

# VibeSing 高音觉醒 - Auto-Labeling System

> AI驱动的声乐分类自动标注系统，为「高音觉醒」iOS App 提供训练数据

## 🏗️ 项目结构

```
vibesing-labeling/
├── config_advanced.yaml      # 主配置文件
├── requirements.txt          # Python 依赖
├── run_download.py           # 数据下载编排器
├── run_full_pipeline.py      # 完整 ETL 流水线
├── Makefile                  # 快捷命令
├── Dockerfile                # 容器构建
├── docker-compose.yml        # 多服务编排
│
├── pipeline/                 # 9步 ETL 流水线
│   ├── step1_extract.py      # 音频提取 (video → wav)
│   ├── step2_separate.py     # 人声分离 (demucs)
│   ├── step3_slice.py        # 智能切片 (VAD + energy)
│   ├── step4_asr.py          # ASR + 关键词标注
│   ├── step5_features.py     # 声学特征提取
│   ├── step6_weak_labels.py  # 弱标签融合
│   ├── step7_embedding.py    # 嵌入向量 + FAISS
│   ├── step8_clustering.py   # HDBSCAN 聚类
│   └── step9_active_learning.py  # 主动学习采样
│
├── models/                   # 模型模块
│   ├── heuristics.py         # 规则启发式分类器
│   ├── teacher_model.py      # 教师模型 (ONNX/PyTorch)
│   └── label_fusion.py       # Snorkel 风格标签融合
│
├── downloaders/              # 多平台下载器
│   ├── bilibili.py           # B站视频下载
│   ├── youtube.py            # YouTube 下载
│   ├── douyin.py             # 抖音下载
│   ├── tieba.py              # 贴吧音频爬虫
│   └── dataset.py            # 公开数据集 (GTSinger/VocalSet)
│
├── database/                 # 数据库
│   ├── models.py             # SQLAlchemy ORM
│   └── schema.sql            # SQL Schema
│
├── api/                      # FastAPI 后端
│   ├── main.py               # API 入口
│   ├── tasks.py              # Celery 异步任务
│   └── routes/               # 路由模块
│
├── utils/                    # 工具库
│   ├── audio_validator.py    # 音频质量验证
│   └── dedup.py              # 音频去重
│
├── frontend/                 # 前端/标注
│   └── labelstudio_plugin/
│       ├── label_config.xml  # Label Studio 标注配置
│       ├── ml_backend.py     # ML Backend (AI预标签)
│       └── ui_tweaks.css     # 自定义样式
│
├── scripts/                  # 辅助脚本
│   ├── init_db.py            # 数据库初始化
│   ├── export_dataset.py     # 导出标注数据
│   ├── prepare_labelstudio_tasks.py  # 生成标注任务
│   └── import_to_labelstudio.py      # 导入到 Label Studio
│
└── data/                     # 数据目录 (不提交到git)
    ├── raw_audio/            # 原始下载
    ├── separated/            # 人声分离后
    ├── clips/                # 切片片段
    ├── labels/               # 弱标签
    ├── features/             # 特征文件
    ├── embeddings/           # 嵌入向量
    ├── models/               # 训练模型
    └── export/               # 导出数据集
```

## 🚀 快速开始

### 1. 环境搭建

```bash
# 创建虚拟环境
py -m venv .venv
.venv\Scripts\activate

# 安装依赖
py -m pip install -r requirements.txt

# 初始化数据库
py scripts/init_db.py
```

### 2. 下载数据

```bash
# 下载所有平台
py run_download.py

# 仅下载B站
py run_download.py --platform bilibili --max-videos 50
```

### 3. 运行 ETL 流水线

```bash
# 完整流水线
py run_full_pipeline.py

# 仅运行指定步骤
py run_full_pipeline.py --step 3   # 仅切片
py run_full_pipeline.py --start 5 --end 8  # 特征→聚类
```

### 4. 标注

```bash
# 准备标注任务
py scripts/prepare_labelstudio_tasks.py

# 导入到 Label Studio
py scripts/import_to_labelstudio.py
```

### 5. 导出训练数据

```bash
py scripts/export_dataset.py --format json --min-confidence 0.7
```

## 🐳 Docker 部署

```bash
docker-compose up -d
```

服务：
- **API**: http://localhost:8000
- **Label Studio**: http://localhost:8080
- **ML Backend**: http://localhost:9090

## 🏷️ 标签体系

### 主标签 (11类)
| 标签 | 快捷键 | 说明 |
|------|---------|------|
| StrongMix | 1 | 强混声 |
| LightMix | 2 | 弱混声 |
| Strained | 3 | 挤卡 |
| Breathy | 4 | 气声 |
| Falsetto | 5 | 假声 |
| Chest | 6 | 胸声 |
| Head | 7 | 头声 |
| Twang | 8 | Twang |
| Pharyngeal | 9 | 咽音 |
| Neutral | 0 | 中性 |
| Invalid | - | 无效 |

### 副标签 (8类)
Vibrato, Belt, Rasp, Nasal, Whistle, Growl, Distortion, Cry

## 📄 License

Internal Project - VibeSing Team

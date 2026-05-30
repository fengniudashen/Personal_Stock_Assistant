# 🚀 VibeSing v2.0 - GitHub 推送指南

## 📋 当前状态

项目已成功初始化为 Git 仓库并准备好推送到 GitHub。

```
✅ Git 仓库已初始化: .git 目录存在
✅ 首次提交已完成: 51 个文件已暂存
✅ 代码已提交: "Initial commit: VibeSing v2.0 with human review system"
✅ 远程仓库已配置: origin → https://github.com/fengniudashen/VOICE_LABEL.git
```

**但**: GitHub 需要使用 **个人访问令牌 (PAT)** 而非密码来进行 Git 操作

## 🔑 快速开始 - 三步推送

### 步骤 1️⃣: 创建 GitHub 个人访问令牌

1. 打开: https://github.com/login
2. 登录: `suiyuan9201@gmail.com` + 密码

3. 点击右上角 ☰ → **Settings**

4. 左侧菜单 → **Developer settings** → **Personal access tokens** → **Tokens (classic)**

5. 点击 **Generate new token (classic)**

6. 填写信息:
   - **Note** (名称): `VOICE_LABEL_GITHUB`
   - **Expiration**: `90 days` (推荐)
   
7. **Select scopes** 勾选:
   ```
   ☑ repo                      (完整私有仓库访问)
   ☑ write:repo_hook
   ```

8. 点击下方 **Generate token**

9. **立即复制令牌** (格式: `ghp_xxxxxxxxxxxxx...`)

⚠️ 关闭页面后无法再看到令牌，必须立即复制！

### 步骤 2️⃣: 运行推送脚本

打开 PowerShell，运行：

```powershell
cd e:\VOICE\vibesing-labeling
.\push-to-github.ps1
```

按照脚本提示粘贴您的令牌。

### 步骤 3️⃣: 验证

推送完成后访问: **https://github.com/fengniudashen/VOICE_LABEL**

应该能看到所有 51 个文件！

---

## 📝 完整说明

如果上述快速步骤遇到问题，请查看: **GitHub_推送说明.md**

---

## 📦 项目内容

此仓库包含 **VibeSing v2.0** 完整项目:

### 核心功能 (10 个 Pipeline 步骤)
1. **Step 1**: 音频提取 (AudioExtractor)
2. **Step 2**: 人声分离 (VocalSeparator)
3. **Step 3**: 智能切片 (HybridSlicer)
4. **Step 4**: ASR 识别 (ASRAnnotator)
5. **Step 5**: 特征提取 (FeatureExtractor)
6. **Step 6**: 弱标签融合 (LabelFuser)
7. **Step 7**: 嵌入计算 (EmbeddingExtractor)
8. **Step 8**: 聚类去重 (AudioClusterer)
9. **Step 9**: 主动学习 (ActiveLearningScheduler)
10. **Step 10**: 👤 人工审核 (HumanReviewManager) ⭐ 新增

### GUI 界面
- 15 个操作面板，涵盖所有 pipeline 步骤
- 人工审核面板：逐条审核切片，支持播放、修改标签、批量操作
- 实时统计和进度显示

### 标签体系 v2
- **9 个主标签**：发声机制（StrongMix, LightMix, Falsetto, Chest, Head, Breathy, Strained, Neutral, Invalid）
- **10 个辅标签**：共鸣色彩（Pharyngeal, Twang, HighRange, SuperHighRange, VowelMod, Vibrato, Glissando, Runs, Demo_Correct, Demo_Error）
- **6 个质量旗标**：音频质量（LowSNR, HighReverb, Clipping, Unstable, MultiVoice, Distortion）

### 模型和 AI
- **VibeSingMultiTaskModel**: CNN 编码器 + 3 个分类头（2.6M 参数）
- **Teacher Model**: 强弱监督融合
- **启发式分类器**: 基于声学特征的规则推理

### API 和数据库
- **FastAPI**: 12 个 REST 接口  + 7 个审核 API
- **SQLAlchemy ORM**: 5 个数据表（sources, clips, sessions, runs, versions）
- **审核系统**: review_results.json，支持通过/拒绝/修改标签

### 文档
- **GUI_操作指南.md**: 20 章节详细使用手册
- **README.md**: 快速开始指南

---

## 🔧 本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/init_db.py

# 启动 GUI
python -m gui.main_app

# 启动 API
uvicorn api.main:app --reload
```

---

## 📁 项目结构

```
vibesing-labeling/
├── pipeline/              # 10 个处理步骤
├── models/               # 模型定义
├── gui/                  # GUI 界面
├── api/                  # FastAPI 接口
├── database/             # 数据库模型
├── downloaders/          # 下载器
├── scripts/              # 工具脚本
├── frontend/             # Label Studio 插件
├── docs/                 # 文档
├── config_advanced.yaml  # 配置文件
└── requirements.txt      # 依赖
```

---

## ✨ 最新特性

### 人工审核系统 (Step 10)
- ✅ 逐条审核图形化界面
- ✅ 音频试听功能
- ✅ 标签修改和确认
- ✅ 批量自动通过/拒绝
- ✅ 快捷键支持 (A/R/S/Space)
- ✅ 审核状态筛选
- ✅ 仅导出已审核通过的切片

### API 审核端点
```
GET  /api/review/stats          - 审核进度统计
GET  /api/review/clips          - 待审核切片列表
POST /api/review/submit         - 提交单条审核
POST /api/review/batch-approve  - 批量自动通过
POST /api/review/batch-reject   - 批量自动拒绝
GET  /api/review/approved       - 获取已通过切片
GET  /api/review/distribution   - 标签分布统计
```

---

## 🆘 技术支持

遇到推送问题？检查以下几点：

1. ✓ 令牌有效期未过期
2. ✓ 令牌包含 `repo` scope
3. ✓ 令牌不含空格或特殊字符
4. ✓ 网络连接正常

详见: **GitHub_推送说明.md**

---

**项目创建时间**: 2026-02-13  
**状态**: ✅ 开发完成，准备发布  
**版本**: v2.0 with Human Review System

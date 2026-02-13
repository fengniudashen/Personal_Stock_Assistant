# VibeSing 高音觉醒 - Makefile
# 使用: make <target>

.PHONY: setup venv install init-db download pipeline annotate export retrain clean help

PYTHON = py
PIP = $(PYTHON) -m pip
VENV = .venv

# ===== 帮助 =====
help:
	@echo ============================================
	@echo   VibeSing 高音觉醒 - 自动标注系统
	@echo ============================================
	@echo.
	@echo   make setup         完整环境搭建
	@echo   make venv          创建虚拟环境
	@echo   make install       安装依赖
	@echo   make init-db       初始化数据库
	@echo   make download      下载音频数据
	@echo   make pipeline      运行完整ETL流水线
	@echo   make annotate      启动标注任务准备
	@echo   make export        导出标注数据
	@echo   make retrain       重新训练教师模型
	@echo   make docker-up     启动Docker服务
	@echo   make docker-down   停止Docker服务
	@echo   make clean         清理临时文件
	@echo   make test          运行基础测试
	@echo.

# ===== 环境搭建 =====
setup: venv install init-db
	@echo 环境搭建完成！

venv:
	$(PYTHON) -m venv $(VENV)
	@echo 虚拟环境已创建: $(VENV)

install:
	$(PIP) install -r requirements.txt
	@echo 依赖安装完成

init-db:
	$(PYTHON) scripts/init_db.py

# ===== 数据采集 =====
download:
	$(PYTHON) run_download.py

# ===== ETL 流水线 =====
pipeline:
	$(PYTHON) run_full_pipeline.py

# ===== 标注相关 =====
annotate:
	$(PYTHON) scripts/prepare_labelstudio_tasks.py
	@echo 标注任务已准备，请导入到 Label Studio

export:
	$(PYTHON) scripts/export_dataset.py --format json
	$(PYTHON) scripts/export_dataset.py --format csv
	@echo 数据集已导出到 data/export/

# ===== 模型训练 =====
retrain:
	$(PYTHON) -c "from pipeline.step9_active_learning import ActiveLearningScheduler; print('TODO: retrain integration')"

# ===== Docker =====
docker-up:
	docker-compose up -d
	@echo Docker 服务已启动

docker-down:
	docker-compose down
	@echo Docker 服务已停止

# ===== API 服务 =====
api:
	$(PYTHON) -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# ===== 测试 =====
test:
	$(PYTHON) -c "import yaml; print('✅ yaml')"
	$(PYTHON) -c "import sqlalchemy; print('✅ sqlalchemy')"
	$(PYTHON) -c "from pathlib import Path; print('✅ pathlib')"
	@echo 基础导入测试通过

# ===== 清理 =====
clean:
	@echo 正在清理...
	-rd /s /q __pycache__ 2>nul
	-rd /s /q .pytest_cache 2>nul
	-del /q *.pyc 2>nul
	-del /q data\*.log 2>nul
	@echo 清理完成

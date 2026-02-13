"""
导入任务到 Label Studio
使用 Label Studio SDK 自动创建项目并导入任务
"""
import sys
import json
import logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def import_to_labelstudio(
    tasks_file: str = 'data/labelstudio_tasks.json',
    config_path: str = None,
    project_title: str = 'VibeSing 高音觉醒',
):
    """
    将任务导入到 Label Studio
    
    Args:
        tasks_file: 任务JSON文件路径
        config_path: 配置文件路径
        project_title: Label Studio 项目名
    """
    # 加载配置
    if config_path is None:
        config_path = str(ROOT / 'config_advanced.yaml')
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    ls_config = config.get('labelstudio', {})
    ls_url = ls_config.get('url', 'http://localhost:8080')
    ls_token = ls_config.get('api_key', '')

    if not ls_token:
        logger.error("Label Studio API Key 未配置！")
        logger.info("请在 config_advanced.yaml 的 labelstudio.api_key 中填入 Token")
        logger.info("获取方式: Label Studio → Account & Settings → Access Token")
        return

    # 加载任务
    tasks_file = Path(tasks_file)
    if not tasks_file.exists():
        logger.error(f"任务文件不存在: {tasks_file}")
        logger.info("请先运行: py scripts/prepare_labelstudio_tasks.py")
        return

    with open(tasks_file, encoding='utf-8') as f:
        tasks = json.load(f)
    logger.info(f"加载了 {len(tasks)} 个任务")

    # 加载标注配置
    label_config_path = ROOT / 'frontend' / 'labelstudio_plugin' / 'label_config.xml'
    with open(label_config_path, encoding='utf-8') as f:
        label_config_xml = f.read()

    try:
        from label_studio_sdk import Client
    except ImportError:
        logger.error("请安装: pip install label-studio-sdk")
        return

    # 连接 Label Studio
    ls = Client(url=ls_url, api_key=ls_token)
    ls.check_connection()
    logger.info(f"已连接 Label Studio: {ls_url}")

    # 查找或创建项目
    projects = ls.list_projects()
    project = None
    for p in projects:
        if p.title == project_title:
            project = p
            logger.info(f"找到已有项目: {project_title} (ID={p.id})")
            break

    if project is None:
        project = ls.create_project(
            title=project_title,
            description='VibeSing 高音觉醒 - AI声乐分类标注',
            label_config=label_config_xml,
        )
        logger.info(f"已创建新项目: {project_title} (ID={project.id})")

    # 导入任务
    project.import_tasks(tasks)
    logger.info(f"✅ 已导入 {len(tasks)} 个任务到项目 '{project_title}'")
    logger.info(f"🔗 打开标注: {ls_url}/projects/{project.id}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='导入任务到 Label Studio')
    parser.add_argument('--tasks', default='data/labelstudio_tasks.json')
    parser.add_argument('--title', default='VibeSing 高音觉醒')
    args = parser.parse_args()

    import_to_labelstudio(tasks_file=args.tasks, project_title=args.title)

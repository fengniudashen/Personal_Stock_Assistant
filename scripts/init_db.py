"""
数据库初始化脚本
创建表结构、初始数据
"""
import sys
from pathlib import Path

# 添加项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from database.models import Base, get_engine, get_session, init_db, AudioSource
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 加载配置获取数据库路径
CONFIG_PATH = ROOT / 'config_advanced.yaml'
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, encoding='utf-8') as f:
        _config = yaml.safe_load(f)
    DB_PATH = Path(_config.get('paths', {}).get('database', 'data/vibesing.db'))
else:
    DB_PATH = Path('data/vibesing.db')

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CONNECTION_STRING = f'sqlite:///{DB_PATH}'


def init_database():
    """创建所有表"""
    logger.info(f"正在创建数据库表... ({CONNECTION_STRING})")
    engine = init_db(CONNECTION_STRING)
    logger.info("数据库表创建完成")

    # 插入默认数据源
    session = get_session(CONNECTION_STRING)
    try:
        existing = session.query(AudioSource).count()
        if existing == 0:
            default_sources = [
                AudioSource(
                    source_type='bilibili',
                    url='https://www.bilibili.com',
                    title='B站高音翻唱/声乐教学',
                    metadata_json={'keywords': '高音翻唱,声乐教学,混声训练'}
                ),
                AudioSource(
                    source_type='youtube',
                    url='https://www.youtube.com',
                    title='YouTube vocal training',
                    metadata_json={'keywords': 'vocal mix,singing high notes'}
                ),
                AudioSource(
                    source_type='dataset',
                    url='https://github.com/gtsinger',
                    title='公开数据集 GTSinger/VocalSet',
                    metadata_json={'keywords': 'GTSinger,VocalSet'}
                ),
            ]
            session.add_all(default_sources)
            session.commit()
            logger.info(f"已插入 {len(default_sources)} 条默认数据源")
        else:
            logger.info(f"数据库中已有 {existing} 条数据源")
    except Exception as e:
        session.rollback()
        logger.error(f"插入默认数据失败: {e}")
    finally:
        session.close()

    return engine


def verify_database():
    """验证数据库状态"""
    from sqlalchemy import inspect
    engine = get_engine(CONNECTION_STRING)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"数据库中的表: {tables}")
    for table in tables:
        columns = inspector.get_columns(table)
        logger.info(f"  {table}: {[c['name'] for c in columns]}")


if __name__ == '__main__':
    init_database()
    verify_database()
    logger.info("数据库初始化完成！")

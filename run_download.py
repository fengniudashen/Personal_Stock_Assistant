"""
VibeSing 高音觉醒 - 数据下载编排器
统一调度多平台下载
"""
import sys
import yaml
import logging
import argparse
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'data/download_{datetime.now():%Y%m%d}.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger('VibeSing.Download')


def load_config(config_path: str = 'config_advanced.yaml') -> dict:
    with open(config_path, encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_bilibili(config: dict, max_videos: int = 0):
    """下载B站视频"""
    from downloaders.bilibili import BilibiliDownloader
    dl = BilibiliDownloader(config)
    sources = config.get('sources', {}).get('bilibili', {})
    keywords = sources.get('keywords', [])
    urls = sources.get('urls', [])

    # 关键词搜索
    for kw in keywords:
        logger.info(f"[B站] 搜索关键词: {kw}")
        results = dl.search(kw, max_results=max_videos or 20)
        for video in results:
            try:
                dl.download(video['url'])
            except Exception as e:
                logger.error(f"下载失败: {video.get('url')} - {e}")

    # 直接URL
    for url in urls:
        try:
            dl.download(url)
        except Exception as e:
            logger.error(f"下载失败: {url} - {e}")


def run_youtube(config: dict, max_videos: int = 0):
    """下载YouTube视频"""
    from downloaders.youtube import YouTubeDownloader
    dl = YouTubeDownloader(config)
    sources = config.get('sources', {}).get('youtube', {})
    keywords = sources.get('keywords', [])
    urls = sources.get('urls', [])

    for kw in keywords:
        logger.info(f"[YouTube] 搜索关键词: {kw}")
        results = dl.search(kw, max_results=max_videos or 10)
        for video in results:
            try:
                dl.download(video['url'])
            except Exception as e:
                logger.error(f"下载失败: {video.get('url')} - {e}")

    for url in urls:
        try:
            dl.download(url)
        except Exception as e:
            logger.error(f"下载失败: {url} - {e}")


def run_douyin(config: dict, max_videos: int = 0):
    """下载抖音视频"""
    from downloaders.douyin import DouyinDownloader
    dl = DouyinDownloader(config)
    sources = config.get('sources', {}).get('douyin', {})
    urls = sources.get('urls', [])

    for url in urls:
        try:
            dl.download(url)
        except Exception as e:
            logger.error(f"下载失败: {url} - {e}")


def run_tieba(config: dict, max_posts: int = 0):
    """抓取贴吧音频"""
    from downloaders.tieba import TiebaSpider
    spider = TiebaSpider(config)
    sources = config.get('sources', {}).get('tieba', {})
    keywords = sources.get('keywords', [])

    for kw in keywords:
        logger.info(f"[贴吧] 搜索关键词: {kw}")
        try:
            spider.crawl(kw, max_pages=max_posts or 5)
        except Exception as e:
            logger.error(f"抓取失败: {kw} - {e}")


def run_datasets(config: dict):
    """下载公开数据集"""
    from downloaders.dataset import DatasetDownloader
    dl = DatasetDownloader(config)
    datasets = config.get('sources', {}).get('datasets', [])

    for ds_name in datasets:
        logger.info(f"[数据集] 下载: {ds_name}")
        try:
            dl.download(ds_name)
        except Exception as e:
            logger.error(f"数据集下载失败: {ds_name} - {e}")


def main():
    parser = argparse.ArgumentParser(description='VibeSing 数据下载编排器')
    parser.add_argument('--config', default='config_advanced.yaml', help='配置文件路径')
    parser.add_argument('--platform', choices=['all', 'bilibili', 'youtube', 'douyin', 'tieba', 'dataset'],
                        default='all', help='下载平台')
    parser.add_argument('--max-videos', type=int, default=0, help='每个关键词最大下载数')
    args = parser.parse_args()

    config = load_config(args.config)

    logger.info("=" * 60)
    logger.info("VibeSing 高音觉醒 - 数据下载启动")
    logger.info(f"平台: {args.platform}")
    logger.info("=" * 60)

    platform = args.platform

    try:
        if platform in ('all', 'bilibili'):
            logger.info("\n>>> 阶段 1/5: 下载B站视频")
            run_bilibili(config, args.max_videos)

        if platform in ('all', 'youtube'):
            logger.info("\n>>> 阶段 2/5: 下载YouTube视频")
            run_youtube(config, args.max_videos)

        if platform in ('all', 'douyin'):
            logger.info("\n>>> 阶段 3/5: 下载抖音视频")
            run_douyin(config, args.max_videos)

        if platform in ('all', 'tieba'):
            logger.info("\n>>> 阶段 4/5: 抓取贴吧音频")
            run_tieba(config, args.max_videos)

        if platform in ('all', 'dataset'):
            logger.info("\n>>> 阶段 5/5: 下载公开数据集")
            run_datasets(config)

    except KeyboardInterrupt:
        logger.warning("\n用户中断下载")

    logger.info("\n" + "=" * 60)
    logger.info("下载任务完成")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()

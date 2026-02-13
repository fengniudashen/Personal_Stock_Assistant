"""
YouTube 视频下载器
使用 yt-dlp 按关键词搜索和下载声乐教学视频
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class YouTubeDownloader:
    """YouTube视频下载器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path("data/raw_videos/youtube")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / '%(title)s-%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-Hans', 'zh'],
            'ignoreerrors': True,
        }

        filters = config.get('filters', {})
        self.min_duration = filters.get('min_duration', 30)
        self.max_duration = filters.get('max_duration', 3600)

    def download_urls(self, urls: List[str]) -> List[Dict]:
        """直接下载URL列表"""
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp 未安装！请运行: pip install yt-dlp")
            return []

        results = []
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            for url in urls:
                try:
                    logger.info(f"📥 下载: {url}")
                    info = ydl.extract_info(url, download=True)
                    if info:
                        results.append({
                            'source': 'youtube',
                            'url': url,
                            'title': info.get('title', 'Unknown'),
                            'duration': info.get('duration', 0),
                            'channel': info.get('channel', 'Unknown'),
                            'filename': ydl.prepare_filename(info),
                        })
                        logger.info(f"✅ 完成: {info.get('title')}")
                except Exception as e:
                    logger.error(f"❌ 失败: {url} - {e}")

        return results

    def search_and_download(self, keywords: List[str], max_results: int = 10) -> List[Dict]:
        """通过关键词搜索并下载"""
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp 未安装！")
            return []

        results = []

        # 下载前先搜索
        search_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / '%(title)s-%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'default_search': 'ytsearch',
            'ignoreerrors': True,
        }

        for keyword in keywords:
            search_query = f"ytsearch{max_results}:{keyword}"
            logger.info(f"🔍 搜索: {keyword} (最多{max_results}个)")

            try:
                with yt_dlp.YoutubeDL(search_opts) as ydl:
                    # 先获取搜索结果信息
                    info = ydl.extract_info(search_query, download=False)

                    if not info or 'entries' not in info:
                        continue

                    for entry in info['entries']:
                        if entry is None:
                            continue

                        duration = entry.get('duration', 0)

                        # 过滤时长
                        if not (self.min_duration <= duration <= self.max_duration):
                            logger.info(f"  ⏭️ 跳过(时长{duration}s): {entry.get('title', '')[:50]}")
                            continue

                        # 下载
                        try:
                            ydl.download([entry['webpage_url']])
                            results.append({
                                'source': 'youtube',
                                'url': entry['webpage_url'],
                                'title': entry.get('title', 'Unknown'),
                                'duration': duration,
                                'channel': entry.get('channel', 'Unknown'),
                                'keyword': keyword,
                            })
                            logger.info(f"  ✅ {entry.get('title', '')[:60]}")
                        except Exception as e:
                            logger.error(f"  ❌ 下载失败: {e}")

            except Exception as e:
                logger.error(f"搜索失败: {keyword} - {e}")

        return results

    def download_from_config(self) -> List[Dict]:
        """从配置文件读取参数并执行"""
        yt_cfg = self.config.get('sources', {}).get('youtube', {})

        if not yt_cfg.get('enabled', False):
            logger.info("YouTube下载器未启用")
            return []

        results = []

        # 按关键词搜索
        keywords = yt_cfg.get('keywords', [])
        max_results = yt_cfg.get('max_results', 10)
        if keywords:
            results.extend(self.search_and_download(keywords, max_results))

        # 直接URL
        channels = yt_cfg.get('channels', [])
        if channels:
            results.extend(self.download_urls(channels))

        return results


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    downloader = YouTubeDownloader(config)
    results = downloader.download_from_config()

    metadata_file = Path('data/metadata_youtube.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 YouTube下载完成，共 {len(results)} 个视频")


if __name__ == "__main__":
    main()

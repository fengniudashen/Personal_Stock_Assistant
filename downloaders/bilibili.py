"""
B站(Bilibili)视频下载器
使用 yt-dlp 下载B站教学视频并提取音频
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class BilibiliDownloader:
    """B站视频下载器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path("data/raw_videos/bilibili")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        download_cfg = config.get('download', {})
        bilibili_cfg = config.get('sources', {}).get('bilibili', {})

        self.ydl_opts = {
            'format': download_cfg.get('format', 'bestaudio/best'),
            'outtmpl': str(self.output_dir / download_cfg.get('output_template', '%(title)s-%(id)s.%(ext)s')),
            'writesubtitles': bilibili_cfg.get('subtitle', True),
            'writeautomaticsub': True,
            'subtitleslangs': ['zh-Hans', 'zh-CN', 'zh'],
            'retries': download_cfg.get('retries', 3),
            'ignoreerrors': True,
            'no_warnings': False,
            'quiet': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
        }

        rate_limit = download_cfg.get('rate_limit', '1M')
        self.ydl_opts['ratelimit'] = self._parse_rate(rate_limit)

    @staticmethod
    def _parse_rate(rate_str: str) -> int:
        """解析速率限制字符串"""
        if isinstance(rate_str, int):
            return rate_str
        rate_str = str(rate_str).strip()
        if rate_str.upper().endswith('M'):
            return int(float(rate_str[:-1]) * 1024 * 1024)
        elif rate_str.upper().endswith('K'):
            return int(float(rate_str[:-1]) * 1024)
        return int(rate_str)

    def download(self, urls: List[str]) -> List[Dict]:
        """
        下载B站视频
        
        Args:
            urls: B站视频URL列表
            
        Returns:
            下载结果元数据列表
        """
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
                        # 处理合集（多P视频）
                        entries = info.get('entries', [info])
                        for entry in entries:
                            if entry is None:
                                continue
                            metadata = {
                                'source': 'bilibili',
                                'url': url,
                                'title': entry.get('title', 'Unknown'),
                                'duration': entry.get('duration', 0),
                                'uploader': entry.get('uploader', 'Unknown'),
                                'upload_date': entry.get('upload_date', ''),
                                'view_count': entry.get('view_count', 0),
                                'description': (entry.get('description', '') or '')[:500],
                                'tags': entry.get('tags', []),
                                'filename': ydl.prepare_filename(entry),
                            }
                            results.append(metadata)
                            logger.info(f"✅ 完成: {metadata['title']}")

                except Exception as e:
                    logger.error(f"❌ 失败: {url} - {e}")

        return results

    def download_from_config(self) -> List[Dict]:
        """从配置文件读取URL并下载"""
        bilibili_cfg = self.config.get('sources', {}).get('bilibili', {})

        if not bilibili_cfg.get('enabled', False):
            logger.info("B站下载器未启用")
            return []

        urls = bilibili_cfg.get('urls', [])
        if not urls:
            logger.warning("B站URL列表为空")
            return []

        logger.info(f"开始下载 {len(urls)} 个B站视频...")
        return self.download(urls)


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    downloader = BilibiliDownloader(config)
    results = downloader.download_from_config()

    # 保存元数据
    metadata_file = Path('data/metadata_bilibili.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 B站下载完成，共 {len(results)} 个视频")


if __name__ == "__main__":
    main()

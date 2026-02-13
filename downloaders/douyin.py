"""
抖音视频下载器
使用 yt-dlp + cookie 下载抖音声乐教学视频
"""
import json
import logging
from pathlib import Path
from typing import List, Dict
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class DouyinDownloader:
    """抖音视频下载器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path("data/raw_videos/douyin")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        douyin_cfg = config.get('sources', {}).get('douyin', {})
        self.cookie_file = douyin_cfg.get('cookie_file', './cookies/douyin.txt')

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.output_dir / '%(title)s-%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'ignoreerrors': True,
        }

        # 添加cookie（如果存在）
        if Path(self.cookie_file).exists():
            self.ydl_opts['cookiefile'] = self.cookie_file
            logger.info(f"已加载Cookie: {self.cookie_file}")
        else:
            logger.warning(f"Cookie文件不存在: {self.cookie_file}")
            logger.info("提示: 使用浏览器导出cookie到 ./cookies/douyin.txt")

    def download(self, urls: List[str]) -> List[Dict]:
        """下载抖音视频"""
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp 未安装！")
            return []

        results = []

        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            for url in urls:
                try:
                    logger.info(f"📥 下载: {url}")
                    info = ydl.extract_info(url, download=True)

                    if info:
                        results.append({
                            'source': 'douyin',
                            'url': url,
                            'title': info.get('title', 'Unknown'),
                            'duration': info.get('duration', 0),
                            'uploader': info.get('uploader', 'Unknown'),
                            'filename': ydl.prepare_filename(info),
                        })
                        logger.info(f"✅ 完成: {info.get('title')}")

                except Exception as e:
                    logger.error(f"❌ 失败: {url} - {e}")

        return results

    def download_from_config(self) -> List[Dict]:
        """从配置读取并执行"""
        douyin_cfg = self.config.get('sources', {}).get('douyin', {})

        if not douyin_cfg.get('enabled', False):
            logger.info("抖音下载器未启用")
            return []

        # 抖音目前需要手动提供URL
        logger.info("抖音下载器: 请在配置中添加视频URL")
        return []


def main():
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    downloader = DouyinDownloader(config)
    results = downloader.download_from_config()

    if results:
        with open('data/metadata_douyin.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

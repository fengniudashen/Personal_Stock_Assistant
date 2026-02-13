"""
百度贴吧爬虫 - 高音贴吧音频采集
从贴吧帖子中提取音频链接并下载
"""
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class TiebaSpider:
    """百度贴吧音频爬虫"""

    BASE_URL = "https://tieba.baidu.com"

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path("data/raw_audios/tieba")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def search_posts(self, forum: str, keywords: List[str],
                      pages: int = 10) -> List[Dict]:
        """
        搜索贴吧帖子
        
        Args:
            forum: 贴吧名（如"高音"）
            keywords: 搜索关键词
            pages: 每个关键词爬取的页数
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("requests 或 beautifulsoup4 未安装！")
            return []

        results = []

        for keyword in keywords:
            logger.info(f"🔍 搜索贴吧: [{forum}] 关键词: {keyword}")

            for page in range(pages):
                url = f"{self.BASE_URL}/f/search/res"
                params = {
                    'kw': forum,
                    'qw': keyword,
                    'pn': page * 50
                }

                try:
                    response = requests.get(
                        url, params=params,
                        headers=self.headers,
                        timeout=15
                    )

                    if response.status_code != 200:
                        logger.warning(f"  HTTP {response.status_code}")
                        continue

                    soup = BeautifulSoup(response.text, 'html.parser')
                    posts = soup.select('.s_post')

                    if not posts:
                        break

                    for post in posts:
                        title_elem = post.select_one('.p_title a')
                        if not title_elem:
                            continue

                        title = title_elem.get_text(strip=True)
                        post_url = self.BASE_URL + title_elem.get('href', '')

                        results.append({
                            'source': 'tieba',
                            'forum': forum,
                            'keyword': keyword,
                            'title': title,
                            'url': post_url,
                            'page': page
                        })

                    logger.info(f"  第{page + 1}页: 找到 {len(posts)} 个帖子")
                    time.sleep(2)  # 避免被封

                except Exception as e:
                    logger.error(f"  爬取失败: {keyword} 第{page + 1}页 - {e}")
                    time.sleep(3)

        logger.info(f"共找到 {len(results)} 个帖子")
        return results

    def extract_audio_from_post(self, post_url: str) -> List[str]:
        """从帖子中提取音频链接"""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        audio_urls = []

        try:
            response = requests.get(
                post_url, headers=self.headers, timeout=15
            )
            soup = BeautifulSoup(response.text, 'html.parser')

            # 直接音频标签
            for tag in soup.select('audio[src]'):
                audio_urls.append(tag['src'])

            # 内嵌音频链接
            for tag in soup.select('source[src]'):
                src = tag['src']
                if any(ext in src for ext in ['.mp3', '.wav', '.m4a', '.ogg']):
                    audio_urls.append(src)

            # 查找文本中的音频链接
            text = soup.get_text()

            # 网盘链接
            netdisk_patterns = [
                r'https?://pan\.baidu\.com/s/[\w-]+',
                r'https?://lanzou[a-z]?\.com/[\w]+',
                r'https?://www\.lanzou[a-z]?\.com/[\w]+',
            ]
            for pattern in netdisk_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    audio_urls.append(match)

            time.sleep(1)

        except Exception as e:
            logger.warning(f"提取音频失败: {post_url} - {e}")

        return audio_urls

    def download_audio(self, audio_url: str, filename: str) -> Optional[str]:
        """下载音频文件"""
        try:
            import requests
        except ImportError:
            return None

        try:
            response = requests.get(
                audio_url,
                headers=self.headers,
                stream=True,
                timeout=30
            )

            if response.status_code != 200:
                return None

            output_path = self.output_dir / filename

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"  ✅ 下载: {filename}")
            return str(output_path)

        except Exception as e:
            logger.error(f"  ❌ 下载失败: {audio_url} - {e}")
            return None

    def run(self) -> List[Dict]:
        """执行完整的贴吧爬取流程"""
        tieba_cfg = self.config.get('sources', {}).get('tieba', {})

        if not tieba_cfg.get('enabled', False):
            logger.info("贴吧爬虫未启用")
            return []

        forum = tieba_cfg.get('forum', '高音')
        keywords = tieba_cfg.get('keywords', ['求鉴定'])
        pages = tieba_cfg.get('pages', 5)

        # 搜索帖子
        posts = self.search_posts(forum, keywords, pages)

        # 提取并下载音频
        downloaded = []
        audio_idx = 0

        for post in posts:
            audio_urls = self.extract_audio_from_post(post['url'])

            for url in audio_urls:
                # 判断文件类型
                if any(url.endswith(ext) for ext in ['.mp3', '.wav', '.m4a', '.ogg']):
                    ext = Path(url).suffix
                else:
                    ext = '.mp3'

                filename = f"tieba_{audio_idx:05d}{ext}"
                local_path = self.download_audio(url, filename)

                if local_path:
                    downloaded.append({
                        **post,
                        'audio_url': url,
                        'local_path': local_path
                    })
                    audio_idx += 1

        return downloaded


def main():
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    spider = TiebaSpider(config)
    results = spider.run()

    with open('data/metadata_tieba.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 贴吧采集完成，共 {len(results)} 个音频")


if __name__ == "__main__":
    main()

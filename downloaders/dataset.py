"""
公开数据集下载器
下载 GTSinger、VocalSet 等公开声乐数据集
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class DatasetDownloader:
    """公开数据集下载器"""

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path("data/raw_audios/datasets")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_gtsinger(self) -> Dict:
        """下载 GTSinger 数据集"""
        logger.info("📥 GTSinger 数据集")
        logger.info("  GTSinger 需要从 GitHub 手动下载")
        logger.info("  地址: https://github.com/GTSinger/GTSinger")
        logger.info("  请将下载的数据放入: data/raw_audios/datasets/gtsinger/")

        gtsinger_dir = self.output_dir / "gtsinger"
        gtsinger_dir.mkdir(parents=True, exist_ok=True)

        return {
            'name': 'GTSinger',
            'status': 'manual_required',
            'output_dir': str(gtsinger_dir),
            'url': 'https://github.com/GTSinger/GTSinger'
        }

    def download_vocalset(self) -> Dict:
        """下载 VocalSet 数据集"""
        logger.info("📥 VocalSet 数据集")
        logger.info("  VocalSet 托管于 Zenodo")
        logger.info("  地址: https://zenodo.org/record/1203819")

        vocalset_dir = self.output_dir / "vocalset"
        vocalset_dir.mkdir(parents=True, exist_ok=True)

        # 尝试使用 wget/curl 下载
        vocalset_url = "https://zenodo.org/record/1203819/files/VocalSet11.zip"
        output_file = vocalset_dir / "VocalSet11.zip"

        if output_file.exists():
            logger.info("  已存在,跳过下载")
            return {
                'name': 'VocalSet',
                'status': 'exists',
                'output_dir': str(vocalset_dir)
            }

        try:
            # 尝试用 curl 下载
            cmd = ['curl', '-L', '-o', str(output_file), vocalset_url]
            logger.info(f"  下载中... (文件较大,请耐心等待)")
            result = subprocess.run(cmd, capture_output=True, timeout=3600)

            if result.returncode == 0 and output_file.exists():
                logger.info("  ✅ 下载完成,开始解压...")
                # 解压
                import zipfile
                with zipfile.ZipFile(str(output_file), 'r') as z:
                    z.extractall(str(vocalset_dir))
                logger.info("  ✅ 解压完成")
                return {
                    'name': 'VocalSet',
                    'status': 'completed',
                    'output_dir': str(vocalset_dir)
                }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        logger.info("  请手动下载: " + vocalset_url)
        logger.info(f"  并放入: {vocalset_dir}")
        return {
            'name': 'VocalSet',
            'status': 'manual_required',
            'output_dir': str(vocalset_dir),
            'url': vocalset_url
        }

    def run(self) -> List[Dict]:
        """下载所有配置的数据集"""
        datasets_cfg = self.config.get('sources', {}).get('datasets', [])
        results = []

        for ds in datasets_cfg:
            name = ds.get('name', '')

            if name == 'GTSinger':
                results.append(self.download_gtsinger())
            elif name == 'VocalSet':
                results.append(self.download_vocalset())
            else:
                logger.info(f"未知数据集: {name}")
                results.append({
                    'name': name,
                    'status': 'unknown',
                    'url': ds.get('url', '')
                })

        return results


def main():
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    downloader = DatasetDownloader(config)
    results = downloader.run()

    with open('data/metadata_datasets.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 数据集下载状态:")
    for r in results:
        logger.info(f"  {r['name']}: {r['status']}")


if __name__ == "__main__":
    main()

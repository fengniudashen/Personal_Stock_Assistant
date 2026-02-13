"""
Step 1: 从视频文件中提取音频轨道
使用 FFmpeg 将各种格式的视频转换为标准 WAV 音频
"""
import subprocess
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class AudioExtractor:
    """从视频中提取音频的工具类"""

    SUPPORTED_VIDEO_EXTS = {'.mp4', '.webm', '.mkv', '.flv', '.avi', '.mov', '.wmv', '.m4v'}
    SUPPORTED_AUDIO_EXTS = {'.mp3', '.m4a', '.aac', '.ogg', '.flac', '.wav', '.wma'}

    def __init__(self, config: dict):
        self.config = config
        self.sample_rate = config['audio']['sample_rate']
        self.channels = config['audio']['channels']
        self.output_dir = Path(config['paths']['audio_raw'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _check_ffmpeg(self) -> bool:
        """检查FFmpeg是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _get_media_info(self, file_path: str) -> Optional[Dict]:
        """使用ffprobe获取媒体文件信息"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.warning(f"获取媒体信息失败: {file_path} - {e}")
        return None

    def extract_audio(self, input_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        从单个视频/音频文件提取标准WAV音频
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径(可选)
            
        Returns:
            输出文件路径，失败返回None
        """
        input_path = Path(input_path)

        if not input_path.exists():
            logger.error(f"文件不存在: {input_path}")
            return None

        # 确定输出路径
        if output_path is None:
            output_path = self.output_dir / f"{input_path.stem}.wav"
        else:
            output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果已存在则跳过
        if output_path.exists():
            logger.info(f"已存在，跳过: {output_path.name}")
            return str(output_path)

        # FFmpeg 命令
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vn',                          # 不要视频流
            '-acodec', 'pcm_s16le',         # 16-bit PCM
            '-ar', str(self.sample_rate),    # 采样率
            '-ac', str(self.channels),       # 单声道
            '-y',                            # 覆盖已有文件
            str(output_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )
            if result.returncode == 0:
                logger.info(f"✅ 提取成功: {input_path.name} -> {output_path.name}")
                return str(output_path)
            else:
                logger.error(f"❌ 提取失败: {input_path.name}\n{result.stderr[:500]}")
                return None
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ 提取超时: {input_path.name}")
            return None
        except Exception as e:
            logger.error(f"❌ 异常: {input_path.name} - {e}")
            return None

    def batch_extract(self, input_dir: Optional[str] = None) -> List[Dict]:
        """
        批量从目录中提取音频
        
        Args:
            input_dir: 输入目录，默认从配置读取
            
        Returns:
            提取结果列表
        """
        if not self._check_ffmpeg():
            logger.error("FFmpeg未安装或不在PATH中！请先安装FFmpeg。")
            return []

        if input_dir is None:
            input_dir = Path(self.config['paths']['raw_videos'])
        else:
            input_dir = Path(input_dir)

        results = []

        # 递归查找所有支持的文件
        all_files = []
        for ext in self.SUPPORTED_VIDEO_EXTS | self.SUPPORTED_AUDIO_EXTS:
            all_files.extend(input_dir.rglob(f"*{ext}"))

        if not all_files:
            logger.warning(f"未找到支持的媒体文件: {input_dir}")
            return results

        logger.info(f"找到 {len(all_files)} 个媒体文件，开始提取...")

        for idx, file_path in enumerate(all_files, 1):
            logger.info(f"[{idx}/{len(all_files)}] 处理: {file_path.name}")

            # 获取媒体信息
            info = self._get_media_info(str(file_path))
            duration = 0
            if info and 'format' in info:
                duration = float(info['format'].get('duration', 0))

            # 提取音频
            output_path = self.extract_audio(str(file_path))

            result = {
                'source_path': str(file_path),
                'source_name': file_path.name,
                'output_path': output_path,
                'duration': duration,
                'success': output_path is not None,
                'source_dir': file_path.parent.name
            }
            results.append(result)

        # 汇总
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"\n📊 提取完成: {success_count}/{len(results)} 成功")

        # 保存元数据
        metadata_path = self.output_dir / 'extraction_metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"📝 元数据已保存: {metadata_path}")

        return results


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    extractor = AudioExtractor(config)
    results = extractor.batch_extract()

    total_duration = sum(r['duration'] for r in results if r['success'])
    print(f"\n🎵 总时长: {total_duration/3600:.1f} 小时")


if __name__ == "__main__":
    main()

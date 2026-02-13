"""
Step 2: 人声分离 - 使用 Demucs/UVR5 去除背景噪音和伴奏
保留纯干声(Dry Vocal)用于后续分析
"""
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class VocalSeparator:
    """人声分离器 - 支持 Demucs 和 UVR5"""

    def __init__(self, config: dict):
        self.config = config
        self.input_dir = Path(config['paths']['audio_raw'])
        self.output_dir = Path(config['paths']['audio_clean'])
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_demucs = config.get('uvr5', {}).get('use_demucs', True)
        self.demucs_model = config.get('uvr5', {}).get('demucs_model', 'htdemucs')
        self.device = config.get('uvr5', {}).get('device', 'cpu')

    def _check_demucs(self) -> bool:
        """检查 demucs 是否可用"""
        try:
            result = subprocess.run(
                ['demucs', '--help'],
                capture_output=True, text=True, timeout=10
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def separate_with_demucs(self, audio_path: str, output_dir: Optional[str] = None) -> Optional[str]:
        """
        使用 Demucs 进行人声分离
        
        Args:
            audio_path: 输入音频路径
            output_dir: 输出目录
            
        Returns:
            分离后的人声文件路径
        """
        audio_path = Path(audio_path)
        if output_dir is None:
            output_dir = self.output_dir
        else:
            output_dir = Path(output_dir)

        # 检查是否已处理
        expected_output = output_dir / self.demucs_model / audio_path.stem / 'vocals.wav'
        if expected_output.exists():
            logger.info(f"已存在，跳过: {audio_path.name}")
            return str(expected_output)

        cmd = [
            'demucs',
            '--two-stems=vocals',                # 只分离人声和伴奏
            '-n', self.demucs_model,             # 模型名
            '-o', str(output_dir),               # 输出目录
            '--device', self.device,             # 设备
            str(audio_path)
        ]

        try:
            logger.info(f"🔊 分离人声: {audio_path.name}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30分钟超时
            )

            if result.returncode == 0:
                if expected_output.exists():
                    logger.info(f"✅ 分离成功: {audio_path.name}")
                    return str(expected_output)
                else:
                    # 尝试查找输出文件
                    demucs_out = output_dir / self.demucs_model / audio_path.stem
                    vocals_files = list(demucs_out.glob('vocals.*'))
                    if vocals_files:
                        logger.info(f"✅ 分离成功: {audio_path.name}")
                        return str(vocals_files[0])
                    logger.error(f"❌ 找不到输出文件: {demucs_out}")
                    return None
            else:
                logger.error(f"❌ 分离失败: {audio_path.name}\n{result.stderr[:500]}")
                return None

        except subprocess.TimeoutExpired:
            logger.error(f"⏰ 分离超时: {audio_path.name}")
            return None
        except Exception as e:
            logger.error(f"❌ 异常: {audio_path.name} - {e}")
            return None

    def separate_simple_copy(self, audio_path: str) -> Optional[str]:
        """
        简单复制模式（无GPU时的降级方案）
        直接复制音频到输出目录，跳过人声分离
        """
        audio_path = Path(audio_path)
        output_path = self.output_dir / 'direct' / audio_path.name

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(str(audio_path), str(output_path))
            logger.info(f"📋 直接复制(跳过分离): {audio_path.name}")
            return str(output_path)
        except Exception as e:
            logger.error(f"❌ 复制失败: {audio_path.name} - {e}")
            return None

    def batch_separate(self, input_dir: Optional[str] = None) -> List[Dict]:
        """
        批量人声分离
        
        Args:
            input_dir: 输入目录
            
        Returns:
            处理结果列表
        """
        if input_dir is None:
            input_dir = self.input_dir
        else:
            input_dir = Path(input_dir)

        results = []
        audio_files = list(input_dir.glob('*.wav'))

        if not audio_files:
            logger.warning(f"未找到WAV文件: {input_dir}")
            return results

        logger.info(f"找到 {len(audio_files)} 个音频文件")

        # 检查 demucs
        has_demucs = self._check_demucs()
        if not has_demucs:
            logger.warning("⚠️ Demucs 未安装，将使用直接复制模式（不进行人声分离）")

        for idx, audio_file in enumerate(audio_files, 1):
            logger.info(f"[{idx}/{len(audio_files)}] 处理: {audio_file.name}")

            if self.use_demucs and has_demucs:
                output_path = self.separate_with_demucs(str(audio_file))
            else:
                output_path = self.separate_simple_copy(str(audio_file))

            results.append({
                'input_path': str(audio_file),
                'output_path': output_path,
                'success': output_path is not None,
                'method': 'demucs' if (self.use_demucs and has_demucs) else 'direct_copy'
            })

        # 汇总
        success_count = sum(1 for r in results if r['success'])
        logger.info(f"\n📊 人声分离完成: {success_count}/{len(results)} 成功")

        return results

    def get_clean_audio_paths(self) -> List[str]:
        """获取所有已清洗的音频文件路径"""
        paths = []

        # demucs 输出
        demucs_dir = self.output_dir / self.demucs_model
        if demucs_dir.exists():
            for vocals_file in demucs_dir.rglob('vocals.wav'):
                paths.append(str(vocals_file))

        # 直接复制的
        direct_dir = self.output_dir / 'direct'
        if direct_dir.exists():
            for wav_file in direct_dir.glob('*.wav'):
                paths.append(str(wav_file))

        return paths


def main():
    """入口函数"""
    config_path = Path(__file__).parent.parent / 'config_advanced.yaml'
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)

    separator = VocalSeparator(config)
    results = separator.batch_separate()

    clean_paths = separator.get_clean_audio_paths()
    print(f"\n🎤 已分离人声文件数: {len(clean_paths)}")


if __name__ == "__main__":
    main()

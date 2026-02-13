"""
准备 Label Studio 标注任务
从已处理的音频片段生成 Label Studio 任务 JSON
"""
import sys
import json
import logging
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def prepare_tasks(
    clips_dir: str = 'data/clips',
    labels_dir: str = 'data/labels',
    output_file: str = 'data/labelstudio_tasks.json',
    audio_base_url: str = 'http://localhost:8000/audio',
    max_tasks: int = 0
):
    """
    生成 Label Studio 导入用的任务 JSON
    
    Args:
        clips_dir: 音频片段目录
        labels_dir: 弱标签目录
        output_file: 输出的任务JSON文件
        audio_base_url: 音频文件的Base URL
        max_tasks: 最大任务数（0=不限）
    """
    clips_dir = Path(clips_dir)
    labels_dir = Path(labels_dir)

    if not clips_dir.exists():
        logger.error(f"片段目录不存在: {clips_dir}")
        return

    audio_files = sorted(clips_dir.glob('*.wav'))
    logger.info(f"发现 {len(audio_files)} 个音频文件")

    if max_tasks > 0:
        audio_files = audio_files[:max_tasks]

    # 加载弱标签缓存
    weak_labels = {}
    if labels_dir.exists():
        for json_file in labels_dir.glob('*.json'):
            try:
                with open(json_file, encoding='utf-8') as f:
                    data = json.load(f)
                weak_labels[json_file.stem] = data
            except Exception:
                pass
        logger.info(f"已加载 {len(weak_labels)} 条弱标签")

    # 生成任务
    tasks = []
    for audio_file in audio_files:
        clip_id = audio_file.stem
        wl = weak_labels.get(clip_id, {})

        ai_label = wl.get('primary_label', wl.get('suggested_label', '未知'))
        ai_confidence = wl.get('confidence', 0.0)
        cluster_id = wl.get('cluster_id', -1)
        asr_text = wl.get('asr_text', '')
        pitch_info = wl.get('pitch_info', '')
        source_name = wl.get('source', audio_file.parent.name)
        secondary = wl.get('secondary_tags', wl.get('secondary_labels', {}))
        quality = wl.get('quality_flags', [])

        # 格式化辅标签显示
        if isinstance(secondary, dict):
            sec_display = ', '.join(f'{k}({v:.0%})' for k, v in secondary.items() if v > 0.3)
        elif isinstance(secondary, list):
            sec_display = ', '.join(secondary)
        else:
            sec_display = ''
        quality_display = ', '.join(quality) if quality else ''

        task = {
            'data': {
                'audio_url': f'{audio_base_url}/{audio_file.name}',
                'ai_label': f'🤖 AI建议: {ai_label}',
                'ai_confidence': f'置信度: {ai_confidence:.1%}',
                'ai_secondary': f'🎨 辅标签: {sec_display}' if sec_display else '🎨 辅标签: (无)',
                'cluster_id': f'簇ID: {cluster_id}',
                'asr_transcript': f'📝 ASR: {asr_text}' if asr_text else '📝 ASR: (无)',
                'pitch_info': f'🎵 {pitch_info}' if pitch_info else '🎵 (待提取)',
                'acoustic_hint': f'🚩 质量: {quality_display}' if quality_display else '🚩 质量: 正常',
                'source_name': f'📁 来源: {source_name}',
            },
            'predictions': []
        }

        # 如果有弱标签，添加 prediction
        if ai_label and ai_label != '未知':
            prediction = {
                'result': [{
                    'from_name': 'primary_label',
                    'to_name': 'audio',
                    'type': 'choices',
                    'value': {'choices': [ai_label]}
                }],
                'score': ai_confidence,
                'model_version': 'weak_labels_v1'
            }

            secondary_list = []
            if isinstance(secondary, dict):
                secondary_list = [k for k, v in secondary.items() if v > 0.3]
            elif isinstance(secondary, list):
                secondary_list = secondary

            if secondary_list:
                prediction['result'].append({
                    'from_name': 'secondary_tags',
                    'to_name': 'audio',
                    'type': 'choices',
                    'value': {'choices': secondary_list}
                })

            if quality:
                prediction['result'].append({
                    'from_name': 'quality_flags',
                    'to_name': 'audio',
                    'type': 'choices',
                    'value': {'choices': quality}
                })

            task['predictions'].append(prediction)

        tasks.append(task)

    # 写入文件
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

    logger.info(f"✅ 已生成 {len(tasks)} 个标注任务: {output_file}")
    return str(output_file)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='准备 Label Studio 标注任务')
    parser.add_argument('--clips', default='data/clips')
    parser.add_argument('--labels', default='data/labels')
    parser.add_argument('--output', default='data/labelstudio_tasks.json')
    parser.add_argument('--base-url', default='http://localhost:8000/audio')
    parser.add_argument('--max-tasks', type=int, default=0)
    args = parser.parse_args()

    prepare_tasks(
        clips_dir=args.clips,
        labels_dir=args.labels,
        output_file=args.output,
        audio_base_url=args.base_url,
        max_tasks=args.max_tasks
    )

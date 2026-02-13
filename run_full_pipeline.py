"""
VibeSing 高音觉醒 - 完整 ETL 流水线编排器
顺序执行: 提取 → 分离 → 切片 → ASR → 特征 → 弱标签 → 嵌入 → 聚类 → 主动学习
"""
import sys
import time
import yaml
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'data/pipeline_{datetime.now():%Y%m%d}.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger('VibeSing.Pipeline')


class VibeSingETL:
    """
    VibeSing 完整 ETL 流水线
    
    9步流水线：
    1. 音频提取 (video → wav)
    2. 人声分离 (demucs)
    3. 智能切片 (VAD + energy)
    4. ASR标注  (whisper + keyword)
    5. 特征提取 (mel + pitch + spectral)
    6. 弱标签   (heuristic + teacher fusion)
    7. 嵌入向量 (openl3/mfcc + FAISS)
    8. 聚类     (HDBSCAN + propagation)
    9. 主动学习 (uncertainty + diversity)
    """

    def __init__(self, config_path: str = 'config_advanced.yaml'):
        with open(config_path, encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.stats = {}
        logger.info("VibeSing ETL 流水线已初始化")

    def step1_extract(self):
        """步骤1: 音频提取"""
        logger.info("=" * 50)
        logger.info("Step 1/9: 音频提取 (video → wav)")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step1_extract import AudioExtractor
        extractor = AudioExtractor(self.config)

        raw_dir = Path(self.config['paths']['raw_audio'])
        output_dir = Path(self.config['paths'].get('extracted', 'data/extracted'))
        output_dir.mkdir(parents=True, exist_ok=True)

        video_files = []
        for ext in ['*.mp4', '*.mkv', '*.webm', '*.avi', '*.flv']:
            video_files.extend(raw_dir.glob(ext))

        count = 0
        for vf in video_files:
            out = output_dir / f"{vf.stem}.wav"
            if out.exists():
                continue
            ok = extractor.extract(str(vf), str(out))
            if ok:
                count += 1

        elapsed = time.time() - t0
        self.stats['step1'] = {'extracted': count, 'total': len(video_files), 'time': elapsed}
        logger.info(f"Step 1 完成: 提取 {count}/{len(video_files)} 文件 ({elapsed:.1f}s)")

    def step2_separate(self):
        """步骤2: 人声分离"""
        logger.info("=" * 50)
        logger.info("Step 2/9: 人声分离 (demucs)")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step2_separate import VocalSeparator
        separator = VocalSeparator(self.config)

        extracted_dir = Path(self.config['paths'].get('extracted', 'data/extracted'))
        separated_dir = Path(self.config['paths']['separated'])
        separated_dir.mkdir(parents=True, exist_ok=True)

        wav_files = list(extracted_dir.glob('*.wav'))
        count = 0
        for wf in wav_files:
            out = separated_dir / wf.name
            if out.exists():
                continue
            ok = separator.separate(str(wf), str(out))
            if ok:
                count += 1

        elapsed = time.time() - t0
        self.stats['step2'] = {'separated': count, 'total': len(wav_files), 'time': elapsed}
        logger.info(f"Step 2 完成: 分离 {count}/{len(wav_files)} 文件 ({elapsed:.1f}s)")

    def step3_slice(self):
        """步骤3: 智能切片"""
        logger.info("=" * 50)
        logger.info("Step 3/9: 智能切片")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step3_slice import HybridSlicer
        slicer = HybridSlicer(self.config)

        separated_dir = Path(self.config['paths']['separated'])
        clips_dir = Path(self.config['paths']['clips'])
        clips_dir.mkdir(parents=True, exist_ok=True)

        wav_files = list(separated_dir.glob('*.wav'))
        total_clips = 0
        for wf in wav_files:
            clips = slicer.slice(str(wf), str(clips_dir))
            total_clips += len(clips) if clips else 0

        elapsed = time.time() - t0
        self.stats['step3'] = {'clips': total_clips, 'source_files': len(wav_files), 'time': elapsed}
        logger.info(f"Step 3 完成: 生成 {total_clips} 个片段 ({elapsed:.1f}s)")

    def step4_asr(self):
        """步骤4: ASR标注"""
        logger.info("=" * 50)
        logger.info("Step 4/9: ASR + 关键词标注")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step4_asr import ASRAnnotator
        annotator = ASRAnnotator(self.config)

        clips_dir = Path(self.config['paths']['clips'])
        labels_dir = Path(self.config['paths']['labels'])
        labels_dir.mkdir(parents=True, exist_ok=True)

        clips = list(clips_dir.glob('*.wav'))
        count = 0
        for clip in clips:
            result = annotator.annotate(str(clip))
            if result:
                out = labels_dir / f"{clip.stem}_asr.json"
                with open(out, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                count += 1

        elapsed = time.time() - t0
        self.stats['step4'] = {'annotated': count, 'total': len(clips), 'time': elapsed}
        logger.info(f"Step 4 完成: ASR标注 {count}/{len(clips)} ({elapsed:.1f}s)")

    def step5_features(self):
        """步骤5: 特征提取"""
        logger.info("=" * 50)
        logger.info("Step 5/9: 声学特征提取")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step5_features import FeatureExtractor
        extractor = FeatureExtractor(self.config)

        clips_dir = Path(self.config['paths']['clips'])
        features_dir = Path(self.config['paths'].get('features', 'data/features'))
        features_dir.mkdir(parents=True, exist_ok=True)

        clips = list(clips_dir.glob('*.wav'))
        count = 0
        for clip in clips:
            try:
                features = extractor.extract(str(clip))
                if features:
                    out = features_dir / f"{clip.stem}.json"
                    # 转换numpy为可序列化类型
                    serializable = {}
                    for k, v in features.items():
                        import numpy as np
                        if isinstance(v, np.ndarray):
                            serializable[k] = v.tolist()
                        elif isinstance(v, (np.float32, np.float64)):
                            serializable[k] = float(v)
                        else:
                            serializable[k] = v

                    with open(out, 'w', encoding='utf-8') as f:
                        json.dump(serializable, f, indent=2)
                    count += 1
            except Exception as e:
                logger.warning(f"特征提取失败: {clip.name} - {e}")

        elapsed = time.time() - t0
        self.stats['step5'] = {'extracted': count, 'total': len(clips), 'time': elapsed}
        logger.info(f"Step 5 完成: 特征提取 {count}/{len(clips)} ({elapsed:.1f}s)")

    def step6_weak_labels(self):
        """步骤6: 弱标签融合"""
        logger.info("=" * 50)
        logger.info("Step 6/9: 弱标签生成 + 融合")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step6_weak_labels import HeuristicClassifier

        clips_dir = Path(self.config['paths']['clips'])
        features_dir = Path(self.config['paths'].get('features', 'data/features'))
        labels_dir = Path(self.config['paths']['labels'])

        classifier = HeuristicClassifier(self.config)
        clips = list(clips_dir.glob('*.wav'))
        count = 0

        for clip in clips:
            feat_file = features_dir / f"{clip.stem}.json"
            if not feat_file.exists():
                continue

            with open(feat_file, encoding='utf-8') as f:
                features = json.load(f)

            result = classifier.classify(features)
            if result:
                out = labels_dir / f"{clip.stem}.json"
                with open(out, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                count += 1

        elapsed = time.time() - t0
        self.stats['step6'] = {'labeled': count, 'total': len(clips), 'time': elapsed}
        logger.info(f"Step 6 完成: 弱标签 {count}/{len(clips)} ({elapsed:.1f}s)")

    def step7_embedding(self):
        """步骤7: 嵌入向量提取"""
        logger.info("=" * 50)
        logger.info("Step 7/9: 嵌入向量 + FAISS索引")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step7_embedding import EmbeddingExtractor
        extractor = EmbeddingExtractor(self.config)

        clips_dir = Path(self.config['paths']['clips'])
        clips = list(clips_dir.glob('*.wav'))

        embeddings, ids = extractor.extract_batch(clips)
        if embeddings is not None and len(embeddings) > 0:
            extractor.build_index(embeddings, ids)

        elapsed = time.time() - t0
        self.stats['step7'] = {'embedded': len(ids) if ids else 0, 'time': elapsed}
        logger.info(f"Step 7 完成: 嵌入 {len(ids) if ids else 0} 个向量 ({elapsed:.1f}s)")

    def step8_clustering(self):
        """步骤8: 聚类分析"""
        logger.info("=" * 50)
        logger.info("Step 8/9: 聚类 + 标签传播")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step8_clustering import AudioClusterer
        clusterer = AudioClusterer(self.config)

        embeddings_dir = Path(self.config['paths'].get('embeddings', 'data/embeddings'))
        import numpy as np
        emb_file = embeddings_dir / 'embeddings.npy'
        ids_file = embeddings_dir / 'ids.json'

        if emb_file.exists() and ids_file.exists():
            embeddings = np.load(str(emb_file))
            with open(ids_file, encoding='utf-8') as f:
                ids = json.load(f)
            cluster_labels = clusterer.cluster(embeddings, ids)
            self.stats['step8'] = {
                'clusters': len(set(cluster_labels)) if cluster_labels else 0,
                'samples': len(ids),
                'time': time.time() - t0,
            }
        else:
            logger.warning("嵌入文件不存在，跳过聚类")
            self.stats['step8'] = {'clusters': 0, 'samples': 0, 'time': 0}

        elapsed = time.time() - t0
        logger.info(f"Step 8 完成 ({elapsed:.1f}s)")

    def step9_active_learning(self):
        """步骤9: 主动学习采样"""
        logger.info("=" * 50)
        logger.info("Step 9/9: 主动学习采样")
        logger.info("=" * 50)
        t0 = time.time()

        from pipeline.step9_active_learning import ActiveLearningScheduler
        scheduler = ActiveLearningScheduler(self.config)

        labels_dir = Path(self.config['paths']['labels'])
        queue = scheduler.generate_queue(str(labels_dir))

        elapsed = time.time() - t0
        self.stats['step9'] = {'queue_size': len(queue) if queue else 0, 'time': elapsed}
        logger.info(f"Step 9 完成: 生成 {len(queue) if queue else 0} 条待标注 ({elapsed:.1f}s)")

    def run_all(self, start_step: int = 1, end_step: int = 9):
        """运行完整流水线"""
        total_start = time.time()

        logger.info("🚀 VibeSing 高音觉醒 - ETL 流水线启动")
        logger.info(f"   步骤范围: Step {start_step} → Step {end_step}")
        logger.info("=" * 60)

        steps = {
            1: self.step1_extract,
            2: self.step2_separate,
            3: self.step3_slice,
            4: self.step4_asr,
            5: self.step5_features,
            6: self.step6_weak_labels,
            7: self.step7_embedding,
            8: self.step8_clustering,
            9: self.step9_active_learning,
        }

        for step_num in range(start_step, end_step + 1):
            if step_num in steps:
                try:
                    steps[step_num]()
                except Exception as e:
                    logger.error(f"Step {step_num} 失败: {e}")
                    import traceback
                    traceback.print_exc()
                    # 继续下一步
                    continue

        total_time = time.time() - total_start

        # 输出摘要
        logger.info("\n" + "=" * 60)
        logger.info("📊 流水线执行摘要")
        logger.info("=" * 60)
        for step_name, stats in self.stats.items():
            logger.info(f"  {step_name}: {stats}")
        logger.info(f"  总耗时: {total_time:.1f}s ({total_time / 60:.1f}min)")
        logger.info("=" * 60)

        # 保存统计
        stats_file = Path('data') / f'pipeline_stats_{datetime.now():%Y%m%d_%H%M%S}.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, default=str)
        logger.info(f"统计已保存: {stats_file}")


def main():
    parser = argparse.ArgumentParser(description='VibeSing 完整 ETL 流水线')
    parser.add_argument('--config', default='config_advanced.yaml', help='配置文件路径')
    parser.add_argument('--start', type=int, default=1, help='起始步骤 (1-9)')
    parser.add_argument('--end', type=int, default=9, help='结束步骤 (1-9)')
    parser.add_argument('--step', type=int, default=0, help='仅运行指定步骤')
    args = parser.parse_args()

    etl = VibeSingETL(args.config)

    if args.step > 0:
        etl.run_all(start_step=args.step, end_step=args.step)
    else:
        etl.run_all(start_step=args.start, end_step=args.end)


if __name__ == '__main__':
    main()

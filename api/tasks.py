"""
VibeSing Celery 异步任务
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入Celery，如果不可用则提供占位符
try:
    from celery import Celery

    celery_app = Celery(
        'vibesing',
        broker='redis://localhost:6379/0',
        backend='redis://localhost:6379/1'
    )

    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1小时超时
    )

    @celery_app.task(bind=True, name='vibesing.run_pipeline_step')
    def run_pipeline_step(self, step_name: str, config_path: str = 'config_advanced.yaml'):
        """异步执行管道步骤"""
        import yaml
        import subprocess

        self.update_state(state='PROGRESS', meta={'step': step_name, 'progress': 0})

        step_modules = {
            'extract': 'pipeline.step1_extract',
            'separate': 'pipeline.step2_separate',
            'slice': 'pipeline.step3_slice',
            'asr': 'pipeline.step4_asr',
            'features': 'pipeline.step5_features',
            'weak_labels': 'pipeline.step6_weak_labels',
            'embedding': 'pipeline.step7_embedding',
            'clustering': 'pipeline.step8_clustering',
            'active_learning': 'pipeline.step9_active_learning',
        }

        module = step_modules.get(step_name)
        if not module:
            return {'status': 'error', 'message': f'Unknown step: {step_name}'}

        try:
            result = subprocess.run(
                ['py', '-m', module],
                capture_output=True, text=True, timeout=3600
            )

            return {
                'status': 'completed' if result.returncode == 0 else 'failed',
                'step': step_name,
                'stdout': result.stdout[-2000:],  # 截断
                'stderr': result.stderr[-2000:] if result.returncode != 0 else '',
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @celery_app.task(name='vibesing.run_full_pipeline')
    def run_full_pipeline(config_path: str = 'config_advanced.yaml'):
        """运行完整管道"""
        steps = [
            'extract', 'separate', 'slice', 'asr',
            'features', 'weak_labels', 'embedding',
            'clustering', 'active_learning'
        ]
        results = []
        for step in steps:
            result = run_pipeline_step(step, config_path)
            results.append(result)
            if result['status'] != 'completed':
                break
        return results

except ImportError:
    logger.warning("Celery 未安装，异步任务不可用")
    celery_app = None

    def run_pipeline_step(step_name, config_path='config_advanced.yaml'):
        logger.error("Celery 未安装，无法执行异步任务")
        return None

    def run_full_pipeline(config_path='config_advanced.yaml'):
        logger.error("Celery 未安装，无法执行异步任务")
        return None

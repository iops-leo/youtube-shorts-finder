from celery import Celery
import os
import json
import hashlib
import time

from common_utils.search import get_recent_popular_shorts
from common_utils.search import get_cache_key

# Redis 설정
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery = Celery('celery_worker', broker=redis_url, backend=redis_url)

# 성능 최적화 설정
celery.conf.update(
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=300,
    worker_concurrency=4
)

@celery.task(name='celery_worker.run_search_task')
def run_search_task(params):
    """실제 검색 로직을 Celery 작업자에서 실행합니다"""
    # 검색 수행
    results = get_recent_popular_shorts(**params)
    return results
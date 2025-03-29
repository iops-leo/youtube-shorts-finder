from celery import Celery
import os
import json
import hashlib
import time

# Redis 설정
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery = Celery('app', broker=redis_url, backend=redis_url)

# 성능 최적화 설정
celery.conf.update(
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=300,
    worker_concurrency=4
)

# 캐시 관련 함수 (core/search.py에서 가져옴)
def get_cache_key(params):
    """파라미터로부터 캐시 키 생성"""
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

@celery.task
def run_search_task(params):
    """
    이 함수는 app.py에서 get_recent_popular_shorts 함수를 호출하는 대신,
    단순히 매개변수만 반환합니다.
    실제 앱에서는 이 매개변수들이 API 호출을 통해 처리됩니다.
    """
    # 여기서 params만 반환하고, 실제 검색은 app.py에서 수행합니다
    return params
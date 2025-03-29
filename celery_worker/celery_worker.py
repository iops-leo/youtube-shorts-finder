# celery_worker/celery_worker.py
from celery import Celery
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# core 모듈에서 함수 임포트
from core.search import (
    get_recent_popular_shorts, get_cache_key, save_to_cache
)

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery = Celery('app', broker=redis_url, backend=redis_url)

# 워커 설정 최적화 (선택사항)
celery.conf.update(
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=300,
    worker_concurrency=4  # Railway에서는 이 값을 낮추는 것이 좋습니다
)

@celery.task
def run_search_task(params):
    # 캐시는 각 작업마다 새로 생성하거나 글로벌 변수로 관리
    cache = {}
    
    # 공통 모듈 사용
    cache_key = get_cache_key(params)
    results = get_recent_popular_shorts(**params)
    save_to_cache(cache, cache_key, results)
    
    return results
# celery_worker.py
from celery import Celery
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
celery = Celery('app', broker=redis_url, backend=redis_url)

@celery.task
def run_search_task(params):
    from flask_app.app import get_recent_popular_shorts, get_cache_key, save_to_cache
    cache_key = get_cache_key(params)
    results = get_recent_popular_shorts(**params)
    save_to_cache(cache_key, results)
    return results
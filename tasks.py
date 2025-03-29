# tasks.py
from flask_app.app import celery
from flask_app.app import get_recent_popular_shorts

@celery.task()
def run_search_task(params):
    print("📦 비동기 작업 실행 중 (Celery)")
    results = get_recent_popular_shorts(**params)
    return results
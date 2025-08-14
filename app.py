import os
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import googleapiclient.discovery
import pytz
import isodate
import json
from functools import lru_cache, wraps
import time
import hashlib
import re
import math
from deep_translator import GoogleTranslator
import uuid
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import logging
from logging.handlers import RotatingFileHandler
import requests
from werkzeug.middleware.proxy_fix import ProxyFix
from concurrent.futures import ThreadPoolExecutor
from pytube import YouTube
import speech_recognition as sr
import moviepy.editor as mp
import tempfile
from services.email_service import EmailService
from services.notification_scheduler import NotificationScheduler
from youtube_management import register_youtube_routes
import fcntl
from config.security import SecurityConfig, validate_required_environment, setup_secure_logging
from sqlalchemy import text


# 공통 기능 임포트
from common_utils.search import get_recent_popular_shorts, get_cache_key, save_to_cache, get_from_cache
from common_utils.search import api_keys, switch_to_next_api_key, get_youtube_api_service, get_cache_stats, get_api_key_info
from common_utils.user_search import UserSearchService
from common_utils.quota_manager import get_quota_manager
from common_utils.quota_monitoring import get_quota_monitor, initialize_quota_monitor
from models import db, EmailNotification, NotificationSearch, User, ChannelCategory, Channel, CategoryChannel, SearchPreference, SearchHistory, ApiLog, SavedVideo, UserApiKey, ApiKeyUsage, ApiKeyRotation
from services.user_api_service import UserApiKeyManager

cache = {}
CACHE_TIMEOUT = 28800  # 캐시 유효시간 (초)

# 보안 설정 초기화
setup_secure_logging()  # 보안 로깅 필터 적용
validate_required_environment()  # 필수 환경변수 검증

if os.environ.get('FLASK_ENV') == 'production':
    # 운영 환경 설정
    # 환경변수는 클라우드 서비스에서 설정됨
    pass  # 필요한 경우 여기에 운영 환경 특정 코드 추가
else:
    # 개발 환경 설정
    from dotenv import load_dotenv
    load_dotenv()  # .env 파일에서 환경변수 로드

# 스레드풀 생성
executor = ThreadPoolExecutor(max_workers=10)


app = Flask(__name__)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'pool_pre_ping': True
}
mail = Mail(app)


app.config.update(
    MAIL_SERVER=os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
    MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
)

# SECRET_KEY 보안 설정 - 기본값 제거로 보안 강화
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("❌ 보안 오류: SECRET_KEY 환경변수가 설정되지 않았습니다. SECRET_KEY는 필수입니다.")
app.secret_key = SECRET_KEY

# 보안 헤더 적용
SecurityConfig.apply_security_headers(app)
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID', '')  # Google OAuth 클라이언트 ID
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET', '')  # Google OAuth 클라이언트 시크릿
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# PostgreSQL 연결 설정
# Railway는 DATABASE_URL 환경 변수를 자동으로 제공합니다
db_url = os.environ.get('DATABASE_URL', '')
# Heroku 호환성을 위해 'postgres://'를 'postgresql://'로 변경
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# 로그 설정
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10485760, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('애플리케이션 시작')

# 할당량 모니터링 시스템 초기화
initialize_quota_monitor(app.config)

# 로그인 매니저 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 정적 파일 경로 설정
app.static_folder = 'static'

with app.app_context():
    db.create_all()
    app.logger.info('데이터베이스 테이블 생성 완료')
    
    # 자동 마이그레이션 실행
    try:
        from auto_migrate import safe_migrate
        safe_migrate(app, db)
    except Exception as e:
        app.logger.warning(f'자동 마이그레이션 실패: {str(e)}')
    
# YouTube 관리 라우트 등록
register_youtube_routes(app)

# 사용자 로딩 콜백
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

# OAuth 클라이언트 설정 부분 수정
def get_google_flow():
    # 로컬 개발 환경인지 확인
    is_local_dev = os.environ.get('FLASK_ENV') == 'dev'
    
    # 리디렉션 URI 목록에 로컬과 운영 모두 포함
    redirect_uris = ["https://shorts.ddns.net/login/callback"]
    
    # 로컬 개발 환경이면 로컬 URI도 추가 (보안 강화)
    if is_local_dev:
        port = os.environ.get('PORT', '8080')
        # 보안: 개발 환경에서만 INSECURE_TRANSPORT 허용
        if os.environ.get('FLASK_ENV') in ['dev', 'development']:
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            print("⚠️ 개발 환경: OAUTHLIB_INSECURE_TRANSPORT 활성화")
        redirect_uris.append(f"http://localhost:{port}/login/callback")
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": app.config['GOOGLE_CLIENT_ID'],
                "client_secret": app.config['GOOGLE_CLIENT_SECRET'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": redirect_uris
            }
        },
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile"
        ]
    )
    return flow


# 로그인 페이지
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    flow = get_google_flow()
    # 환경에 따라 리디렉션 URI 설정
    is_local_dev = os.environ.get('FLASK_ENV') in ['dev', 'development']
    if is_local_dev:
        flow.redirect_uri = f"http://localhost:{os.environ.get('PORT', '8080')}/login/callback"
    else:
        flow.redirect_uri = "https://shorts.ddns.net/login/callback"
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state
    return render_template('login.html', auth_url=authorization_url)

# 로그인 콜백 처리
@app.route('/login/callback')
def login_callback():
    if 'state' not in session:
        return redirect(url_for('login'))
    
    flow = get_google_flow()
    # 환경에 따라 리디렉션 URI 설정
    is_local_dev = os.environ.get('FLASK_ENV') in ['dev', 'development']
    if is_local_dev:
        flow.redirect_uri = f"http://localhost:{os.environ.get('PORT', '8080')}/login/callback"
    else:
        flow.redirect_uri = "https://shorts.ddns.net/login/callback"
        
    flow.fetch_token(authorization_response=request.url)
    
    credentials = flow.credentials
    request_session = requests.session()
    token_request = google.auth.transport.requests.Request(session=request_session)
    
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,
        request=token_request,
        audience=app.config['GOOGLE_CLIENT_ID']
    )
    
    # 사용자 정보 가져오기
    user_id = id_info['sub']
    email = id_info['email']
    name = id_info.get('name', 'Unknown')
    picture = id_info.get('picture', '').split(';')[0]
    
    # 데이터베이스에서 사용자 확인 또는 생성
    user = User.query.get(user_id)
    
    if user:
        # 기존 사용자 업데이트
        user.last_login = datetime.utcnow()
        user.name = name
        user.picture = picture
        user_role = user.role
    else:
        # 새 사용자 추가 (기본적으로 pending 상태)
        user = User(
            id=user_id,
            email=email,
            name=name,
            picture=picture,
            role='pending',
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        db.session.add(user)
        user_role = 'pending'
        app.logger.info(f'새 사용자 등록: {email}')
    
    db.session.commit()
    
    # 사용자 로그인
    login_user(user)
    
    app.logger.info(f'사용자 로그인: {email}')
    
    # pending 상태인 경우 대기 페이지로 리디렉션
    if user_role == 'pending':
        flash('계정이 승인 대기 중입니다. 관리자의 승인이 필요합니다.', 'warning')
        return redirect(url_for('pending'))
    
    # 원래 접근하려던 페이지가 있으면 해당 페이지로, 없으면 인덱스로 리디렉션
    next_page = session.get('next', url_for('index'))
    session.pop('next', None)
    return redirect(next_page)

# 로그아웃
@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        app.logger.info(f'사용자 로그아웃: {current_user.email}')
    logout_user()
    return redirect(url_for('index'))

# 승인 대기 페이지
@app.route('/pending')
@login_required
def pending():
    if current_user.is_approved():
        return redirect(url_for('dashboard'))
    return render_template('pending.html')

# 관리자 페이지 - 사용자 관리
@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin():
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.order_by(User.created_at.desc()).all()
    
    users_list = []
    for user in users:
        user_dict = {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'picture': user.picture,
            'role': user.role,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'api_calls': user.api_calls
        }
        users_list.append(user_dict)

    # 오늘 API 호출 수 계산 (관리자 계정 기준 또는 전체 합산도 가능)
    today = datetime.utcnow().date()
    daily_api_calls = ApiLog.query.filter(
        ApiLog.user_id == current_user.id,
        db.func.date(ApiLog.timestamp) == today
    ).count()

    return render_template('admin_users.html', users=users_list, daily_api_calls=daily_api_calls)

# 사용자 승인/거부
@app.route('/admin/users/<user_id>/approve', methods=['POST'])
@login_required
def approve_user(user_id):
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    action = request.form.get('action')
    if action not in ['approve', 'reject', 'make_admin', 'remove_admin']:
        return jsonify({"status": "error", "message": "유효하지 않은 작업입니다."})
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "사용자를 찾을 수 없습니다."})
    
    if action == 'approve':
        user.role = 'approved'
        message = "사용자가 승인되었습니다."
    elif action == 'reject':
        db.session.delete(user)
        message = "사용자가 거부되었습니다."
    elif action == 'make_admin':
        user.role = 'admin'
        message = "사용자가 관리자로 설정되었습니다."
    else:  # remove_admin
        user.role = 'approved'
        message = "관리자 권한이 제거되었습니다."
    
    db.session.commit()
    
    app.logger.info(f'관리자 {current_user.email}가 사용자 {user_id}에 대해 {action} 작업 수행')
    
    return jsonify({"status": "success", "message": message})

# API 호출 로깅 함수 - 보안 강화
def log_api_call(endpoint, params=None):
    if current_user.is_authenticated:
        # 보안: 파라미터에서 민감한 정보 마스킹
        safe_params = SecurityConfig.safe_log_params(params) if params else None
        
        # API 호출 로그 저장
        api_log = ApiLog(
            user_id=current_user.id,
            endpoint=endpoint,
            params=json.dumps(safe_params) if safe_params else None
        )
        db.session.add(api_log)
        
        # 사용자의 API 호출 횟수 증가
        current_user.api_calls += 1
        db.session.commit()
        
        app.logger.info(f'🔍 API 호출: {endpoint} by {current_user.email}')

# API 호출 제한 함수
def check_api_limits():
    if current_user.is_authenticated:
        # 관리자는 제한 없음
        if current_user.is_admin():
            return True
        
        # 승인된 사용자는 일일 호출 제한 (예: 100회)
        if current_user.is_approved():
            # 오늘 API 호출 횟수 확인
            today = datetime.utcnow().date()
            daily_calls = ApiLog.query.filter(
                ApiLog.user_id == current_user.id,
                db.func.date(ApiLog.timestamp) == today
            ).count()
            
            if daily_calls >= 100:  # 일일 API 호출 제한
                return False
        
        return True
    
    return False  # 비인증 사용자는 제한

# API 접근 권한 검사 래퍼 함수
def api_login_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_approved():
            return jsonify({"status": "error", "message": "승인된 사용자만 API에 접근할 수 있습니다."})
        if not check_api_limits():
            return jsonify({"status": "error", "message": "일일 API 호출 제한에 도달했습니다."})
        return f(*args, **kwargs)
    return decorated_function

# 메인 페이지에 로그인 상태 반영
@app.route('/')
def index():
    # 로그인하지 않았거나 승인되지 않은 사용자는 로그인 페이지로 리디렉션
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    if not current_user.is_approved():
        return redirect(url_for('pending'))
    
    # 대시보드를 기본 홈페이지로 설정
    # 검색 페이지로 이동하려면 /?page=search 파라미터 사용
    if request.args.get('page') != 'search':
        return redirect(url_for('dashboard'))
    
    # 오늘 API 호출 횟수 계산
    today = datetime.utcnow().date()
    daily_api_calls = ApiLog.query.filter(
        ApiLog.user_id == current_user.id,
        db.func.date(ApiLog.timestamp) == today
    ).count()
    
    # 기존 index 함수 로직 유지 (카테고리, 국가, 언어 리스트 등)
    categories = [
        {"id": "any", "name": "모든 카테고리"},
        {"id": "1", "name": "영화 & 애니메이션"},
        {"id": "2", "name": "자동차 & 차량"},
        {"id": "10", "name": "음악"},
        {"id": "15", "name": "애완동물 & 동물"},
        {"id": "17", "name": "스포츠"},
        {"id": "20", "name": "게임"},
        {"id": "22", "name": "인물 & 블로그"},
        {"id": "23", "name": "코미디"},
        {"id": "24", "name": "엔터테인먼트"},
        {"id": "25", "name": "뉴스 & 정치"},
        {"id": "26", "name": "노하우 & 스타일"},
        {"id": "27", "name": "교육"},
        {"id": "28", "name": "과학 & 기술"}
    ]
    regions = [
        {"code": "all", "name": "모든 국가"},
        {"code": "KR", "name": "대한민국"},
        {"code": "US", "name": "미국"},
        {"code": "JP", "name": "일본"},
        {"code": "GB", "name": "영국"},
        {"code": "FR", "name": "프랑스"},
        {"code": "DE", "name": "독일"},
        {"code": "CA", "name": "캐나다"},
        {"code": "AU", "name": "호주"},
        {"code": "CN", "name": "중국"}
    ]
    languages = [
        {"code": "any", "name": "모든 언어"},
        {"code": "ko", "name": "한국어"},
        {"code": "en", "name": "영어"},
        {"code": "ja", "name": "일본어"},
        {"code": "zh", "name": "중국어"},
        {"code": "es", "name": "스페인어"},
        {"code": "fr", "name": "프랑스어"},
        {"code": "de", "name": "독일어"}
    ]

    # 기본값 설정
    selected_region = request.args.get('region', 'KR')
    selected_language = request.args.get('language', 'ko')

    return render_template('index.html', 
                          categories=categories, 
                          regions=regions, 
                          languages=languages,
                          selected_region=selected_region, 
                          selected_language=selected_language,
                          daily_api_calls=daily_api_calls)

# 관리자 대시보드 - API 사용 통계
@app.route('/admin/cache-stats')
@login_required
def admin_cache_stats():
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    # 캐시 통계 수집
    cache_stats = get_cache_stats()
    
    # API 키 상태
    api_key_info = get_api_key_info()
    
    return jsonify({
        "status": "success",
        "cache_stats": cache_stats,
        "api_key_info": api_key_info
    })

@app.route('/admin/stats')
@login_required
def admin_stats():
    if not current_user.is_admin():
        flash('관리자 권한이 필요합니다.', 'danger')
        return redirect(url_for('index'))
    
    # 일별 API 호출 통계
    daily_stats = db.session.query(
        db.func.date(ApiLog.timestamp).label('date'),
        db.func.count().label('count')
    ).group_by(db.func.date(ApiLog.timestamp)).order_by(db.func.date(ApiLog.timestamp).desc()).limit(30).all()
    
    # 사용자별 API 호출 통계
    user_stats = db.session.query(
        User.email,
        db.func.count(ApiLog.id).label('call_count')
    ).join(ApiLog, User.id == ApiLog.user_id).group_by(User.id).order_by(db.func.count(ApiLog.id).desc()).limit(20).all()
    
    # 엔드포인트별 API 호출 통계
    endpoint_stats = db.session.query(
        ApiLog.endpoint,
        db.func.count().label('count')
    ).group_by(ApiLog.endpoint).order_by(db.func.count().desc()).all()
    
    return render_template('admin_stats.html', 
                         daily_stats=daily_stats,
                         user_stats=user_stats,
                         endpoint_stats=endpoint_stats)

# ===================== YouTube API 할당량 관리 API =====================

@app.route('/admin/quota/status')
@login_required
def admin_quota_status():
    """관리자용 할당량 현황 API"""
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    try:
        quota_manager = get_quota_manager()
        quota_monitor = get_quota_monitor()
        
        if not quota_manager:
            return jsonify({"status": "error", "message": "할당량 관리자가 초기화되지 않았습니다."})
        
        # 현재 할당량 상태
        quota_status = quota_manager.get_quota_status()
        
        # 사용량 통계 (최근 24시간)
        usage_stats = quota_manager.get_usage_statistics(hours=24)
        
        # 최근 알림 정보
        alerts_summary = quota_monitor.get_alerts_summary(hours=24) if quota_monitor else {}
        
        # 응답 데이터 구성
        response_data = {
            "status": "success",
            "quota_status": quota_status,
            "usage_stats": usage_stats,
            "alerts_summary": alerts_summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"할당량 상태 조회 오류: {str(e)}")
        return jsonify({"status": "error", "message": "할당량 상태를 조회할 수 없습니다."})

@app.route('/admin/quota/usage/<int:hours>')
@login_required  
def admin_quota_usage(hours):
    """관리자용 할당량 사용량 통계 API"""
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    try:
        quota_manager = get_quota_manager()
        if not quota_manager:
            return jsonify({"status": "error", "message": "할당량 관리자가 초기화되지 않았습니다."})
        
        # 시간 범위 제한 (최대 7일)
        hours = min(hours, 168)
        
        usage_stats = quota_manager.get_usage_statistics(hours=hours)
        
        return jsonify({
            "status": "success",
            "usage_stats": usage_stats,
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"할당량 사용량 조회 오류: {str(e)}")
        return jsonify({"status": "error", "message": "사용량 통계를 조회할 수 없습니다."})

@app.route('/admin/quota/alerts')
@login_required
def admin_quota_alerts():
    """관리자용 할당량 알림 내역 API"""
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    try:
        quota_monitor = get_quota_monitor()
        if not quota_monitor:
            return jsonify({"status": "error", "message": "할당량 모니터가 초기화되지 않았습니다."})
        
        hours = request.args.get('hours', 24, type=int)
        hours = min(hours, 168)  # 최대 7일
        
        alerts_summary = quota_monitor.get_alerts_summary(hours=hours)
        
        return jsonify({
            "status": "success",
            "alerts_summary": alerts_summary,
            "period_hours": hours,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"할당량 알림 조회 오류: {str(e)}")
        return jsonify({"status": "error", "message": "알림 내역을 조회할 수 없습니다."})

@app.route('/admin/quota/check', methods=['POST'])
@login_required
def admin_quota_check():
    """관리자용 할당량 상태 수동 체크 API"""
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    try:
        quota_manager = get_quota_manager()
        quota_monitor = get_quota_monitor()
        
        if not quota_manager or not quota_monitor:
            return jsonify({"status": "error", "message": "할당량 시스템이 초기화되지 않았습니다."})
        
        # 할당량 상태 수동 체크
        quota_monitor.check_quota_status(quota_manager)
        
        app.logger.info(f"관리자 {current_user.email}가 할당량 상태를 수동으로 체크했습니다.")
        
        return jsonify({
            "status": "success",
            "message": "할당량 상태 체크가 완료되었습니다.",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"할당량 수동 체크 오류: {str(e)}")
        return jsonify({"status": "error", "message": "할당량 체크 중 오류가 발생했습니다."})

@app.route('/api/quota/info')
@login_required
def api_quota_info():
    """사용자용 할당량 정보 API (간단한 정보만)"""
    try:
        quota_manager = get_quota_manager()
        if not quota_manager:
            return jsonify({"status": "error", "message": "할당량 정보를 조회할 수 없습니다."})
        
        quota_status = quota_manager.get_quota_status()
        
        # 사용자에게는 전체적인 상태만 제공
        user_info = {
            "total_keys": quota_status['total_keys'],
            "overall_status": "normal",  # 기본값
            "message": "API 서비스가 정상 작동 중입니다."
        }
        
        # 모든 키가 경고 수준 이상인지 확인
        warning_keys = sum(1 for key_status in quota_status['keys_status'] 
                          if key_status['usage_percentage'] >= 90)
        exceeded_keys = sum(1 for key_status in quota_status['keys_status'] 
                           if key_status['is_exceeded'])
        
        if exceeded_keys > 0:
            user_info['overall_status'] = "limited"
            user_info['message'] = "일부 API 서비스에 제한이 있을 수 있습니다. 잠시 후 다시 시도해주세요."
        elif warning_keys >= len(quota_status['keys_status']) // 2:
            user_info['overall_status'] = "warning" 
            user_info['message'] = "API 사용량이 증가했습니다. 서비스 속도가 일시적으로 느려질 수 있습니다."
        
        return jsonify({
            "status": "success",
            "quota_info": user_info,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"사용자 할당량 정보 조회 오류: {str(e)}")
        return jsonify({"status": "error", "message": "할당량 정보를 조회할 수 없습니다."})

# ===================== 할당량 관리 API 끝 =====================

# 정적 파일 경로 설정
app.static_folder = 'static'

@app.route("/search", methods=["POST"])
@api_login_required
def search():
    try:
        data = request.form
        
        # 파라미터 파싱 및 제한 적용
        params = {
            'min_views': max(100000, int(data.get('min_views', '100000'))),  # 최소 10만 조회수
            'days_ago': min(5, max(1, int(data.get('days_ago', 5)))),  # 최대 5일, 최소 1일
            'max_results': min(20, max(1, int(data.get('max_results', 20)))),  # 최대 20개
            'category_id': data.get('category_id') if data.get('category_id') != 'any' else None,
            'region_code': data.get('region_code'),
            'language': data.get('language') if data.get('language') != 'any' else None,
            'keyword': data.get('keyword'),
            'channel_ids': data.get('channel_ids') or None
        }

        
        # API 호출 로깅
        log_api_call('search', params)

        # 캐시 체크
        cache_key = get_cache_key(params)
        cached_results = get_from_cache(cache_key)
        if cached_results:
            return jsonify({"status": "success", "results": cached_results, "fromCache": True})

        # 비동기 작업 시작
        future = executor.submit(get_recent_popular_shorts, **params)
        results = future.result(timeout=30)  # 최대 30초 대기
        
        # 결과 캐싱
        save_to_cache(cache_key, results)
        
        return jsonify({
            "status": "success",
            "results": results,
            "count": len(results), 
            "fromCache": False
        })
    except Exception as e:
        error_message = str(e)
        print(f"오류 발생: {e}")
        
        # YouTube API 할당량 초과 오류 처리 (국문/영문 모두 인식)
        lower_msg = error_message.lower()
        if ("모든" in error_message and ("할당량" in error_message or "api 키" in error_message)) or \
           ("quota" in lower_msg and ("exceeded" in lower_msg or "daily" in lower_msg)) or \
           ("api key not valid" in lower_msg or "forbidden" in lower_msg or "invalid" in lower_msg):
            return jsonify({
                "status": "quota_exceeded",
                "message": "모든 YouTube API 키의 할당량이 초과되었거나 사용이 제한되었습니다.",
                "user_message": "YouTube API 일일 할당량이 소진되었거나 일시적으로 제한되었습니다. 잠시 후 다시 시도해주세요."
            })
        
        return jsonify({"status": "error", "message": error_message})


@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    """사용자의 모든 채널 카테고리 가져오기"""
    # eager loading을 사용하여 관련 테이블을 한 번에 조회
    categories = ChannelCategory.query.options(
        db.joinedload(ChannelCategory.category_channels).joinedload(CategoryChannel.channel)
    ).filter_by(user_id=current_user.id).all()

    result = []

    for category in categories:
        channels = [{
            'id': cat_channel.channel.id,
            'title': cat_channel.channel.title,
            'description': cat_channel.channel.description,
            'thumbnail': cat_channel.channel.thumbnail
        } for cat_channel in category.category_channels]

        result.append({
            'id': str(category.id),
            'name': category.name,
            'description': category.description,
            'createdAt': category.created_at.isoformat(),
            'channels': channels
        })

    return jsonify({"status": "success", "categories": result})

@app.route('/api/categories', methods=['POST'])
@login_required
def create_category():
    """새 채널 카테고리 생성"""
    data = request.json
    
    if not data.get('name'):
        return jsonify({"status": "error", "message": "카테고리 이름은 필수입니다."})
    
    # 이름 중복 확인
    existing = ChannelCategory.query.filter_by(user_id=current_user.id, name=data['name']).first()
    if existing:
        return jsonify({"status": "error", "message": "이미 존재하는 카테고리 이름입니다."})
    
    # 새 카테고리 생성
    category = ChannelCategory(
        user_id=current_user.id,
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(category)
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": "카테고리가 생성되었습니다.",
        "category": {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
            "createdAt": category.created_at.isoformat(),
            "channels": []
        }
    })

@app.route('/api/categories/<int:category_id>', methods=['DELETE'])
@login_required
def delete_category(category_id):
    """채널 카테고리 삭제"""
    category = ChannelCategory.query.filter_by(id=category_id, user_id=current_user.id).first()
    
    if not category:
        return jsonify({"status": "error", "message": "카테고리를 찾을 수 없습니다."})
    
    db.session.delete(category)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "카테고리가 삭제되었습니다."})

@app.route('/api/categories/<int:category_id>/channels', methods=['POST'])
@login_required
def add_channels_to_category(category_id):
    """카테고리에 채널 추가"""
    data = request.json
    category = ChannelCategory.query.filter_by(id=category_id, user_id=current_user.id).first()
    
    if not category:
        return jsonify({"status": "error", "message": "카테고리를 찾을 수 없습니다."})
    
    if not data.get('channels') or not isinstance(data['channels'], list):
        return jsonify({"status": "error", "message": "채널 목록이 유효하지 않습니다."})
    
    added_count = 0
    errors = []
    
    try:
        for channel_data in data['channels']:
            # 채널 ID가 없으면 스킵
            if not channel_data.get('id'):
                continue
                
            # 채널이 이미 데이터베이스에 있는지 확인
            channel = Channel.query.get(channel_data['id'])
            if not channel:
                # 새 채널 추가
                channel = Channel(
                    id=channel_data['id'],
                    title=channel_data.get('title', ''),
                    description=channel_data.get('description', ''),
                    thumbnail=channel_data.get('thumbnail', '')
                )
                db.session.add(channel)
            
            # 이미 카테고리에 추가되어 있는지 확인
            existing = CategoryChannel.query.filter_by(
                category_id=category.id, 
                channel_id=channel.id
            ).first()
            
            if not existing:
                # 카테고리에 채널 연결 (id는 자동 생성되도록 지정하지 않음)
                cat_channel = CategoryChannel(
                    category_id=category.id,
                    channel_id=channel.id
                )
                db.session.add(cat_channel)
                added_count += 1
        
        # 모든 처리가 끝난 후 한 번에 커밋
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"채널 추가 중 오류: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"채널 추가 중 오류가 발생했습니다: {str(e)}"
        })
    
    return jsonify({
        "status": "success", 
        "message": f"{added_count}개의 채널이 추가되었습니다.",
        "added_count": added_count
    })

@app.route('/api/categories/<int:category_id>/channels/<channel_id>', methods=['DELETE'])
@login_required
def remove_channel_from_category(category_id, channel_id):
    """카테고리에서 채널 제거"""
    category = ChannelCategory.query.filter_by(id=category_id, user_id=current_user.id).first()
    
    if not category:
        return jsonify({"status": "error", "message": "카테고리를 찾을 수 없습니다."})
    
    cat_channel = CategoryChannel.query.filter_by(
        category_id=category.id, 
        channel_id=channel_id
    ).first()
    
    if not cat_channel:
        return jsonify({"status": "error", "message": "채널을 찾을 수 없습니다."})
    
    db.session.delete(cat_channel)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "채널이 제거되었습니다."})

@app.route('/api/search/preferences', methods=['GET'])
@login_required
def get_search_preferences():
    """사용자의 저장된 검색 설정 가져오기"""
    pref = SearchPreference.query.filter_by(user_id=current_user.id).order_by(SearchPreference.created_at.desc()).first()
    
    if not pref:
        return jsonify({"status": "success", "has_preferences": False})
    
    return jsonify({
        "status": "success",
        "has_preferences": True,
        "preferences": {
            "keyword": pref.keyword,
            "min_views": pref.min_views,
            "days_ago": pref.days_ago,
            "category_id": pref.category_id,
            "region_code": pref.region_code,
            "language": pref.language,
            "max_results": pref.max_results
        }
    })

@app.route('/api/search/preferences', methods=['POST'])
@login_required
def save_search_preferences():
    """사용자의 검색 설정 저장"""
    data = request.json
    
    # 기존 설정이 있으면 업데이트, 없으면 생성
    pref = SearchPreference.query.filter_by(user_id=current_user.id).first()
    if not pref:
        pref = SearchPreference(user_id=current_user.id)
    
    # 데이터 업데이트
    pref.keyword = data.get('keyword', '')
    pref.min_views = data.get('min_views', 100000)
    pref.days_ago = data.get('days_ago', 5)
    pref.category_id = data.get('category_id', 'any')
    pref.region_code = data.get('region_code', 'KR')
    pref.language = data.get('language', 'any')
    pref.max_results = data.get('max_results', 300)
    pref.created_at = datetime.utcnow()
    
    db.session.add(pref)
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": "검색 설정이 저장되었습니다."
    })

@app.route('/api/search/history', methods=['GET'])
@login_required
def get_search_history():
    """사용자의 검색 기록 가져오기"""
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.created_at.desc()).limit(10).all()
    
    result = []
    for item in history:
        result.append({
            "id": item.id,
            "keyword": item.keyword,
            "min_views": item.min_views,
            "days_ago": item.days_ago,
            "category_id": item.category_id,
            "region_code": item.region_code,
            "language": item.language,
            "max_results": item.max_results,
            "created_at": item.created_at.isoformat(),
            "dateFormatted": item.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return jsonify({"status": "success", "history": result})

@app.route('/api/search/history', methods=['POST'])
@login_required
def add_search_history():
    """새 검색 기록 추가"""
    data = request.json
    
    # 중복 검색 확인 (완전히 동일한 검색 파라미터면 추가하지 않음)
    existing = SearchHistory.query.filter_by(
        user_id=current_user.id,
        keyword=data.get('keyword', ''),
        min_views=data.get('min_views', 0),
        days_ago=data.get('days_ago', 0),
        category_id=data.get('category_id', ''),
        region_code=data.get('region_code', ''),
        language=data.get('language', ''),
        max_results=data.get('max_results', 0)
    ).first()
    
    if existing:
        # 기존 기록이 있으면 타임스탬프만 업데이트
        existing.created_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"status": "success", "message": "검색 기록이 업데이트되었습니다."})
    
    # 새 검색 기록 추가
    history = SearchHistory(
        user_id=current_user.id,
        keyword=data.get('keyword', ''),
        min_views=data.get('min_views', 0),
        days_ago=data.get('days_ago', 0),
        category_id=data.get('category_id', ''),
        region_code=data.get('region_code', ''),
        language=data.get('language', ''),
        max_results=data.get('max_results', 0)
    )
    
    db.session.add(history)
    
    # 최대 검색 기록 개수 제한 (사용자당 10개)
    count = SearchHistory.query.filter_by(user_id=current_user.id).count()
    if count > 10:
        # 가장 오래된 항목 삭제
        oldest = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.created_at).first()
        db.session.delete(oldest)
    
    db.session.commit()
    
    return jsonify({"status": "success", "message": "검색 기록이 저장되었습니다."})

@app.route('/api/search/history', methods=['DELETE'])
@login_required
def clear_search_history():
    """모든 검색 기록 삭제"""
    SearchHistory.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    
    return jsonify({"status": "success", "message": "모든 검색 기록이 삭제되었습니다."})

@app.route('/channel-search', methods=['GET'])
def channel_search():
    # API 호출 로깅
    log_api_call('channel-search', dict(request.args))
    """채널 검색 API 엔드포인트 - 다중 API 키 지원"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "검색어가 필요합니다."})
            
        if not api_keys:
            return jsonify({"status": "error", "message": "YouTube API 키가 설정되지 않았습니다."})
        
        # 최대 API 키 시도 횟수
        max_api_key_attempts = len(api_keys) if api_keys else 1
        attempt_count = 0
        
        while attempt_count < max_api_key_attempts:
            try:
                # YouTube API 서비스 가져오기 (자동 키 순환)
                youtube = get_youtube_api_service()
                
                # URL이나 핸들(@) 형식인지 확인
                if '@' in query or 'youtube.com/' in query:
                    # URL에서 채널 ID 또는 핸들 추출
                    if 'youtube.com/' in query:
                        parts = query.split('/')
                        for part in parts:
                            if part.startswith('@'):
                                query = part
                                break
                    
                    # @ 기호가 있으면 그대로 사용하고, 없으면 추가
                    if not query.startswith('@') and '@' not in query:
                        query = '@' + query
                    
                    # YouTube Data API v3의 정확한 핸들 검색 사용
                    handle = query.replace('@', '')  # @ 기호 제거
                    
                    try:
                        # forHandle 파라미터로 정확한 핸들 매칭
                        response = youtube.channels().list(
                            part="snippet",
                            forHandle=handle,
                            maxResults=1  # 핸들은 유니크하므로 1개만
                        ).execute()
                        
                        if response.get('items'):
                            # 정확한 핸들 매칭 성공
                            item = response['items'][0]
                            channel = {
                                'id': item['id'],
                                'title': item['snippet']['title'],
                                'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                                'description': item['snippet']['description']
                            }
                            return jsonify({"status": "success", "channels": [channel]})
                    except Exception as handle_error:
                        # forHandle 검색 실패 시 대체 방법 사용
                        print(f"핸들 검색 실패: {handle_error}")
                        pass
                    
                    # 대체 방법: 일반 검색으로 핸들 유사 매칭
                    response = youtube.search().list(
                        part="snippet",
                        type="channel",
                        q=handle,  # @ 기호 제거하고 검색
                        maxResults=10  # 더 많은 결과를 가져와서 정확히 필터링
                    ).execute()
                    
                    # 결과에서 정확한 핸들 매칭 시도
                    exact_matches = []
                    partial_matches = []
                    
                    for item in response.get('items', []):
                        channel_title = item['snippet']['title'].lower()
                        # 정확한 매칭 우선 (대소문자 무시)
                        if channel_title == handle.lower():
                            exact_matches.append({
                                'id': item['id']['channelId'],
                                'title': item['snippet']['title'],
                                'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                                'description': item['snippet']['description']
                            })
                        # 부분 매칭은 별도로 저장
                        elif handle.lower() in channel_title:
                            partial_matches.append({
                                'id': item['id']['channelId'],
                                'title': item['snippet']['title'],
                                'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                                'description': item['snippet']['description']
                            })
                    
                    # 정확한 매칭이 있으면 그것만 반환, 없으면 부분 매칭 반환
                    filtered_channels = exact_matches if exact_matches else partial_matches[:3]  # 최대 3개로 제한
                    
                    if filtered_channels:
                        return jsonify({"status": "success", "channels": filtered_channels})
                
                # 일반 검색으로 진행
                response = youtube.search().list(
                    part="snippet",
                    type="channel",
                    q=query,
                    maxResults=5
                ).execute()
                
                channels = [{
                    'id': item['id']['channelId'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                    'description': item['snippet']['description']
                } for item in response.get('items', [])]
                
                return jsonify({"status": "success", "channels": channels})
                
            except Exception as e:
                error_str = str(e).lower()
                if 'quota' in error_str or 'exceeded' in error_str:
                    # 다음 API 키로 전환
                    next_key = switch_to_next_api_key()
                    if next_key:
                        print(f"채널 검색: 할당량 초과로 다음 API 키로 전환합니다.")
                        attempt_count += 1
                        continue
                    else:
                        return jsonify({
                            "status": "quota_exceeded", 
                            "message": "모든 YouTube API 키의 할당량이 초과되었습니다."
                        })
                else:
                    return jsonify({"status": "error", "message": str(e)})
        
        # 모든 시도 실패 시
        return jsonify({"status": "error", "message": "모든 API 키 시도 후에도 검색에 실패했습니다."})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/categories/import', methods=['POST'])
@login_required
def import_categories():
    """카테고리 데이터 가져오기 (기존 데이터 대체)"""
    data = request.json
    
    if not data or not data.get('categories') or not isinstance(data['categories'], list):
        return jsonify({"status": "error", "message": "유효하지 않은 데이터 형식입니다."})
    
    # 기존 카테고리 삭제
    ChannelCategory.query.filter_by(user_id=current_user.id).delete()
    
    imported_count = 0
    for cat_data in data['categories']:
        # 기본 정보 확인
        if not cat_data.get('name'):
            continue
            
        # 새 카테고리 생성
        category = ChannelCategory(
            user_id=current_user.id,
            name=cat_data['name'],
            description=cat_data.get('description', '')
        )
        db.session.add(category)
        db.session.flush()  # ID 할당을 위해 플러시
        
        # 채널 추가
        channels = cat_data.get('channels', [])
        for channel_data in channels:
            if not channel_data.get('id'):
                continue
                
            # 채널 존재 여부 확인
            channel = Channel.query.get(channel_data['id'])
            if not channel:
                # 새 채널 추가
                channel = Channel(
                    id=channel_data['id'],
                    title=channel_data.get('title', ''),
                    description=channel_data.get('description', ''),
                    thumbnail=channel_data.get('thumbnail', '')
                )
                db.session.add(channel)
                
            # 카테고리에 채널 연결
            cat_channel = CategoryChannel(
                category_id=category.id,
                channel_id=channel.id
            )
            db.session.add(cat_channel)
        
        imported_count += 1
    
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": f"{imported_count}개의 카테고리가 가져오기 되었습니다.",
        "count": imported_count
    })

@app.route('/api/categories/merge', methods=['POST'])
@login_required
def merge_categories():
    """카테고리 데이터 병합"""
    data = request.json
    
    if not data or not data.get('categories') or not isinstance(data['categories'], list):
        return jsonify({"status": "error", "message": "유효하지 않은 데이터 형식입니다."})
    
    new_categories_count = 0
    updated_categories_count = 0
    
    for cat_data in data['categories']:
        # 기본 정보 확인
        if not cat_data.get('name'):
            continue
            
        # 동일한 이름의 카테고리가 있는지 확인
        existing = ChannelCategory.query.filter_by(
            user_id=current_user.id, 
            name=cat_data['name']
        ).first()
        
        if not existing:
            # 새 카테고리 생성
            category = ChannelCategory(
                user_id=current_user.id,
                name=cat_data['name'],
                description=cat_data.get('description', '')
            )
            db.session.add(category)
            db.session.flush()  # ID 할당을 위해 플러시
            new_categories_count += 1
        else:
            category = existing
            
        # 채널 추가
        channels = cat_data.get('channels', [])
        added_channels = 0
        
        for channel_data in channels:
            if not channel_data.get('id'):
                continue
                
            # 이미 카테고리에 추가된 채널인지 확인
            existing_channel = CategoryChannel.query.filter_by(
                category_id=category.id, 
                channel_id=channel_data['id']
            ).first()
            
            if not existing_channel:
                # 채널 존재 여부 확인
                channel = Channel.query.get(channel_data['id'])
                if not channel:
                    # 새 채널 추가
                    channel = Channel(
                        id=channel_data['id'],
                        title=channel_data.get('title', ''),
                        description=channel_data.get('description', ''),
                        thumbnail=channel_data.get('thumbnail', '')
                    )
                    db.session.add(channel)
                    
                # 카테고리에 채널 연결
                cat_channel = CategoryChannel(
                    category_id=category.id,
                    channel_id=channel.id
                )
                db.session.add(cat_channel)
                added_channels += 1
                
        if added_channels > 0 and existing:
            updated_categories_count += 1
    
    db.session.commit()
    
    return jsonify({
        "status": "success", 
        "message": f"{new_categories_count}개의 새 카테고리, {updated_categories_count}개의 카테고리가 업데이트되었습니다.",
        "newCategoriesCount": new_categories_count,
        "updatedCategoriesCount": updated_categories_count
    })


@app.route('/notifications')
@login_required
def notifications_page():
    """알림 설정 페이지"""
    if not current_user.is_approved():
        return redirect(url_for('pending'))
    
    # 사용자의 알림 설정 가져오기
    notification = EmailNotification.query.filter_by(user_id=current_user.id).first()
    
    # 사용자의 카테고리 목록 가져오기
    categories = ChannelCategory.query.filter_by(user_id=current_user.id).all()
    
    # 알림 설정이 없으면 기본값으로 생성
    if not notification:
        notification = EmailNotification(
            user_id=current_user.id,
            active=False,
            frequency=3,
            preferred_times="9,13,18",  # 기본값: 오전 9시, 오후 1시, 오후 6시
            weekly_settlement_active=False
        )
        db.session.add(notification)
        db.session.commit()
    
    # 카테고리별 검색 설정 정보
    notification_searches = {}
    for search in notification.searches:
        notification_searches[search.category_id] = {
            'min_views': search.min_views,
            'days_ago': search.days_ago,
            'max_results': search.max_results
        }
    
    return render_template(
        'notifications.html',
        notification=notification,
        categories=categories,
        notification_searches=notification_searches
    )

@app.route('/api/notifications/save', methods=['POST'])
@login_required
def save_notification_settings():
    """알림 설정 저장 API"""
    data = request.json
    
    if not data:
        return jsonify({"status": "error", "message": "유효하지 않은 데이터입니다."})
    
    # 기존 알림 설정 가져오기 또는 새로 생성
    notification = EmailNotification.query.filter_by(user_id=current_user.id).first()
    if not notification:
        notification = EmailNotification(user_id=current_user.id)
        db.session.add(notification)
    
    # 기본 설정 업데이트
    notification.active = data.get('active', False)
    notification.frequency = data.get('frequency', 3)
    notification.preferred_times = data.get('preferred_times', "9,13,18")
    notification.weekly_settlement_active = data.get('weekly_settlement_active', False)
    
    # 기존 검색 설정 삭제
    NotificationSearch.query.filter_by(notification_id=notification.id).delete()
    
    # 새로운 검색 설정 추가
    categories = data.get('categories', [])
    for category_data in categories:
        if not category_data.get('id'):
            continue
            
        # 카테고리 존재 확인
        category = ChannelCategory.query.filter_by(
            id=category_data['id'],
            user_id=current_user.id
        ).first()
        
        if category:
            search = NotificationSearch(
                notification_id=notification.id,
                category_id=category.id,
                min_views=category_data.get('min_views', 100000),
                days_ago=category_data.get('days_ago', 1),
                max_results=category_data.get('max_results', 5)
            )
            db.session.add(search)
    
    db.session.commit()
    
    return jsonify({
        "status": "success",
        "message": "알림 설정이 저장되었습니다."
    })

@app.route('/api/notifications/debug', methods=['POST'])
@login_required
def debug_notification_search():
    """날짜 필터링 디버깅용 API"""
    from datetime import datetime, timedelta
    
    # 사용자의 알림 설정 가져오기
    notification = EmailNotification.query.filter_by(user_id=current_user.id).first()
    if not notification:
        return jsonify({"status": "error", "message": "저장된 알림 설정이 없습니다."})
    
    debug_info = []
    for search in notification.searches:
        category = search.category
        channels = [cat_channel.channel.id for cat_channel in category.category_channels]
        
        if channels:
            cutoff_date = datetime.utcnow() - timedelta(days=search.days_ago)
            debug_info.append({
                "category": category.name,
                "days_ago": search.days_ago,
                "cutoff_date": cutoff_date.strftime('%Y-%m-%d %H:%M:%S'),
                "min_views": search.min_views,
                "channels_count": len(channels)
            })
    
    return jsonify({
        "status": "success",
        "debug_info": debug_info,
        "current_time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/notifications/test', methods=['POST'])
@login_required
def test_notification_email():
    """테스트 알림 이메일 발송"""
    # 이메일 서비스 인스턴스 생성
    email_service = EmailService(app)
    
    # 사용자의 알림 설정 가져오기
    notification = EmailNotification.query.filter_by(user_id=current_user.id).first()
    if not notification:
        return jsonify({"status": "error", "message": "저장된 알림 설정이 없습니다."})
    
    # 검색 결과 수집
    scheduler = NotificationScheduler(app, db, email_service)
    search_results = scheduler.collect_search_results(notification)
    
    # KST 시간대로 변환
    import pytz
    from datetime import datetime
    kst = pytz.timezone('Asia/Seoul')
    kst_now = datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(kst)
    kst_timestamp = kst_now.strftime('%Y-%m-%d %H:%M:%S KST')
    
    # 테스트 이메일 발송
    email_html = email_service.format_shorts_email(
        current_user,
        search_results,
        kst_timestamp
    )
    
    success = email_service.send_email(
        current_user.email,
        f"YouTube Shorts 인기 영상 알림 (테스트 - {kst_now.strftime('%Y-%m-%d %H:%M')})",
        email_html
    )
    
    if success:
        # 테스트 이메일 발송 시에도 이력 기록 (선택적)
        # notification_scheduler.record_sent_videos(current_user.id, search_results)
        
        return jsonify({
            "status": "success",
            "message": f"{current_user.email} 주소로 테스트 이메일이 발송되었습니다."
        })
    else:
        return jsonify({
            "status": "error",
            "message": "이메일 발송 중 오류가 발생했습니다."
        })

@app.route('/admin/reset-sequence', methods=['GET'])
@login_required
def reset_sequence():
    if not current_user.is_admin():
        return jsonify({"status": "error", "message": "관리자 권한이 필요합니다."})
    
    try:
        # 최대 ID 값 찾기 - text() 함수로 감싸기
        max_id_result = db.session.execute(text("SELECT MAX(id) FROM category_channel")).scalar()
        max_id = max_id_result if max_id_result is not None else 0
        
        # 시퀀스 재설정 (PostgreSQL용) - text() 함수로 감싸기
        db.session.execute(text(f"ALTER SEQUENCE category_channel_id_seq RESTART WITH {max_id + 1}"))
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"시퀀스가 성공적으로 재설정되었습니다. 다음 ID: {max_id + 1}"
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"시퀀스 재설정 중 오류: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": f"시퀀스 재설정 중 오류가 발생했습니다: {str(e)}"
        })
        
# 정적 파일 제공 라우트
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/static/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(app.static_folder, 'js'), filename)

@app.route('/static/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(app.static_folder, 'css'), filename)

@app.route('/favicon.ico')
def favicon():
    """Favicon 반환 라우트"""
    return send_from_directory(os.path.join(app.root_path, 'static'),'favicon.ico', mimetype='image/vnd.microsoft.icon')

# 에러 핸들러
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f'서버 오류: {str(e)}')
    return render_template('error/500.html'), 500


# 이메일 서비스 및 스케줄러 설정
app.logger.info("이메일 서비스 초기화...")
email_service = EmailService(app)

# 파일 락을 사용하여 하나의 프로세스만 스케줄러 실행
app.logger.info("스케줄러 초기화 시도...")
lock_file_path = '/tmp/scheduler.lock'

try:
    lock_file = open(lock_file_path, 'w')
    fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    
    # 잠금을 획득한 프로세스만 스케줄러 시작
    app.logger.info(f"프로세스 {os.getpid()}에서 스케줄러 락 획득, 스케줄러 시작...")
    scheduler = NotificationScheduler(app, db, email_service)
    scheduler.start()
    
    # 종료 시 정리
    def shutdown_scheduler():
        app.logger.info("애플리케이션 종료: 스케줄러 종료 중...")
        if hasattr(scheduler, 'scheduler') and scheduler.scheduler.running:
            scheduler.scheduler.shutdown()
        # 잠금 해제
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()
        app.logger.info("스케줄러가 성공적으로 종료되었습니다.")
    
    import atexit
    atexit.register(shutdown_scheduler)
    app.logger.info("스케줄러 초기화 완료")
    
except IOError:
    # 다른 프로세스가 이미 잠금을 획득함
    app.logger.info(f"프로세스 {os.getpid()}에서 스케줄러 락 획득 실패, 스케줄러 초기화 건너뜀")

# ===================== 저장된 영상 관리 API =====================

@app.route('/api/saved-videos', methods=['POST'])
@login_required
def save_video():
    """영상 저장 API"""
    try:
        data = request.get_json()
        
        # 필수 데이터 검증
        required_fields = ['video_id', 'video_title', 'channel_title', 'video_url']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field}는 필수 입력값입니다.'}), 400
        
        # 이미 저장된 영상인지 확인
        existing_video = SavedVideo.query.filter_by(
            user_id=current_user.id, 
            video_id=data['video_id']
        ).first()
        
        if existing_video:
            return jsonify({'success': False, 'message': '이미 저장된 영상입니다.'}), 409
        
        # 새 저장된 영상 생성
        saved_video = SavedVideo(
            user_id=current_user.id,
            video_id=data['video_id'],
            video_title=data['video_title'],
            channel_title=data['channel_title'],
            channel_id=data.get('channel_id'),
            thumbnail_url=data.get('thumbnail_url'),
            video_url=data['video_url'],
            view_count=data.get('view_count', 0),
            duration=data.get('duration'),
            published_at=datetime.fromisoformat(data['published_at'].replace('Z', '+00:00')) if data.get('published_at') else None,
            notes=data.get('notes', '')
        )
        
        db.session.add(saved_video)
        db.session.commit()
        
        app.logger.info(f"사용자 {current_user.email}가 영상을 저장했습니다: {data['video_id']}")
        
        return jsonify({
            'success': True, 
            'message': '영상이 성공적으로 저장되었습니다.',
            'video': saved_video.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"영상 저장 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '영상 저장 중 오류가 발생했습니다.'}), 500

@app.route('/api/saved-videos', methods=['GET'])
@login_required
def get_saved_videos():
    """저장된 영상 목록 조회 API"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 50)  # 최대 50개
        
        # 저장된 영상 조회 (최신순)
        pagination = SavedVideo.query.filter_by(user_id=current_user.id)\
            .order_by(SavedVideo.saved_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        videos = [video.to_dict() for video in pagination.items]
        
        return jsonify({
            'success': True,
            'videos': videos,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
        
    except Exception as e:
        app.logger.error(f"저장된 영상 조회 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '저장된 영상 조회 중 오류가 발생했습니다.'}), 500

@app.route('/api/saved-videos/<int:video_id>', methods=['DELETE'])
@login_required
def delete_saved_video(video_id):
    """저장된 영상 삭제 API"""
    try:
        saved_video = SavedVideo.query.filter_by(
            id=video_id, 
            user_id=current_user.id
        ).first()
        
        if not saved_video:
            return jsonify({'success': False, 'message': '해당 영상을 찾을 수 없습니다.'}), 404
        
        video_title = saved_video.video_title
        db.session.delete(saved_video)
        db.session.commit()
        
        app.logger.info(f"사용자 {current_user.email}가 저장된 영상을 삭제했습니다: {video_title}")
        
        return jsonify({
            'success': True, 
            'message': '영상이 성공적으로 삭제되었습니다.'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"저장된 영상 삭제 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '영상 삭제 중 오류가 발생했습니다.'}), 500

@app.route('/api/saved-videos/<int:video_id>/notes', methods=['PUT'])
@login_required 
def update_video_notes(video_id):
    """저장된 영상 메모 업데이트 API"""
    try:
        data = request.get_json()
        notes = data.get('notes', '')
        
        saved_video = SavedVideo.query.filter_by(
            id=video_id,
            user_id=current_user.id
        ).first()
        
        if not saved_video:
            return jsonify({'success': False, 'message': '해당 영상을 찾을 수 없습니다.'}), 404
        
        saved_video.notes = notes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '메모가 성공적으로 업데이트되었습니다.',
            'video': saved_video.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"영상 메모 업데이트 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '메모 업데이트 중 오류가 발생했습니다.'}), 500

# ===================== 사용자 API 키 관리 API =====================

@app.route('/api-keys')
@login_required
def api_keys_page():
    """사용자 API 키 관리 페이지"""
    if not current_user.is_approved():
        return redirect(url_for('pending'))
    
    return render_template('api_keys.html', user=current_user)

@app.route('/api/user-api-keys', methods=['GET'])
@login_required
def get_user_api_keys():
    """사용자의 API 키 목록 조회"""
    try:
        manager = UserApiKeyManager(current_user.id)
        keys = manager.get_user_api_keys()
        
        return jsonify({
            'success': True,
            'api_keys': keys,
            'total_count': len(keys)
        })
        
    except Exception as e:
        app.logger.error(f"API 키 목록 조회 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': 'API 키 목록을 조회할 수 없습니다.'}), 500

@app.route('/api/user-api-keys', methods=['POST'])
@login_required
def add_user_api_key():
    """새 API 키 추가"""
    try:
        data = request.get_json()
        
        # 필수 데이터 검증
        if not data.get('name') or not data.get('api_key'):
            return jsonify({'success': False, 'message': '이름과 API 키는 필수입니다.'}), 400
        
        # API 키 개수 제한 (사용자당 최대 5개)
        manager = UserApiKeyManager(current_user.id)
        existing_keys = manager.get_user_api_keys()
        
        if len(existing_keys) >= 5:
            return jsonify({'success': False, 'message': '최대 5개의 API 키만 등록할 수 있습니다.'}), 400
        
        name = data['name'].strip()
        api_key = data['api_key'].strip()
        
        # 이름 길이 제한
        if len(name) > 50:
            return jsonify({'success': False, 'message': 'API 키 이름은 50자를 초과할 수 없습니다.'}), 400
        
        success, message = manager.add_api_key(name, api_key)
        
        if success:
            app.logger.info(f"사용자 {current_user.email}가 새 API 키를 추가했습니다: {name}")
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        app.logger.error(f"API 키 추가 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': 'API 키 추가 중 오류가 발생했습니다.'}), 500

@app.route('/api/user-api-keys/<int:key_id>', methods=['PUT'])
@login_required
def update_user_api_key(key_id):
    """API 키 정보 업데이트"""
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip() if data.get('name') else None
        is_active = data.get('is_active')
        
        # 이름 길이 제한
        if name and len(name) > 50:
            return jsonify({'success': False, 'message': 'API 키 이름은 50자를 초과할 수 없습니다.'}), 400
        
        manager = UserApiKeyManager(current_user.id)
        success, message = manager.update_api_key(key_id, name, None, is_active)
        
        if success:
            app.logger.info(f"사용자 {current_user.email}가 API 키를 업데이트했습니다: ID {key_id}")
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        app.logger.error(f"API 키 업데이트 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': 'API 키 업데이트 중 오류가 발생했습니다.'}), 500

@app.route('/api/user-api-keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_user_api_key(key_id):
    """API 키 삭제"""
    try:
        manager = UserApiKeyManager(current_user.id)
        success, message = manager.delete_api_key(key_id)
        
        if success:
            app.logger.info(f"사용자 {current_user.email}가 API 키를 삭제했습니다: ID {key_id}")
            return jsonify({'success': True, 'message': message})
        else:
            return jsonify({'success': False, 'message': message}), 404
            
    except Exception as e:
        app.logger.error(f"API 키 삭제 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': 'API 키 삭제 중 오류가 발생했습니다.'}), 500

@app.route('/api/user-api-keys/test/<int:key_id>', methods=['POST'])
@login_required
def test_user_api_key(key_id):
    """API 키 테스트"""
    try:
        api_key_obj = UserApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
        if not api_key_obj:
            return jsonify({'success': False, 'message': 'API 키를 찾을 수 없습니다.'}), 404
        
        manager = UserApiKeyManager(current_user.id)
        decrypted_key = manager.decrypt_api_key(api_key_obj.api_key)
        
        # 간단한 API 호출 테스트
        import googleapiclient.discovery
        import time
        
        start_time = time.time()
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=decrypted_key)
        
        # 가벼운 테스트 요청 (할당량 1 소모)
        test_response = youtube.search().list(
            part="snippet",
            q="test",
            type="video",
            maxResults=1
        ).execute()
        
        response_time = round((time.time() - start_time) * 1000, 2)  # 밀리초 단위
        
        # 테스트 성공 기록
        manager.current_key = api_key_obj
        manager.record_api_usage("search.list", success=True, response_time=response_time/1000)
        
        return jsonify({
            'success': True, 
            'message': 'API 키가 정상적으로 작동합니다.',
            'response_time': f"{response_time}ms",
            'items_found': len(test_response.get('items', []))
        })
        
    except Exception as e:
        error_str = str(e).lower()
        
        # 테스트 실패 기록
        if 'api_key_obj' in locals():
            manager = UserApiKeyManager(current_user.id)
            manager.current_key = api_key_obj
            manager.record_api_usage("search.list", success=False, error_message=str(e))
        
        if 'quota' in error_str or 'exceeded' in error_str:
            message = 'API 키는 유효하지만 할당량이 초과되었습니다.'
        elif 'invalid' in error_str or 'forbidden' in error_str:
            message = '유효하지 않은 API 키입니다.'
        else:
            message = f'API 키 테스트 중 오류가 발생했습니다: {str(e)}'
        
        app.logger.error(f"API 키 테스트 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/user-api-keys/statistics', methods=['GET'])
@login_required
def get_api_key_statistics():
    """API 키 사용 통계 조회"""
    try:
        days = int(request.args.get('days', 7))
        days = min(days, 30)  # 최대 30일
        
        manager = UserApiKeyManager(current_user.id)
        statistics = manager.get_usage_statistics(days)
        
        return jsonify({
            'success': True,
            'statistics': statistics,
            'period_days': days
        })
        
    except Exception as e:
        app.logger.error(f"API 키 통계 조회 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '통계를 조회할 수 없습니다.'}), 500

@app.route('/api/user-api-keys/reset-usage/<int:key_id>', methods=['POST'])
@login_required
def reset_api_key_usage(key_id):
    """API 키 일일 사용량 수동 리셋 (관리자 또는 키 소유자만)"""
    try:
        api_key_obj = UserApiKey.query.filter_by(id=key_id, user_id=current_user.id).first()
        if not api_key_obj:
            return jsonify({'success': False, 'message': 'API 키를 찾을 수 없습니다.'}), 404
        
        # 수동 리셋 (오늘 날짜로 강제 설정)
        api_key_obj.usage_count = 0
        api_key_obj.error_count = 0
        api_key_obj.last_reset_date = datetime.utcnow().date()
        api_key_obj.updated_at = datetime.utcnow()
        db.session.commit()
        
        app.logger.info(f"사용자 {current_user.email}가 API 키 사용량을 리셋했습니다: {api_key_obj.name}")
        
        return jsonify({
            'success': True,
            'message': 'API 키 사용량이 리셋되었습니다.'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"API 키 사용량 리셋 중 오류: {str(e)}")
        return jsonify({'success': False, 'message': '사용량 리셋 중 오류가 발생했습니다.'}), 500


# 사용자 API 키 상태 체크 API
@app.route('/api/user-api-status')
@login_required
def check_user_api_status():
    """사용자 API 키 상태 체크"""
    try:
        manager = UserApiKeyManager(current_user.id)
        api_keys = manager.get_user_api_keys()
        
        # 사용 가능한 키가 있는지 확인
        available_key = manager.get_available_api_key()
        
        status = {
            'has_keys': len(api_keys) > 0,
            'total_keys': len(api_keys),
            'active_keys': len([k for k in api_keys if k['is_active']]),
            'available_quota': available_key is not None,
            'keys_summary': []
        }
        
        # 각 키의 간단한 상태 정보
        for key in api_keys:
            key_status = {
                'id': key['id'],
                'name': key['name'],
                'is_active': key['is_active'],
                'usage_percentage': key['usage_percentage'],
                'is_healthy': key['error_count'] < 5,
                'quota_exceeded': key['usage_count'] >= key['daily_quota']
            }
            status['keys_summary'].append(key_status)
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        app.logger.error(f"API 키 상태 체크 오류: {str(e)}")
        return jsonify({
            'success': False,
            'message': '상태를 확인할 수 없습니다.'
        })

# 네비게이션에 API 키 관리 링크 추가를 위한 컨텍스트 프로세서
@app.context_processor
def inject_api_key_status():
    """템플릿에서 사용할 API 키 상태 정보 주입"""
    if current_user.is_authenticated and current_user.is_approved():
        try:
            manager = UserApiKeyManager(current_user.id)
            api_keys = manager.get_user_api_keys()
            
            return {
                'user_has_api_keys': len(api_keys) > 0,
                'user_api_keys_count': len(api_keys)
            }
        except:
            pass
    
    return {
        'user_has_api_keys': False,
        'user_api_keys_count': 0
    }


@app.route('/saved-videos')
@login_required
def saved_videos_page():
    """저장된 영상 관리 페이지"""
    if not current_user.is_approved():
        return redirect(url_for('pending'))
    
    return render_template('saved_videos.html', user=current_user)

# ===================== 대시보드 라우트 =====================

@app.route('/dashboard')
@login_required
def dashboard():
    """대시보드 메인 페이지"""
    if not current_user.is_approved():
        return redirect(url_for('pending'))
    
    try:
        # 통계 데이터 수집
        stats = {}
        
        # 총 검색 횟수
        stats['total_searches'] = SearchHistory.query.filter_by(user_id=current_user.id).count()
        
        # 저장된 영상 수
        stats['saved_videos'] = SavedVideo.query.filter_by(user_id=current_user.id).count()
        
        # 사용자 API 키 수
        user_api_keys = UserApiKey.query.filter_by(user_id=current_user.id).all()
        stats['api_keys'] = len(user_api_keys)
        stats['active_api_keys'] = len([k for k in user_api_keys if k.is_active and not k.is_quota_exceeded()])
        
        # 활성 알림 수
        stats['active_notifications'] = EmailNotification.query.filter_by(
            user_id=current_user.id, 
            active=True
        ).count()
        
        # 최근 7일 API 사용량 차트 데이터
        from datetime import timedelta
        today = datetime.utcnow().date()
        chart_data = {
            'labels': [],
            'data': []
        }
        
        for i in range(7):
            date = today - timedelta(days=i)
            day_calls = ApiLog.query.filter(
                ApiLog.user_id == current_user.id,
                db.func.date(ApiLog.timestamp) == date
            ).count()
            
            chart_data['labels'].insert(0, date.strftime('%m/%d'))
            chart_data['data'].insert(0, day_calls)
        
        # 최근 활동 (검색 기록, 저장된 영상 등)
        recent_activities = []
        
        # 최근 검색 기록
        recent_searches = SearchHistory.query.filter_by(user_id=current_user.id)\
            .order_by(SearchHistory.created_at.desc())\
            .limit(5).all()
        
        for search in recent_searches:
            recent_activities.append({
                'type': '검색',
                'description': f'"{search.query or "인기 Shorts"}" 검색',
                'timestamp': search.created_at
            })
        
        # 최근 저장된 영상
        recent_saved = SavedVideo.query.filter_by(user_id=current_user.id)\
            .order_by(SavedVideo.created_at.desc())\
            .limit(3).all()
        
        for video in recent_saved:
            recent_activities.append({
                'type': '저장',
                'description': f'영상 저장: {video.title[:30]}...',
                'timestamp': video.created_at
            })
        
        # 시간순 정렬
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]  # 최근 10개만
        
        # 시스템 상태 (관리자용)
        system_status = None
        if current_user.is_admin():
            try:
                # API 상태 체크 (간단한 체크)
                api_status = len(api_keys) > 0
                
                # 데이터베이스 상태 체크
                db.session.execute(text('SELECT 1'))
                db_status = True
                
                # 이메일 서비스 상태 (기본적으로 True, 실제 테스트는 복잡함)
                email_status = True
                
                # 총 사용자 수
                total_users = User.query.count()
                
                system_status = {
                    'api_status': api_status,
                    'db_status': db_status,
                    'email_status': email_status,
                    'total_users': total_users
                }
            except Exception as e:
                app.logger.error(f"시스템 상태 체크 오류: {str(e)}")
                system_status = {
                    'api_status': False,
                    'db_status': False,
                    'email_status': False,
                    'total_users': 0
                }
        
        return render_template('dashboard.html',
                             user=current_user,
                             stats=stats,
                             chart_data=chart_data,
                             recent_activities=recent_activities,
                             system_status=system_status)
    
    except Exception as e:
        app.logger.error(f"대시보드 로드 오류: {str(e)}")
        flash('대시보드를 로드하는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
        # 이메일 서비스 및 스케줄러 설정
    email_service = EmailService(app)
    scheduler = NotificationScheduler(app, db, email_service)
    scheduler.start()

    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)  # 디버그 모드 활성화

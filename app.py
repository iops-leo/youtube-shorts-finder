import os
from celery import Celery
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import googleapiclient.discovery
import pytz
import isodate
import json
from functools import lru_cache
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
# 공통 기능 임포트
from core.search import (
    get_recent_popular_shorts, get_cache_key, save_to_cache, 
    get_youtube_api_service, perform_search, switch_to_next_api_key, api_keys
)


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key')  # 실제 배포 시 환경 변수로 설정해야 함
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
db = SQLAlchemy(app)

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

# 로그인 매니저 설정
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 정적 파일 경로 설정
app.static_folder = 'static'

# 데이터베이스 모델 정의
class User(db.Model, UserMixin):
    id = db.Column(db.String(128), primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    picture = db.Column(db.String(256))
    role = db.Column(db.String(20), default='pending')  # pending, approved, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    api_calls = db.Column(db.Integer, default=0)

    def is_admin(self):
        return self.role == 'admin'
    
    def is_approved(self):
        return self.role == 'approved' or self.role == 'admin'

class ApiLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'))
    endpoint = db.Column(db.String(128), nullable=False)
    params = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('api_logs', lazy=True))

# app.py에 추가할 모델

class ChannelCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('categories', lazy=True))
    
class Channel(db.Model):
    id = db.Column(db.String(128), primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    thumbnail = db.Column(db.String(255))
    
class CategoryChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('channel_category.id', ondelete='CASCADE'), nullable=False)
    channel_id = db.Column(db.String(128), db.ForeignKey('channel.id'), nullable=False)
    
    category = db.relationship('ChannelCategory', backref=db.backref('category_channels', lazy=True, cascade='all, delete-orphan'))
    channel = db.relationship('Channel', backref=db.backref('category_channels', lazy=True))
    
class SearchPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    keyword = db.Column(db.String(255))
    min_views = db.Column(db.Integer, default=100000)
    days_ago = db.Column(db.Integer, default=5)
    category_id = db.Column(db.String(10))
    region_code = db.Column(db.String(10))
    language = db.Column(db.String(10))
    max_results = db.Column(db.Integer, default=300)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('search_preferences', lazy=True))

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    keyword = db.Column(db.String(255))
    min_views = db.Column(db.Integer)
    days_ago = db.Column(db.Integer)
    category_id = db.Column(db.String(10))
    region_code = db.Column(db.String(10))
    language = db.Column(db.String(10))
    max_results = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('search_history', lazy=True))

with app.app_context():
    db.create_all()
    app.logger.info('데이터베이스 테이블 생성 완료')

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
    
    # 로컬 개발 환경이면 로컬 URI도 추가
    if is_local_dev:
        port = os.environ.get('PORT', '8080')
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
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
    is_local_dev = os.environ.get('FLASK_ENV') == 'dev'
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
    is_local_dev = os.environ.get('FLASK_ENV') == 'dev'
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
        return redirect(url_for('index'))
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

# API 호출 로깅 함수
def log_api_call(endpoint, params=None):
    if current_user.is_authenticated:
        # API 호출 로그 저장
        api_log = ApiLog(
            user_id=current_user.id,
            endpoint=endpoint,
            params=json.dumps(params) if params else None
        )
        db.session.add(api_log)
        
        # 사용자의 API 호출 횟수 증가
        current_user.api_calls += 1
        db.session.commit()
        
        app.logger.info(f'API 호출: {endpoint} by {current_user.email}')

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

# 정적 파일 경로 설정
app.static_folder = 'static'


@app.route("/search", methods=["POST"])
@api_login_required
def search():
    try:
        data = request.form

        # 파라미터 파싱
        params = {
            'min_views': int(data.get('min_views', '100000')),
            'days_ago': int(data.get('days_ago', 5)),
            'max_results': int(data.get('max_results', 300)),
            'category_id': data.get('category_id') if data.get('category_id') != 'any' else None,
            'region_code': data.get('region_code'),
            'language': data.get('language') if data.get('language') != 'any' else None,
            'keyword': data.get('keyword'),
            'channel_ids': data.get('channel_ids') or None
        }

        user_id = current_user.id if current_user.is_authenticated else 'anonymous'
        cache_params = {'user_id': user_id, 'date': datetime.utcnow().date().isoformat(), **params}
        cache_key = get_cache_key(cache_params)
        cached_results = get_from_cache(cache_key)
        if cached_results:
            return jsonify({"status": "success", "results": cached_results, "fromCache": True})
        
        from celery_worker.celery_worker import run_search_task

        # 비동기 작업 실행
        task = run_search_task.delay(cache_params)
        results = task.get(timeout=30)  # 30초까지 기다림

        return jsonify({
            "status": "success",
            "results": results,
            "fromCache": False
        })
    except Exception as e:
        print(f"오류 발생: {e}")
        return jsonify({"status": "error", "message": str(e)})
    


@app.route('/api/categories', methods=['GET'])
@login_required
def get_categories():
    """사용자의 모든 채널 카테고리 가져오기"""
    categories = ChannelCategory.query.filter_by(user_id=current_user.id).all()
    result = []
    
    for category in categories:
        # 카테고리에 속한 채널 가져오기
        channels = []
        for cat_channel in category.category_channels:
            channel = cat_channel.channel
            channels.append({
                'id': channel.id,
                'title': channel.title,
                'description': channel.description,
                'thumbnail': channel.thumbnail
            })
        
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
            # 카테고리에 채널 연결
            cat_channel = CategoryChannel(
                category_id=category.id,
                channel_id=channel.id
            )
            db.session.add(cat_channel)
            added_count += 1
    
    db.session.commit()
    
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
                    
                    # 핸들 검색 (채널 이름으로 검색 + 필터링)
                    response = youtube.search().list(
                        part="snippet",
                        type="channel",
                        q=query.replace('@', ''),  # @ 기호 제거하고 검색
                        maxResults=10  # 더 많은 결과를 가져와서 필터링
                    ).execute()
                    
                    # 결과에서 정확히 일치하거나 유사한 핸들을 가진 채널 필터링
                    filtered_channels = []
                    channel_handle = query.lower().replace('@', '')
                    
                    for item in response.get('items', []):
                        channel_title = item['snippet']['title'].lower()
                        channel_desc = item['snippet']['description'].lower()
                        
                        if (channel_handle in channel_title.replace(' ', '') or 
                            channel_handle in channel_desc):
                            filtered_channels.append({
                                'id': item['id']['channelId'],
                                'title': item['snippet']['title'],
                                'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                                'description': item['snippet']['description']
                            })
                    
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
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

# 에러 핸들러
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f'서버 오류: {str(e)}')
    return render_template('error/500.html'), 500

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

def make_celery(app):
    celery = Celery(
        app.import_name,
        broker=os.environ.get("REDIS_URL"),  # Railway Redis URL
        backend=os.environ.get("REDIS_URL")
    )
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)  # 디버그 모드 활성화

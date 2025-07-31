from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

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

class EmailNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    frequency = db.Column(db.Integer, default=3)
    preferred_times = db.Column(db.String(128))
    last_sent = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('email_notifications', lazy=True))

class NotificationSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    notification_id = db.Column(db.Integer, db.ForeignKey('email_notification.id', ondelete='CASCADE'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('channel_category.id'), nullable=False)
    min_views = db.Column(db.Integer, default=100000)
    days_ago = db.Column(db.Integer, default=1)
    max_results = db.Column(db.Integer, default=5)

    notification = db.relationship('EmailNotification', backref=db.backref('searches', lazy=True, cascade='all, delete-orphan'))
    category = db.relationship('ChannelCategory', backref=db.backref('notification_searches', lazy=True))


class Editor(db.Model):
    """편집자 모델"""
    __tablename__ = 'editors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(50))
    email = db.Column(db.String(100))
    contract_date = db.Column(db.Date, default=datetime.utcnow().date)
    basic_rate = db.Column(db.Integer, default=15000)  # 기본 단가
    japanese_rate = db.Column(db.Integer, default=20000)  # 일본어 단가
    status = db.Column(db.String(20), default='active')  # active, inactive, pending
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    user = db.relationship('User', backref='editors')
    works = db.relationship('Work', backref='editor', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'contact': self.contact,
            'email': self.email,
            'contract_date': self.contract_date.isoformat() if self.contract_date else None,
            'basic_rate': self.basic_rate,
            'japanese_rate': self.japanese_rate,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class EditorRateHistory(db.Model):
    """편집자 단가 변경 이력 모델"""
    __tablename__ = 'editor_rate_history'
    
    id = db.Column(db.Integer, primary_key=True)
    editor_id = db.Column(db.Integer, db.ForeignKey('editors.id'), nullable=False)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)  # 변경한 사용자
    old_basic_rate = db.Column(db.Integer)
    new_basic_rate = db.Column(db.Integer)
    old_japanese_rate = db.Column(db.Integer)
    new_japanese_rate = db.Column(db.Integer)
    change_reason = db.Column(db.String(200))  # 변경 사유
    effective_date = db.Column(db.Date, nullable=False)  # 적용일
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정
    editor = db.relationship('Editor', backref='rate_history')
    changed_by_user = db.relationship('User', backref='rate_changes')
    
    def to_dict(self):
        return {
            'id': self.id,
            'editor_id': self.editor_id,
            'editor_name': self.editor.name if self.editor else None,
            'changed_by': self.changed_by_user.name if self.changed_by_user else None,
            'old_basic_rate': self.old_basic_rate,
            'new_basic_rate': self.new_basic_rate,
            'old_japanese_rate': self.old_japanese_rate,
            'new_japanese_rate': self.new_japanese_rate,
            'change_reason': self.change_reason,
            'effective_date': self.effective_date.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class Work(db.Model):
    """작업 모델"""
    __tablename__ = 'works'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    editor_id = db.Column(db.Integer, db.ForeignKey('editors.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    work_type = db.Column(db.String(20), nullable=False)  # basic, japanese
    work_date = db.Column(db.Date, nullable=False)
    deadline = db.Column(db.Date)
    rate = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    user = db.relationship('User', backref='works')
    
    def to_dict(self):
        return {
            'id': self.id,
            'editor_id': self.editor_id,
            'editor_name': self.editor.name if self.editor else None,
            'title': self.title,
            'work_type': self.work_type,
            'work_date': self.work_date.isoformat(),
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'rate': self.rate,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Revenue(db.Model):
    """수익 모델"""
    __tablename__ = 'revenues'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    year_month = db.Column(db.String(7), nullable=False)  # YYYY-MM 형식
    youtube_revenue = db.Column(db.Integer, default=0)  # 유튜브 수익
    music_revenue = db.Column(db.Integer, default=0)  # 음원 수익
    other_revenue = db.Column(db.Integer, default=0)  # 기타 수익
    total_revenue = db.Column(db.Integer, default=0)  # 총 수익
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 관계 설정
    user = db.relationship('User', backref='revenues')
    
    def to_dict(self):
        return {
            'id': self.id,
            'year_month': self.year_month,
            'youtube_revenue': self.youtube_revenue,
            'music_revenue': self.music_revenue,
            'other_revenue': self.other_revenue,
            'total_revenue': self.total_revenue,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class EmailSentVideo(db.Model):
    """이메일 발송 영상 이력 모델"""
    __tablename__ = 'email_sent_videos'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.String(50), nullable=False)  # YouTube 영상 ID
    video_title = db.Column(db.String(255), nullable=False)  # 영상 제목
    channel_title = db.Column(db.String(255), nullable=False)  # 채널명
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # 발송 일시
    
    # 관계 설정
    user = db.relationship('User', backref='sent_videos')
    
    # 복합 인덱스 설정 (사용자별 영상 ID 조회 최적화)
    __table_args__ = (
        db.Index('idx_user_video', 'user_id', 'video_id'),
        db.Index('idx_user_sent_at', 'user_id', 'sent_at'),
    )

class YoutubeDashboard(db.Model):
    """대시보드 통계 캐시 모델"""
    __tablename__ = 'youtube_dashboard'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), db.ForeignKey('user.id'), nullable=False)
    stats_date = db.Column(db.Date, nullable=False)
    total_editors = db.Column(db.Integer, default=0)
    week_works = db.Column(db.Integer, default=0)
    week_payment = db.Column(db.Integer, default=0)
    month_revenue = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='dashboard_stats')
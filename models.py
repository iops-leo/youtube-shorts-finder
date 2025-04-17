from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.String(128), primary_key=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    picture = db.Column(db.String(256))
    role = db.Column(db.String(20), default='pending')
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

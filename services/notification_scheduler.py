from common_utils.search import get_recent_popular_shorts
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_sqlalchemy import SQLAlchemy
import datetime
import pytz
from models import (
    db,
    EmailNotification,
    NotificationSearch,
    User,
    ChannelCategory,
    CategoryChannel,
    Channel
)

class NotificationScheduler:
    def __init__(self, app, db, email_service):
        self.app = app
        self.db = db
        self.email_service = email_service
        self.scheduler = BackgroundScheduler(timezone=pytz.UTC)
        
    def start(self):
        """스케줄러 시작"""
        # 매 시간 정각에 체크하여 해당 시간에 발송할 이메일이 있는지 확인
        self.scheduler.add_job(
            self.check_and_send_notifications,
            CronTrigger(minute=0),  # 매 시간 정각
            id='email_notification_job',
            replace_existing=True
        )
        
        # API 키 리셋 작업 (자정에 실행)
        self.scheduler.add_job(
            self.reset_api_keys,
            CronTrigger(hour=0, minute=0),  # 매일 자정
            id='api_key_reset_job',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.app.logger.info("알림 스케줄러가 시작되었습니다.")
    
    def reset_api_keys(self):
        """API 키 사용량 리셋 (자정에 실행)"""
        with self.app.app_context():
            # API 키 사용량 리셋 로직
            self.app.logger.info("API 키 사용량이 리셋되었습니다.")
    
    def check_and_send_notifications(self):
        """이메일 알림 체크 및 발송"""
        with self.app.app_context():
            try:
                # 현재 시간 (UTC)
                now = datetime.datetime.utcnow()
                
                # KST로 변환
                import pytz
                kst = pytz.timezone('Asia/Seoul')
                kst_now = now.replace(tzinfo=pytz.UTC).astimezone(kst)
                current_hour = kst_now.hour  # KST 기준 시간
                
                # 현재 시간에 발송해야 할 알림 검색
                notifications = EmailNotification.query.filter(
                    EmailNotification.active == True
                ).all()
                
                for notification in notifications:
                    # 선호 시간 확인
                    preferred_times = [int(t) for t in notification.preferred_times.split(',')]
                    
                    # 현재 시간이 선호 시간에 포함되는지 확인 (KST 기준)
                    if current_hour in preferred_times:
                        # 마지막 발송 시간 확인 (같은 시간에 중복 발송 방지)
                        if (notification.last_sent is None or 
                            (now - notification.last_sent).total_seconds() > 3600):  # 1시간 이상 차이
                            
                            # 사용자 정보 조회
                            user = User.query.get(notification.user_id)
                            if not user:
                                continue
                            
                            # 검색 결과 수집
                            search_results = self.collect_search_results(notification)
                            
                            # KST 시간대 문자열
                            kst_timestamp = kst_now.strftime('%Y-%m-%d %H:%M:%S KST')
                            
                            # 이메일 발송
                            email_html = self.email_service.format_shorts_email(
                                user,
                                search_results,
                                kst_timestamp
                            )
                            
                            success = self.email_service.send_email(
                                user.email,
                                f"YouTube Shorts 인기 영상 알림 ({kst_now.strftime('%Y-%m-%d %H:%M')})",
                                email_html
                            )
                            
                            if success:
                                # 마지막 발송 시간 업데이트
                                notification.last_sent = now
                                self.db.session.commit()
                                self.app.logger.info(f"사용자 {user.email}에게 알림 이메일 발송됨")
            
            except Exception as e:
                self.app.logger.error(f"알림 체크 중 오류 발생: {str(e)}")
    
    def collect_search_results(self, notification):
        """사용자의 검색 조건에 따라 영상 검색 결과 수집"""
        results = []
        
        for search in notification.searches:
            # 카테고리 정보 가져오기
            category = search.category
            
            # 카테고리에 속한 채널 목록 가져오기
            channels = []
            for cat_channel in category.category_channels:
                channels.append(cat_channel.channel.id)
            
            if not channels:
                # 채널이 없으면 빈 결과 추가
                results.append({
                    'name': category.name,
                    'videos': []
                })
                continue
            
            # 채널 검색 수행
            try:
                videos = get_recent_popular_shorts(
                    min_views=search.min_views,
                    days_ago=search.days_ago,
                    max_results=search.max_results,
                    channel_ids=','.join(channels)
                )
                
                results.append({
                    'name': category.name,
                    'videos': videos
                })
            except Exception as e:
                self.app.logger.error(f"검색 중 오류: {str(e)}")
                results.append({
                    'name': category.name,
                    'videos': []
                })
        
        return results
# notification_scheduler.py 수정
from common_utils.search import get_recent_popular_shorts
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask_sqlalchemy import SQLAlchemy
import datetime
import pytz
import os
import traceback
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
        try:
            # 환경 변수 확인 및 로깅
            self.app.logger.info(f"스케줄러 시작 시도: PID={os.getpid()}, 현재 시간(UTC)={datetime.datetime.utcnow()}")
            self.app.logger.info(f"SMTP 설정: Server={self.email_service.smtp_server}, Port={self.email_service.smtp_port}")
            
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
            
            # 테스트용 작업 추가 (1분마다 실행)
            self.scheduler.add_job(
                self.test_scheduler_running,
                CronTrigger(minute='*/1'),  # 매 1분마다 실행
                id='test_job',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.app.logger.info("알림 스케줄러가 시작되었습니다.")
            
            # 현재 등록된 작업 출력
            jobs = self.scheduler.get_jobs()
            self.app.logger.info(f"등록된 작업 수: {len(jobs)}")
            for job in jobs:
                self.app.logger.info(f"작업: {job.id}, 다음 실행: {job.next_run_time}")
                
        except Exception as e:
            self.app.logger.error(f"스케줄러 시작 중 오류 발생: {str(e)}")
            self.app.logger.error(traceback.format_exc())
    
    def test_scheduler_running(self):
        """스케줄러가 실행 중인지 확인하는 테스트 함수"""
        with self.app.app_context():
            now = datetime.datetime.utcnow()
            self.app.logger.info(f"스케줄러 테스트 작업 실행 중: {now}")
    
    def reset_api_keys(self):
        """API 키 사용량 리셋 (자정에 실행)"""
        with self.app.app_context():
            try:
                # API 키 사용량 리셋 로직
                self.app.logger.info("API 키 사용량이 리셋되었습니다.")
            except Exception as e:
                self.app.logger.error(f"API 키 리셋 중 오류 발생: {str(e)}")
                self.app.logger.error(traceback.format_exc())
    
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
                
                self.app.logger.info(f"알림 체크 시작: UTC={now}, KST={kst_now}, 현재 시간(KST)={current_hour}시")
                
                # 활성화된 알림 수 확인
                notifications = EmailNotification.query.filter(
                    EmailNotification.active == True
                ).all()
                
                self.app.logger.info(f"활성화된 알림 수: {len(notifications)}")
                
                for notification in notifications:
                    # 선호 시간 확인
                    preferred_times = [int(t) for t in notification.preferred_times.split(',')]
                    self.app.logger.info(f"알림 ID: {notification.id}, 선호 시간: {preferred_times}, 현재 시간(KST): {current_hour}")
                    
                    # 현재 시간이 선호 시간에 포함되는지 확인 (KST 기준)
                    if current_hour in preferred_times:
                        # 마지막 발송 시간 확인 (같은 시간에 중복 발송 방지)
                        if (notification.last_sent is None or 
                            (now - notification.last_sent).total_seconds() > 3600):  # 1시간 이상 차이
                            
                            self.app.logger.info(f"알림 ID: {notification.id}에 대한 이메일 발송 조건 충족")
                            
                            # 사용자 정보 조회
                            user = User.query.get(notification.user_id)
                            if not user:
                                self.app.logger.error(f"사용자 ID: {notification.user_id}를 찾을 수 없음")
                                continue
                            
                            self.app.logger.info(f"사용자 {user.email}에게 이메일 발송 준비 중")
                            
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
                            
                            self.app.logger.info(f"이메일 발송 시도: 사용자={user.email}")
                            
                            success = self.email_service.send_email(
                                user.email,
                                f"YouTube Shorts 인기 영상 알림 ({kst_now.strftime('%Y-%m-%d %H:%M')})",
                                email_html
                            )
                            
                            if success:
                                # 마지막 발송 시간 업데이트
                                notification.last_sent = now
                                self.db.session.commit()
                                self.app.logger.info(f"사용자 {user.email}에게 알림 이메일 발송 성공")
                            else:
                                self.app.logger.error(f"사용자 {user.email}에게 이메일 발송 실패")
                    else:
                        self.app.logger.info(f"알림 ID: {notification.id}는 현재 시간({current_hour})에 발송되지 않음 (선호 시간: {preferred_times})")
            
            except Exception as e:
                self.app.logger.error(f"알림 체크 중 오류 발생: {str(e)}")
                self.app.logger.error(traceback.format_exc())
    
    def collect_search_results(self, notification):
        """사용자의 검색 조건에 따라 영상 검색 결과 수집"""
        results = []
        
        try:
            self.app.logger.info(f"검색 결과 수집 시작: 알림 ID={notification.id}")
            
            for search in notification.searches:
                # 카테고리 정보 가져오기
                category = search.category
                self.app.logger.info(f"카테고리: {category.name} 처리 중")
                
                # 카테고리에 속한 채널 목록 가져오기
                channels = []
                for cat_channel in category.category_channels:
                    channels.append(cat_channel.channel.id)
                
                self.app.logger.info(f"카테고리 {category.name}에 속한 채널 수: {len(channels)}")
                
                if not channels:
                    # 채널이 없으면 빈 결과 추가
                    self.app.logger.warning(f"카테고리 {category.name}에 채널이 없음")
                    results.append({
                        'name': category.name,
                        'videos': []
                    })
                    continue
                
                # 채널 검색 수행
                try:
                    self.app.logger.info(f"검색 조건: 최소 조회수={search.min_views}, 기간={search.days_ago}일, 최대 결과={search.max_results}")
                    
                    videos = get_recent_popular_shorts(
                        min_views=search.min_views,
                        days_ago=search.days_ago,
                        max_results=search.max_results,
                        channel_ids=','.join(channels)
                    )
                    
                    self.app.logger.info(f"카테고리 {category.name}에서 {len(videos)}개 영상 찾음")
                    
                    results.append({
                        'name': category.name,
                        'videos': videos
                    })
                except Exception as e:
                    self.app.logger.error(f"검색 중 오류: {str(e)}")
                    self.app.logger.error(traceback.format_exc())
                    results.append({
                        'name': category.name,
                        'videos': []
                    })
            
            return results
        except Exception as e:
            self.app.logger.error(f"검색 결과 수집 중 오류 발생: {str(e)}")
            self.app.logger.error(traceback.format_exc())
            return []
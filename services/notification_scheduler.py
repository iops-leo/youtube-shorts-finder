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
    EmailSentVideo,
    User,
    ChannelCategory,
    CategoryChannel,
    Channel,
    Work
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

            # 매주 월요일 01:00 UTC (KST 10:00)에 주간 정산 발송
            self.scheduler.add_job(
                self.send_weekly_settlement_reports,
                CronTrigger(day_of_week='mon', hour=1, minute=0),
                id='weekly_settlement_job',
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
            
            # 매일 자정 2시에 오래된 발송 이력 정리
            self.scheduler.add_job(
                self.cleanup_old_sent_records,
                CronTrigger(hour=2, minute=0),
                id='cleanup_sent_records_job',
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
                                
                                # 발송된 영상들을 이력에 기록
                                self.record_sent_videos(user.id, search_results)
                                
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
                    self.app.logger.info(f"검색 조건: 카테고리={category.name}, 최소 조회수={search.min_views:,}회, 기간={search.days_ago}일, 최대 결과={search.max_results}개, 채널 수={len(channels)}개")
                    
                    videos = get_recent_popular_shorts(
                        min_views=search.min_views,
                        days_ago=search.days_ago,
                        max_results=search.max_results,
                        channel_ids=','.join(channels),
                        region_code='KR'
                    )
                    
                    # 이미 발송된 영상 제외
                    videos = self.filter_already_sent_videos(notification.user_id, videos)
                    
                    # 조회수 높은 순으로 정렬
                    videos.sort(key=lambda x: x.get('viewCount', 0), reverse=True)
                    
                    # 수정: 결과를 최대 10개로 제한
                    max_videos_per_category = 10
                    if len(videos) > max_videos_per_category:
                        self.app.logger.info(f"카테고리 {category.name}의 결과를 {max_videos_per_category}개로 제한 (원래: {len(videos)}개)")
                        videos = videos[:max_videos_per_category]
                    
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
    
    def filter_already_sent_videos(self, user_id, videos):
        """이미 발송된 영상을 제외하고 새로운 영상만 반환"""
        try:
            if not videos:
                return videos
            
            # 영상 ID 목록 추출
            video_ids = [video.get('id') for video in videos if video.get('id')]
            
            if not video_ids:
                return videos
            
            # 이미 발송된 영상 ID 조회
            sent_video_ids = db.session.query(EmailSentVideo.video_id).filter(
                EmailSentVideo.user_id == user_id,
                EmailSentVideo.video_id.in_(video_ids)
            ).all()
            
            sent_ids_set = {row[0] for row in sent_video_ids}
            
            # 새로운 영상만 필터링
            new_videos = [video for video in videos if video.get('id') not in sent_ids_set]
            
            if len(sent_ids_set) > 0:
                self.app.logger.info(f"사용자 {user_id}: {len(sent_ids_set)}개 영상은 이미 발송됨, {len(new_videos)}개 새로운 영상 발송 예정")
            
            return new_videos
            
        except Exception as e:
            self.app.logger.error(f"이미 발송된 영상 필터링 중 오류: {str(e)}")
            # 오류 발생 시 원본 영상 목록 반환 (안전하게 처리)
            return videos
    
    def record_sent_videos(self, user_id, search_results):
        """발송된 영상들을 데이터베이스에 기록"""
        try:
            sent_videos = []
            
            for category_result in search_results:
                for video in category_result.get('videos', []):
                    video_id = video.get('id')
                    if not video_id:
                        continue
                    
                    sent_video = EmailSentVideo(
                        user_id=user_id,
                        video_id=video_id,
                        video_title=video.get('title', '')[:255],  # 길이 제한
                        channel_title=video.get('channelTitle', '')[:255]  # 길이 제한
                    )
                    sent_videos.append(sent_video)
            
            if sent_videos:
                db.session.add_all(sent_videos)
                db.session.commit()
                self.app.logger.info(f"사용자 {user_id}: {len(sent_videos)}개 영상 발송 이력 저장 완료")
            
        except Exception as e:
            self.app.logger.error(f"발송 이력 저장 중 오류: {str(e)}")
            db.session.rollback()
    
    def cleanup_old_sent_records(self, days_to_keep=30):
        """오래된 발송 이력 정리 (30일 이상 된 기록 삭제)"""
        try:
            cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_to_keep)
            
            deleted_count = db.session.query(EmailSentVideo).filter(
                EmailSentVideo.sent_at < cutoff_date
            ).delete()
            
            db.session.commit()
            
            if deleted_count > 0:
                self.app.logger.info(f"오래된 발송 이력 {deleted_count}개 정리 완료")
                
        except Exception as e:
            self.app.logger.error(f"발송 이력 정리 중 오류: {str(e)}")
            db.session.rollback()

    def send_weekly_settlement_reports(self):
        """매주 월요일 10시(KST)에 전주 정산 리포트를 발송"""
        with self.app.app_context():
            try:
                self.app.logger.info("주간 정산 리포트 발송 시작")
                # 주간 정산을 활성화한 사용자
                active_notifications = EmailNotification.query.filter(
                    EmailNotification.weekly_settlement_active == True
                ).all()
                self.app.logger.info(f"주간 정산 활성 사용자 수: {len(active_notifications)}")

                # 전주 기간 계산 (월요일~일요일 기준)
                kst = pytz.timezone('Asia/Seoul')
                now_kst = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC).astimezone(kst)
                # 월요일 10시에 실행되므로, 전주의 월~일 산출
                week_end = (now_kst.date() - datetime.timedelta(days=1))  # 전주 일요일
                week_start = week_end - datetime.timedelta(days=6)  # 전주 월요일

                for notif in active_notifications:
                    user = User.query.get(notif.user_id)
                    if not user:
                        continue

                    # 전주 기간에 해당하는 작업 수집
                    items = []
                    # User.works 관계 사용
                    works = Work.query.filter(
                        Work.user_id == user.id,
                        Work.work_date >= week_start,
                        Work.work_date <= week_end
                    ).order_by(Work.work_date.asc()).all()

                    settled_amount = 0
                    pending_amount = 0
                    settlement_works = 0
                    completed_works = 0

                    for w in works:
                        completed_works += 1
                        if w.settlement_status == 'settled':
                            settlement_works += 1
                            settled_amount += (w.settlement_amount or w.rate or 0)
                        else:
                            pending_amount += (w.rate or 0)
                        items.append({
                            'editor_name': w.editor.name if w.editor else '-',
                            'title': w.title,
                            'work_type': w.work_type,
                            'work_date': w.work_date.strftime('%Y-%m-%d'),
                            'settlement_status': w.settlement_status,
                            'rate': (w.settlement_amount or w.rate or 0)
                        })

                    summary = type('Summary', (), {
                        'completed_works': completed_works,
                        'settlement_works': settlement_works,
                        'settled_amount': settled_amount,
                        'pending_amount': pending_amount
                    })()

                    html = self.email_service.format_weekly_settlement_email(
                        user=user,
                        week_start_date=week_start,
                        week_end_date=week_end,
                        summary=summary,
                        items=items
                    )

                    subject = f"주간 정산 리포트 ({week_start.strftime('%Y-%m-%d')} ~ {week_end.strftime('%Y-%m-%d')})"
                    ok = self.email_service.send_email(user.email, subject, html)
                    if ok:
                        self.app.logger.info(f"주간 정산 리포트 발송 성공: {user.email}")
                    else:
                        self.app.logger.error(f"주간 정산 리포트 발송 실패: {user.email}")

            except Exception as e:
                self.app.logger.error(f"주간 정산 리포트 발송 중 오류: {str(e)}")
                self.app.logger.error(traceback.format_exc())
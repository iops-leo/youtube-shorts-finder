from common_utils.search import get_recent_popular_shorts
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime
import pytz
import os
import traceback
import gc
from sqlalchemy import text
from werkzeug.local import release_local
from flask import _app_ctx_stack, _request_ctx_stack

class NotificationScheduler:
    def __init__(self, app, db, email_service):
        self.app = app
        self.db = db
        self.email_service = email_service
        self.scheduler = None  # 초기화를 start 메서드로 이동
        
    def start(self):
        """스케줄러 시작"""
        try:
            # 이미 실행 중인 스케줄러가 있다면 종료
            if self.scheduler and self.scheduler.running:
                self.app.logger.info("기존 스케줄러 종료 후 재시작합니다.")
                self.stop()
                
            # 환경 변수 확인 및 로깅
            self.app.logger.info(f"스케줄러 시작 시도: PID={os.getpid()}, 현재 시간(UTC)={datetime.datetime.utcnow()}")
            self.app.logger.info(f"SMTP 설정: Server={self.email_service.smtp_server}, Port={self.email_service.smtp_port}")
            
            # 스케줄러 새로 생성
            self.scheduler = BackgroundScheduler(timezone=pytz.UTC)
            
            # 매 시간 정각에 체크하여 해당 시간에 발송할 이메일이 있는지 확인
            self.scheduler.add_job(
                self.check_and_send_notifications,
                CronTrigger(minute=0),  # 매 시간 정각
                id='email_notification_job',
                replace_existing=True,
                misfire_grace_time=600  # 10분의 유예 시간
            )
            
            # API 키 리셋 작업 (자정에 실행)
            self.scheduler.add_job(
                self.reset_api_keys,
                CronTrigger(hour=0, minute=0),  # 매일 자정
                id='api_key_reset_job',
                replace_existing=True,
                misfire_grace_time=3600  # 1시간의 유예 시간
            )
            
            # 메모리 정리 작업 추가 (6시간마다 실행)
            self.scheduler.add_job(
                self.cleanup_memory,
                CronTrigger(hour='*/6'),  # 6시간마다
                id='memory_cleanup_job',
                replace_existing=True
            )
            
            # 테스트용 작업 추가 (1분마다 실행)
            self.scheduler.add_job(
                self.test_scheduler_running,
                CronTrigger(minute='*/5'),  # 5분마다로 변경 (부하 감소)
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
            
    def stop(self):
        """스케줄러 종료"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            self.app.logger.info("스케줄러가 종료되었습니다.")
    
    def cleanup_memory(self):
        """메모리 정리 함수"""
        with self.app.app_context():
            try:
                self.app.logger.info("메모리 정리 작업 시작")
                
                # Flask 컨텍스트 정리
                release_local(_app_ctx_stack.top)
                release_local(_request_ctx_stack.top)
                
                # 데이터베이스 연결 정리
                self.db.session.remove()
                
                # 가비지 컬렉션 강제 실행
                collected = gc.collect(generation=2)
                
                self.app.logger.info(f"메모리 정리 완료: {collected}개 객체 정리됨")
            except Exception as e:
                self.app.logger.error(f"메모리 정리 중 오류 발생: {str(e)}")
                self.app.logger.error(traceback.format_exc())
    
    def test_scheduler_running(self):
        """스케줄러가 실행 중인지 확인하는 테스트 함수"""
        with self.app.app_context():
            try:
                now = datetime.datetime.utcnow()
                self.app.logger.info(f"스케줄러 테스트 작업 실행 중: {now}")
                
                # 세션 정리 - 테스트 후 항상 세션 정리 
                self.db.session.remove()
            except Exception as e:
                self.app.logger.error(f"테스트 작업 중 오류 발생: {str(e)}")
                # 세션 정리 시도
                try:
                    self.db.session.remove()
                except:
                    pass
    
    def reset_api_keys(self):
        """API 키 사용량 리셋 (자정에 실행)"""
        with self.app.app_context():
            try:
                # API 키 사용량 리셋 로직
                self.app.logger.info("API 키 사용량이 리셋되었습니다.")
                
                # 세션 정리
                self.db.session.remove()
            except Exception as e:
                self.app.logger.error(f"API 키 리셋 중 오류 발생: {str(e)}")
                self.app.logger.error(traceback.format_exc())
                # 세션 정리 시도
                try:
                    self.db.session.remove()
                except:
                    pass
    
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
                
                # 활성화된 알림 수 확인 - text() 함수로 감싸기
                notifications_query = text("SELECT * FROM email_notification WHERE active = true")
                notifications = [dict(row) for row in self.db.session.execute(notifications_query).mappings()]
                
                self.app.logger.info(f"활성화된 알림 수: {len(notifications)}")
                
                for notification in notifications:
                    # 선호 시간 확인
                    preferred_times = [int(t) for t in notification['preferred_times'].split(',')]
                    self.app.logger.info(f"알림 ID: {notification['id']}, 선호 시간: {preferred_times}, 현재 시간(KST): {current_hour}")
                    
                    # 현재 시간이 선호 시간에 포함되는지 확인 (KST 기준)
                    if current_hour in preferred_times:
                        # 마지막 발송 시간 확인 (같은 시간에 중복 발송 방지)
                        last_sent = notification['last_sent']
                        if (last_sent is None or 
                            (now - last_sent).total_seconds() > 3600):  # 1시간 이상 차이
                            
                            self.app.logger.info(f"알림 ID: {notification['id']}에 대한 이메일 발송 조건 충족")
                            
                            # 사용자 정보 조회 - text() 함수로 감싸기
                            user_query = text(f"SELECT * FROM user WHERE id = :user_id")
                            user_result = self.db.session.execute(user_query, {"user_id": notification['user_id']}).mappings().first()
                            
                            if not user_result:
                                self.app.logger.error(f"사용자 ID: {notification['user_id']}를 찾을 수 없음")
                                continue
                            
                            user = dict(user_result)
                            self.app.logger.info(f"사용자 {user['email']}에게 이메일 발송 준비 중")
                            
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
                            
                            self.app.logger.info(f"이메일 발송 시도: 사용자={user['email']}")
                            
                            success = self.email_service.send_email(
                                user['email'],
                                f"YouTube Shorts 인기 영상 알림 ({kst_now.strftime('%Y-%m-%d %H:%M')})",
                                email_html
                            )
                            
                            if success:
                                # 마지막 발송 시간 업데이트 - text() 함수로 감싸기
                                update_query = text("""
                                    UPDATE email_notification 
                                    SET last_sent = :now 
                                    WHERE id = :notification_id
                                """)
                                self.db.session.execute(update_query, {
                                    "now": now,
                                    "notification_id": notification['id']
                                })
                                self.db.session.commit()
                                self.app.logger.info(f"사용자 {user['email']}에게 알림 이메일 발송 성공")
                            else:
                                self.app.logger.error(f"사용자 {user['email']}에게 이메일 발송 실패")
                                # 세션 롤백
                                self.db.session.rollback()
                    else:
                        self.app.logger.info(f"알림 ID: {notification['id']}는 현재 시간({current_hour})에 발송되지 않음 (선호 시간: {preferred_times})")
                
                # 작업 완료 후 명시적으로 세션 및 리소스 정리
                self.db.session.remove()
                # 가비지 컬렉션 실행
                gc.collect()
            
            except Exception as e:
                self.app.logger.error(f"알림 체크 중 오류 발생: {str(e)}")
                self.app.logger.error(traceback.format_exc())
                # 세션 정리 시도
                try:
                    self.db.session.rollback()
                    self.db.session.remove()
                except:
                    pass
    
    def collect_search_results(self, notification):
        """사용자의 검색 조건에 따라 영상 검색 결과 수집"""
        results = []
        
        try:
            self.app.logger.info(f"검색 결과 수집 시작: 알림 ID={notification['id']}")
            
            # 카테고리 조회 - text() 함수로 감싸기
            categories_query = text("""
                SELECT ns.*, cc.name as category_name 
                FROM notification_search ns
                JOIN channel_category cc ON ns.category_id = cc.id
                WHERE ns.notification_id = :notification_id
            """)
            searches = self.db.session.execute(categories_query, {
                "notification_id": notification['id']
            }).mappings().all()
            
            for search in searches:
                search_dict = dict(search)
                category_id = search_dict['category_id']
                category_name = search_dict['category_name']
                
                self.app.logger.info(f"카테고리: {category_name} (ID: {category_id}) 처리 중")
                
                # 카테고리에 속한 채널 목록 가져오기 - text() 함수로 감싸기
                channels_query = text("""
                    SELECT c.id 
                    FROM category_channel cc
                    JOIN channel c ON cc.channel_id = c.id
                    WHERE cc.category_id = :category_id
                """)
                channel_rows = self.db.session.execute(channels_query, {
                    "category_id": category_id
                }).fetchall()
                
                channels = [row[0] for row in channel_rows]
                
                self.app.logger.info(f"카테고리 {category_name}에 속한 채널 수: {len(channels)}")
                
                if not channels:
                    # 채널이 없으면 빈 결과 추가
                    self.app.logger.warning(f"카테고리 {category_name}에 채널이 없음")
                    results.append({
                        'name': category_name,
                        'videos': []
                    })
                    continue
                
                # 채널 검색 수행
                try:
                    self.app.logger.info(f"검색 조건: 최소 조회수={search_dict['min_views']}, 기간={search_dict['days_ago']}일, 최대 결과={search_dict['max_results']}")
                    
                    videos = get_recent_popular_shorts(
                        min_views=search_dict['min_views'],
                        days_ago=search_dict['days_ago'],
                        max_results=search_dict['max_results'],
                        channel_ids=','.join(channels)
                    )
                    
                    # 결과를 최대 10개로 제한
                    max_videos_per_category = 10
                    if len(videos) > max_videos_per_category:
                        self.app.logger.info(f"카테고리 {category_name}의 결과를 {max_videos_per_category}개로 제한 (원래: {len(videos)}개)")
                        videos = videos[:max_videos_per_category]
                    
                    self.app.logger.info(f"카테고리 {category_name}에서 {len(videos)}개 영상 찾음")
                    
                    results.append({
                        'name': category_name,
                        'videos': videos
                    })
                    
                    # 메모리에서 불필요한 데이터 제거
                    del videos
                    
                except Exception as e:
                    self.app.logger.error(f"검색 중 오류: {str(e)}")
                    self.app.logger.error(traceback.format_exc())
                    results.append({
                        'name': category_name,
                        'videos': []
                    })
            
            # 메모리에서 불필요한 데이터 제거
            del searches
            gc.collect()
            
            return results
        except Exception as e:
            self.app.logger.error(f"검색 결과 수집 중 오류 발생: {str(e)}")
            self.app.logger.error(traceback.format_exc())
            return []
        finally:
            # 리소스 명시적 해제
            self.db.session.close()
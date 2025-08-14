# services/user_api_service.py
import os
import time
import googleapiclient.discovery
from datetime import datetime, date
from cryptography.fernet import Fernet
from flask import current_app
from models import db, UserApiKey, ApiKeyUsage, ApiKeyRotation
import logging

class UserApiKeyManager:
    """사용자별 API 키 관리 클래스"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.current_key = None
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
    def _get_or_create_encryption_key(self):
        """암호화 키 가져오기 또는 생성"""
        key = os.environ.get('API_ENCRYPTION_KEY')
        if not key:
            # 새 키 생성 (운영환경에서는 환경변수로 설정 필요)
            key = Fernet.generate_key().decode()
            current_app.logger.warning("⚠️ API_ENCRYPTION_KEY 환경변수가 설정되지 않아 임시 키를 생성했습니다.")
        return key.encode() if isinstance(key, str) else key
    
    def encrypt_api_key(self, api_key):
        """API 키 암호화"""
        return self.cipher.encrypt(api_key.encode()).decode()
    
    def decrypt_api_key(self, encrypted_key):
        """API 키 복호화"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def add_api_key(self, name, api_key, daily_quota=10000):
        """새 API 키 추가"""
        try:
            # API 키 유효성 검증
            if not self._validate_api_key(api_key):
                return False, "유효하지 않은 YouTube API 키입니다."
            
            # 중복 확인
            existing = UserApiKey.query.filter_by(
                user_id=self.user_id,
                api_key=self.encrypt_api_key(api_key)
            ).first()
            
            if existing:
                return False, "이미 등록된 API 키입니다."
            
            # 이름 중복 확인
            name_exists = UserApiKey.query.filter_by(
                user_id=self.user_id,
                name=name
            ).first()
            
            if name_exists:
                return False, "이미 사용중인 이름입니다."
            
            # 새 API 키 생성
            new_key = UserApiKey(
                user_id=self.user_id,
                name=name,
                api_key=self.encrypt_api_key(api_key),
                daily_quota=daily_quota
            )
            
            db.session.add(new_key)
            db.session.commit()
            
            current_app.logger.info(f"사용자 {self.user_id}가 새 API 키를 추가했습니다: {name}")
            return True, "API 키가 성공적으로 추가되었습니다."
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"API 키 추가 중 오류: {str(e)}")
            return False, "API 키 추가 중 오류가 발생했습니다."
    
    def _validate_api_key(self, api_key):
        """API 키 유효성 검증"""
        try:
            youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
            # 간단한 테스트 요청
            youtube.search().list(part="snippet", q="test", type="video", maxResults=1).execute()
            return True
        except Exception as e:
            error_str = str(e).lower()
            # API 키가 잘못되었거나 권한이 없는 경우
            if 'api key not valid' in error_str or 'forbidden' in error_str:
                return False
            # 할당량 초과는 유효한 키로 간주
            if 'quota' in error_str or 'exceeded' in error_str:
                return True
            return False
    
    def get_user_api_keys(self):
        """사용자의 모든 API 키 조회"""
        keys = UserApiKey.query.filter_by(user_id=self.user_id).order_by(UserApiKey.created_at).all()
        
        # 일일 사용량 리셋 확인
        for key in keys:
            key.reset_daily_usage()
        
        return [key.to_dict(include_key=True) for key in keys]
    
    def update_api_key(self, key_id, name=None, daily_quota=None, is_active=None):
        """API 키 정보 업데이트"""
        try:
            api_key = UserApiKey.query.filter_by(id=key_id, user_id=self.user_id).first()
            if not api_key:
                return False, "API 키를 찾을 수 없습니다."
            
            # 이름 중복 확인
            if name and name != api_key.name:
                name_exists = UserApiKey.query.filter_by(
                    user_id=self.user_id,
                    name=name
                ).filter(UserApiKey.id != key_id).first()
                
                if name_exists:
                    return False, "이미 사용중인 이름입니다."
                
                api_key.name = name
            
            if daily_quota is not None:
                api_key.daily_quota = max(1000, min(50000, daily_quota))  # 1,000 ~ 50,000 제한
            
            if is_active is not None:
                api_key.is_active = is_active
            
            api_key.updated_at = datetime.utcnow()
            db.session.commit()
            
            current_app.logger.info(f"사용자 {self.user_id}가 API 키를 업데이트했습니다: {api_key.name}")
            return True, "API 키가 성공적으로 업데이트되었습니다."
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"API 키 업데이트 중 오류: {str(e)}")
            return False, "API 키 업데이트 중 오류가 발생했습니다."
    
    def delete_api_key(self, key_id):
        """API 키 삭제"""
        try:
            api_key = UserApiKey.query.filter_by(id=key_id, user_id=self.user_id).first()
            if not api_key:
                return False, "API 키를 찾을 수 없습니다."
            
            key_name = api_key.name
            db.session.delete(api_key)
            db.session.commit()
            
            current_app.logger.info(f"사용자 {self.user_id}가 API 키를 삭제했습니다: {key_name}")
            return True, "API 키가 성공적으로 삭제되었습니다."
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"API 키 삭제 중 오류: {str(e)}")
            return False, "API 키 삭제 중 오류가 발생했습니다."
    
    def get_available_api_key(self):
        """사용 가능한 API 키 반환 (순환 로직 포함)"""
        # 활성화된 API 키들 조회 (사용량이 적은 순으로 정렬)
        available_keys = UserApiKey.query.filter_by(
            user_id=self.user_id,
            is_active=True
        ).order_by(
            UserApiKey.usage_count,
            UserApiKey.error_count,
            UserApiKey.id
        ).all()
        
        # 사용자 개인 키가 있는 경우 우선 사용
        if available_keys:
            # 일일 사용량 리셋 및 건강한 키 찾기
            for key in available_keys:
                key.reset_daily_usage()
                if key.is_healthy() and not key.is_quota_exceeded():
                    self.current_key = key
                    return self.decrypt_api_key(key.api_key)
        
        # 개인 키가 없거나 모두 사용불가한 경우 시스템 키 사용
        return self._get_system_fallback_key()
    
    def _get_system_fallback_key(self):
        """시스템 기본 API 키 사용 (Railway 환경변수)"""
        try:
            # 기존 시스템의 할당량 관리자 사용
            from common_utils.quota_manager import get_quota_manager
            quota_manager = get_quota_manager()
            
            if quota_manager and quota_manager.has_available_quota():
                system_key = quota_manager.get_current_api_key()
                if system_key:
                    current_app.logger.info(f"사용자 {self.user_id}: 시스템 API 키 사용 (개인 키 없음)")
                    self.current_key = None  # 시스템 키 사용 시 current_key는 None
                    return system_key
        except Exception as e:
            current_app.logger.error(f"시스템 API 키 접근 중 오류: {str(e)}")
        
        return None
    
    def switch_to_next_key(self, reason="quota_exceeded"):
        """다음 API 키로 전환"""
        current_key_id = self.current_key.id if self.current_key else None
        
        # 다음 사용 가능한 키 찾기
        next_key_value = self.get_available_api_key()
        
        if next_key_value and self.current_key:
            # 순환 로그 기록
            rotation = ApiKeyRotation(
                user_id=self.user_id,
                from_key_id=current_key_id,
                to_key_id=self.current_key.id,
                reason=reason
            )
            db.session.add(rotation)
            db.session.commit()
            
            current_app.logger.info(f"사용자 {self.user_id} API 키 순환: {self.current_key.name} (이유: {reason})")
            
        return next_key_value
    
    def record_api_usage(self, endpoint, quota_cost=1, success=True, error_message=None, response_time=None):
        """API 사용 기록"""
        # 시스템 키 사용 시에는 기록하지 않음
        if not self.current_key:
            return
        
        try:
            # 사용량 증가
            if success:
                self.current_key.increment_usage()
            else:
                self.current_key.record_error(error_message or "Unknown error")
            
            # 사용 이력 기록
            usage_log = ApiKeyUsage(
                api_key_id=self.current_key.id,
                user_id=self.user_id,
                endpoint=endpoint,
                quota_cost=quota_cost,
                success=success,
                error_message=error_message,
                response_time=response_time
            )
            
            db.session.add(usage_log)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"API 사용 기록 중 오류: {str(e)}")
    
    def get_usage_statistics(self, days=7):
        """사용 통계 조회"""
        from sqlalchemy import func
        from datetime import timedelta
        
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # 일별 사용량
            daily_usage = db.session.query(
                func.date(ApiKeyUsage.timestamp).label('date'),
                func.count().label('total_calls'),
                func.sum(func.case([(ApiKeyUsage.success == True, 1)], else_=0)).label('successful_calls'),
                func.avg(ApiKeyUsage.response_time).label('avg_response_time')
            ).filter(
                ApiKeyUsage.user_id == self.user_id,
                ApiKeyUsage.timestamp >= start_date
            ).group_by(func.date(ApiKeyUsage.timestamp)).all()
            
            # API 키별 사용량
            key_usage = db.session.query(
                UserApiKey.name,
                func.count(ApiKeyUsage.id).label('total_calls'),
                func.sum(func.case([(ApiKeyUsage.success == True, 1)], else_=0)).label('successful_calls')
            ).join(ApiKeyUsage).filter(
                UserApiKey.user_id == self.user_id,
                ApiKeyUsage.timestamp >= start_date
            ).group_by(UserApiKey.id, UserApiKey.name).all()
            
            # 안전한 데이터 변환
            daily_usage_data = []
            for day in daily_usage:
                total_calls = int(day.total_calls) if day.total_calls else 0
                successful_calls = int(day.successful_calls) if day.successful_calls else 0
                avg_response_time = float(day.avg_response_time) if day.avg_response_time else 0.0
                
                daily_usage_data.append({
                    'date': day.date.isoformat(),
                    'total_calls': total_calls,
                    'successful_calls': successful_calls,
                    'success_rate': round((successful_calls / total_calls) * 100, 1) if total_calls > 0 else 0,
                    'avg_response_time': round(avg_response_time, 2)
                })
            
            key_usage_data = []
            for key in key_usage:
                total_calls = int(key.total_calls) if key.total_calls else 0
                successful_calls = int(key.successful_calls) if key.successful_calls else 0
                
                key_usage_data.append({
                    'key_name': key.name,
                    'total_calls': total_calls,
                    'successful_calls': successful_calls,
                    'success_rate': round((successful_calls / total_calls) * 100, 1) if total_calls > 0 else 0
                })
            
            return {
                'daily_usage': daily_usage_data,
                'key_usage': key_usage_data
            }
            
        except Exception as e:
            current_app.logger.error(f"사용 통계 조회 중 오류: {str(e)}")
            # 기본값 반환
            return {
                'daily_usage': [],
                'key_usage': []
            }
    
    def get_youtube_service(self):
        """YouTube API 서비스 인스턴스 반환"""
        api_key = self.get_available_api_key()
        if not api_key:
            raise Exception("사용 가능한 YouTube API 키가 없습니다. API 키를 추가하거나 할당량을 확인해주세요.")
        
        try:
            start_time = time.time()
            youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
            response_time = time.time() - start_time
            
            # 개인 키 사용 시에만 사용량 기록
            if self.current_key:
                self.record_api_usage("service.build", success=True, response_time=response_time)
            
            return youtube
            
        except Exception as e:
            response_time = time.time() - start_time
            
            # 개인 키 사용 시에만 오류 기록
            if self.current_key:
                self.record_api_usage("service.build", success=False, error_message=str(e), response_time=response_time)
            
            raise
    
    def execute_api_call(self, api_call_func, endpoint_name, quota_cost=1, max_retries=3):
        """API 호출 실행 (재시도 및 키 순환 로직 포함)"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result = api_call_func()
                response_time = time.time() - start_time
                
                # 성공 기록 (개인 키 사용 시에만)
                self.record_api_usage(endpoint_name, quota_cost, success=True, response_time=response_time)
                return result
                
            except Exception as e:
                response_time = time.time() - start_time
                error_str = str(e).lower()
                last_error = e
                
                # 할당량 초과 또는 키 오류인 경우
                if any(keyword in error_str for keyword in ['quota', 'exceeded', 'invalid', 'forbidden']):
                    # 오류 기록 (개인 키 사용 시에만)
                    self.record_api_usage(endpoint_name, quota_cost, success=False, 
                                        error_message=str(e), response_time=response_time)
                    
                    # 시스템 키 사용 중인 경우 시스템 할당량 관리자에 위임
                    if not self.current_key:
                        # 시스템 키를 사용하는 경우 기존 시스템 로직에 위임
                        try:
                            from common_utils.search import switch_to_next_api_key
                            next_system_key = switch_to_next_api_key()
                            if next_system_key and attempt < max_retries - 1:
                                current_app.logger.info(f"시스템 API 키 전환 후 재시도 ({attempt + 1}/{max_retries}): {endpoint_name}")
                                continue
                        except:
                            pass
                        
                        raise Exception("시스템 API 키 할당량이 초과되었습니다. 개인 API 키를 등록해주세요.")
                    
                    # 개인 키 사용 중인 경우 다음 개인 키로 전환 시도
                    next_key = self.switch_to_next_key("quota_exceeded" if 'quota' in error_str else "key_error")
                    
                    if next_key and attempt < max_retries - 1:
                        current_app.logger.info(f"개인 API 키 전환 후 재시도 ({attempt + 1}/{max_retries}): {endpoint_name}")
                        continue
                    else:
                        # 모든 개인 키 실패 시 시스템 키로 fallback
                        fallback_key = self._get_system_fallback_key()
                        if fallback_key and attempt < max_retries - 1:
                            current_app.logger.info(f"시스템 키로 fallback 재시도 ({attempt + 1}/{max_retries}): {endpoint_name}")
                            continue
                        
                        raise Exception("모든 API 키의 할당량이 초과되었거나 사용할 수 없습니다.")
                else:
                    # 다른 오류는 기록하고 재시도
                    self.record_api_usage(endpoint_name, quota_cost, success=False, 
                                        error_message=str(e), response_time=response_time)
                    
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 1초 대기 후 재시도
                        continue
                    else:
                        raise
        
        # 모든 재시도 실패
        raise last_error or Exception(f"API 호출 실패: {endpoint_name}")

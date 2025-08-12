# quota_manager.py
import os
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List, Tuple
from enum import Enum
import logging
from dataclasses import dataclass
from threading import Lock
import pytz

logger = logging.getLogger(__name__)

class QuotaErrorType(Enum):
    """할당량 오류 유형"""
    DAILY_QUOTA_EXCEEDED = "daily_quota_exceeded"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded" 
    API_KEY_INVALID = "api_key_invalid"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class APICall:
    """API 호출 정보"""
    endpoint: str
    cost: int
    timestamp: datetime
    key_index: int
    success: bool
    error_message: str = ""

@dataclass
class QuotaUsage:
    """할당량 사용량 정보"""
    daily_used: int = 0
    daily_limit: int = 10000  # YouTube Data API v3 기본 할당량
    reset_time: datetime = None
    rate_limit_remaining: int = 100  # 분당 요청 제한
    last_request_time: datetime = None
    warning_threshold: float = 0.9  # 90%
    # 추가 상태
    disabled: bool = False  # 키 비활성화(예: 잘못된 키)
    last_error_reason: str = ""  # 마지막 오류 이유 기록
    
    def get_usage_percentage(self) -> float:
        """할당량 사용률 반환"""
        if self.daily_limit <= 0:
            return 0.0
        return (self.daily_used / self.daily_limit) * 100

    def is_warning_level(self) -> bool:
        """경고 수준 도달 여부"""
        return self.get_usage_percentage() >= (self.warning_threshold * 100)
    
    def is_exceeded(self) -> bool:
        """할당량 초과 여부"""
        return self.daily_used >= self.daily_limit

class YouTubeQuotaManager:
    """YouTube API 할당량 관리자"""
    
    # YouTube Data API v3 cost 정의 (공식 문서 기준)
    API_COSTS = {
        'search.list': 100,
        'videos.list': 1,
        'channels.list': 1,
        'playlists.list': 1,
        'playlistItems.list': 1,
        'commentThreads.list': 1,
        'comments.list': 1,
    }
    
    def __init__(self, api_keys: List[str], daily_limit: int = 10000):
        self.api_keys = api_keys
        self.daily_limit = daily_limit
        self.current_key_index = 0
        self.quota_usage: Dict[int, QuotaUsage] = {}
        self.call_history: List[APICall] = []
        self.lock = Lock()
        
        # 각 API 키별 할당량 정보 초기화
        for i, _ in enumerate(api_keys):
            self.quota_usage[i] = QuotaUsage(
                daily_limit=daily_limit,
                reset_time=self._get_next_reset_time()
            )
        
        logger.info(f"YouTube 할당량 관리자 초기화: {len(api_keys)}개 키, 일일 한도: {daily_limit}")
    
    def _get_next_reset_time(self) -> datetime:
        """다음 할당량 리셋 시간 계산 (PST 자정 기준)"""
        pst = pytz.timezone('America/Los_Angeles')
        now = datetime.now(pst)
        tomorrow = now + timedelta(days=1)
        reset_time = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        return reset_time.astimezone(timezone.utc)
    
    def _is_key_available(self, index: int) -> bool:
        usage = self.quota_usage.get(index)
        if not usage:
            return False
        if usage.disabled:
            return False
        if usage.is_exceeded():
            return False
        return True
    
    def get_current_api_key(self) -> Optional[str]:
        """현재 사용할 API 키 반환"""
        if not self.api_keys:
            return None
        
        with self.lock:
            # 할당량 리셋 확인
            self._check_quota_reset()
            
            # 현재 키가 사용 가능한지 확인
            if self._is_key_available(self.current_key_index):
                return self.api_keys[self.current_key_index]
            
            # 사용 가능한 다른 키 찾기
            for i, key in enumerate(self.api_keys):
                if self._is_key_available(i):
                    self.current_key_index = i
                    logger.info(f"API 키 전환: 인덱스 {i}로 변경")
                    return key
            
            # 모든 키가 사용 불가한 경우
            logger.warning("모든 API 키가 사용 불가 상태입니다(소진/비활성).")
            return None
    
    def record_api_call(self, endpoint: str, success: bool = True, 
                       error_message: str = "", key_index: Optional[int] = None) -> int:
        """API 호출 기록 및 할당량 업데이트"""
        if key_index is None:
            key_index = self.current_key_index
            
        cost = self.API_COSTS.get(endpoint, 1)  # 기본 cost는 1
        now = datetime.now(timezone.utc)
        
        with self.lock:
            # 할당량 업데이트
            if key_index in self.quota_usage:
                usage = self.quota_usage[key_index]
                if success:
                    usage.daily_used += cost
                usage.last_request_time = now
                usage.last_error_reason = "" if success else (error_message or usage.last_error_reason)
                
                # 경고 레벨 체크
                if usage.is_warning_level() and not usage.is_exceeded():
                    self._send_quota_warning(key_index, usage)
            
            # 호출 이력 기록
            call = APICall(
                endpoint=endpoint,
                cost=cost,
                timestamp=now,
                key_index=key_index,
                success=success,
                error_message=error_message
            )
            self.call_history.append(call)
            
            # 이력 크기 제한 (최근 1000개만 보관)
            if len(self.call_history) > 1000:
                self.call_history = self.call_history[-1000:]
        
        return cost
    
    def switch_to_next_key(self) -> Optional[str]:
        """다음 사용 가능한 API 키로 전환"""
        with self.lock:
            # 현재 키 상태 로그
            if self.current_key_index in self.quota_usage:
                current_usage = self.quota_usage[self.current_key_index]
                status = []
                if current_usage.is_exceeded():
                    status.append("소진")
                if current_usage.disabled:
                    status.append("비활성")
                status_str = "/".join(status) if status else "사용 가능"
                logger.warning(
                    f"API 키 {self.current_key_index} 전환 - 상태: {status_str} - "
                    f"사용량: {current_usage.daily_used}/{current_usage.daily_limit}"
                )
            
            # 다음 사용 가능한 키 찾기
            start_index = self.current_key_index
            for _ in range(len(self.api_keys)):
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                if self._is_key_available(self.current_key_index):
                    new_key = self.api_keys[self.current_key_index]
                    logger.info(f"API 키 전환 성공: 인덱스 {self.current_key_index}")
                    return new_key
                    
            # 모든 키가 소진/비활성인 경우
            logger.error("사용 가능한 API 키가 없습니다")
            return None
    
    def handle_quota_error(self, error_message: str, endpoint: str = "") -> Tuple[QuotaErrorType, str]:
        """할당량 오류 처리 및 분석"""
        error_lower = (error_message or "").lower()
        
        # 할당량 초과 기록
        self.record_api_call(endpoint, success=False, error_message=error_message)
        
        # 오류 유형 분석 (googleapiclient HttpError 메시지 패턴 고려)
        # 대표 코드: quotaExceeded, dailyLimitExceeded, rateLimitExceeded, keyInvalid
        if any(k in error_lower for k in ['quotaexceeded', 'dailylimitexceeded']):
            error_type = QuotaErrorType.DAILY_QUOTA_EXCEEDED
        elif 'ratelimitexceeded' in error_lower or (
            'quota' in error_lower and 'exceeded' in error_lower and 'daily' not in error_lower
        ):
            error_type = QuotaErrorType.RATE_LIMIT_EXCEEDED
        elif any(k in error_lower for k in ['keyinvalid', 'api key not valid', 'api key not valid.', 'invalid key', 'invalid', 'forbidden', '403']):
            error_type = QuotaErrorType.API_KEY_INVALID
        else:
            error_type = QuotaErrorType.UNKNOWN_ERROR
        
        # 현재 키 상태 갱신 (유형별 조치)
        with self.lock:
            usage = self.quota_usage.get(self.current_key_index)
            if usage:
                usage.last_error_reason = error_type.value
                if error_type == QuotaErrorType.DAILY_QUOTA_EXCEEDED:
                    # 당일 키 소진 처리하여 재선택 방지
                    usage.daily_used = usage.daily_limit
                elif error_type == QuotaErrorType.API_KEY_INVALID:
                    # 잘못된 키는 비활성화 처리
                    usage.disabled = True
                elif error_type == QuotaErrorType.RATE_LIMIT_EXCEEDED:
                    # 속도 제한은 일시적인 문제 → 바로 전환할 수 있도록만 기록
                    pass
        
        # 한국어 오류 메시지 생성
        user_message = self._generate_korean_error_message(error_type)
        
        logger.error(f"API 할당량 오류 발생: {error_type.value} - {error_message}")
        
        return error_type, user_message
    
    def _generate_korean_error_message(self, error_type: QuotaErrorType) -> str:
        """사용자 친화적인 한국어 오류 메시지 생성"""
        kst = pytz.timezone('Asia/Seoul')
        current_usage = self.quota_usage.get(self.current_key_index)
        
        if error_type == QuotaErrorType.DAILY_QUOTA_EXCEEDED:
            if current_usage and current_usage.reset_time:
                reset_time_kst = current_usage.reset_time.astimezone(kst)
                reset_str = reset_time_kst.strftime('%Y년 %m월 %d일 %H:%M')
                
                return (f"일일 YouTube API 할당량이 모두 소진되었습니다. 🚫\n"
                       f"• 현재 사용량: {current_usage.daily_used:,}/{current_usage.daily_limit:,} 요청\n"
                       f"• 할당량 리셋 예정: {reset_str} (한국시간)\n"
                       f"• 잠시 후 다시 시도해주세요.\n"
                       f"• 문의사항이 있으시면 관리자에게 연락해주세요.")
        
        elif error_type == QuotaErrorType.RATE_LIMIT_EXCEEDED:
            return ("YouTube API 요청 속도 제한에 도달했습니다. ⚡\n"
                   "• 잠시 기다린 후(1-2분) 다시 시도해주세요.\n"
                   "• 너무 많은 검색을 연속으로 실행하면 발생할 수 있습니다.")
        
        elif error_type == QuotaErrorType.API_KEY_INVALID:
            return ("YouTube API 키에 문제가 발생했습니다. 🔑\n"
                   "• 관리자에게 문의해주세요.\n"
                   "• 임시적인 문제일 수 있으니 잠시 후 다시 시도해보세요.")
        
        else:
            return ("예상치 못한 오류가 발생했습니다. ❌\n"
                   "• 잠시 후 다시 시도해주세요.\n"
                   "• 문제가 지속되면 관리자에게 문의해주세요.")
    
    def _send_quota_warning(self, key_index: int, usage: QuotaUsage):
        """할당량 경고 발송"""
        percentage = usage.get_usage_percentage()
        logger.warning(f"API 키 {key_index} 할당량 경고: {percentage:.1f}% 사용됨 "
                      f"({usage.daily_used}/{usage.daily_limit})")
        
        # 여기에 이메일 알림이나 Slack 알림 등을 추가할 수 있음
        # 예: send_warning_notification(key_index, percentage)
    
    def _check_quota_reset(self):
        """할당량 리셋 시간 확인 및 리셋"""
        now = datetime.now(timezone.utc)
        
        for key_index, usage in self.quota_usage.items():
            if usage.reset_time and now >= usage.reset_time:
                old_usage = usage.daily_used
                usage.daily_used = 0
                usage.reset_time = self._get_next_reset_time()
                usage.rate_limit_remaining = 100
                # 리셋 시 비활성 상태 해제 (키가 다시 유효해졌을 수 있음은 제외: invalid는 유지)
                if usage.last_error_reason == QuotaErrorType.DAILY_QUOTA_EXCEEDED.value:
                    usage.disabled = False
                
                logger.info(f"API 키 {key_index} 할당량 리셋: {old_usage} -> 0")
    
    def get_quota_status(self) -> Dict:
        """현재 할당량 상태 정보 반환"""
        with self.lock:
            self._check_quota_reset()
            
            status = {
                'total_keys': len(self.api_keys),
                'current_key_index': self.current_key_index,
                'keys_status': [],
                'total_calls_today': len([c for c in self.call_history 
                                            if c.timestamp.date() == datetime.now().date()])
            }
            
            for i, usage in self.quota_usage.items():
                key_status = {
                    'key_index': i,
                    'daily_used': usage.daily_used,
                    'daily_limit': usage.daily_limit,
                    'usage_percentage': round(usage.get_usage_percentage(), 2),
                    'is_exceeded': usage.is_exceeded(),
                    'is_warning': usage.is_warning_level(),
                    'disabled': usage.disabled,
                    'last_error_reason': usage.last_error_reason,
                    'reset_time': usage.reset_time.isoformat() if usage.reset_time else None
                }
                status['keys_status'].append(key_status)
            
            return status
    
    def get_usage_statistics(self, hours: int = 24) -> Dict:
        """사용량 통계 반환"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_calls = [c for c in self.call_history if c.timestamp >= since]
        
        stats = {
            'period_hours': hours,
            'total_calls': len(recent_calls),
            'successful_calls': len([c for c in recent_calls if c.success]),
            'failed_calls': len([c for c in recent_calls if not c.success]),
            'total_cost': sum(c.cost for c in recent_calls if c.success),
            'endpoints': {},
            'hourly_usage': {}
        }
        
        # 엔드포인트별 통계
        for call in recent_calls:
            endpoint = call.endpoint
            if endpoint not in stats['endpoints']:
                stats['endpoints'][endpoint] = {'calls': 0, 'cost': 0, 'errors': 0}
            
            stats['endpoints'][endpoint]['calls'] += 1
            if call.success:
                stats['endpoints'][endpoint]['cost'] += call.cost
            else:
                stats['endpoints'][endpoint]['errors'] += 1
        
        # 시간별 사용량
        for call in recent_calls:
            hour_key = call.timestamp.strftime('%Y-%m-%d %H:00')
            if hour_key not in stats['hourly_usage']:
                stats['hourly_usage'][hour_key] = 0
            if call.success:
                stats['hourly_usage'][hour_key] += call.cost
        
        return stats

# 전역 인스턴스
_quota_manager: Optional[YouTubeQuotaManager] = None

def get_quota_manager() -> Optional[YouTubeQuotaManager]:
    """할당량 매니저 인스턴스 반환"""
    global _quota_manager
    return _quota_manager

def initialize_quota_manager(api_keys_str: str, daily_limit: int = 10000) -> YouTubeQuotaManager:
    """할당량 매니저 초기화"""
    global _quota_manager
    
    if not api_keys_str:
        logger.warning("API 키가 설정되지 않았습니다")
        return None
    
    api_keys = [key.strip() for key in api_keys_str.split(',') if key.strip()]
    _quota_manager = YouTubeQuotaManager(api_keys, daily_limit)
    
    logger.info(f"할당량 매니저 초기화 완료: {len(api_keys)}개 키")
    return _quota_manager
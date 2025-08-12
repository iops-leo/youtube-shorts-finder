# config/security.py
"""
보안 설정 관리 모듈
- 환경변수 검증
- 민감한 정보 로깅 방지
- 보안 정책 적용
"""

import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SecurityConfig:
    """보안 설정 관리 클래스"""
    
    # 필수 환경변수 목록
    REQUIRED_ENV_VARS = [
        'SECRET_KEY',
        'YOUTUBE_API_KEY',
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET',
        'DATABASE_URL'
    ]
    
    # 민감한 정보 키워드 (로깅 시 마스킹)
    SENSITIVE_KEYWORDS = [
        'api_key', 'secret', 'password', 'token', 'credential',
        'client_secret', 'private_key', 'auth', 'oauth'
    ]
    
    @classmethod
    def validate_environment(cls) -> Dict[str, Any]:
        """
        환경변수 검증
        Returns:
            dict: 검증 결과
        """
        missing_vars = []
        present_vars = []
        
        for var_name in cls.REQUIRED_ENV_VARS:
            if not os.environ.get(var_name):
                missing_vars.append(var_name)
            else:
                present_vars.append(var_name)
        
        return {
            'is_valid': len(missing_vars) == 0,
            'missing_vars': missing_vars,
            'present_vars': present_vars,
            'total_required': len(cls.REQUIRED_ENV_VARS)
        }
    
    @classmethod
    def mask_sensitive_data(cls, text: str, replacement: str = "••••") -> str:
        """
        민감한 정보 마스킹
        Args:
            text: 원본 텍스트
            replacement: 대체할 문자열
        Returns:
            str: 마스킹된 텍스트
        """
        if not text:
            return text
            
        # API 키 패턴 마스킹 (AIza로 시작하는 Google API 키)
        import re
        
        # Google API 키 패턴
        text = re.sub(r'AIza[A-Za-z0-9_-]{35}', f'{replacement}[API_KEY]', text)
        
        # 일반적인 키 패턴 (32자 이상의 영숫자 조합)
        text = re.sub(r'\b[A-Za-z0-9]{32,}\b', f'{replacement}[LONG_KEY]', text)
        
        return text
    
    @classmethod
    def safe_log_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        로깅용 안전한 파라미터 생성
        Args:
            params: 원본 파라미터
        Returns:
            dict: 마스킹된 파라미터
        """
        safe_params = {}
        
        for key, value in params.items():
            key_lower = key.lower()
            
            # 민감한 키워드 포함 시 마스킹
            if any(keyword in key_lower for keyword in cls.SENSITIVE_KEYWORDS):
                safe_params[key] = "••••[MASKED]"
            elif isinstance(value, str) and len(value) > 20:
                # 긴 문자열은 축약
                safe_params[key] = f"{value[:10]}...({len(value)}자)"
            else:
                safe_params[key] = value
                
        return safe_params
    
    @classmethod
    def get_environment_status(cls) -> str:
        """
        환경 상태 요약 반환
        Returns:
            str: 환경 상태 메시지
        """
        validation = cls.validate_environment()
        
        if validation['is_valid']:
            return f"✅ 보안 환경변수 검증 완료 ({validation['total_required']}개 모두 설정됨)"
        else:
            missing_count = len(validation['missing_vars'])
            return f"⚠️ 보안 환경변수 누락: {missing_count}개 미설정 {validation['missing_vars']}"
    
    @classmethod
    def is_development_environment(cls) -> bool:
        """
        개발 환경 여부 확인
        Returns:
            bool: 개발 환경이면 True
        """
        flask_env = os.environ.get('FLASK_ENV', '').lower()
        return flask_env in ['dev', 'development', 'local']
    
    @classmethod
    def apply_security_headers(cls, app):
        """
        Flask 앱에 보안 헤더 적용
        Args:
            app: Flask 앱 인스턴스
        """
        @app.after_request
        def add_security_headers(response):
            # XSS 보호
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # HTTPS 강제 (운영 환경에서만)
            if not cls.is_development_environment():
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            return response
        
        logger.info("🔒 보안 헤더 적용 완료")

def validate_required_environment():
    """
    필수 환경변수 검증 및 예외 발생
    Raises:
        ValueError: 필수 환경변수가 누락된 경우
    """
    validation = SecurityConfig.validate_environment()
    
    if not validation['is_valid']:
        missing_vars = ', '.join(validation['missing_vars'])
        raise ValueError(
            f"❌ 보안 오류: 필수 환경변수가 설정되지 않았습니다.\n"
            f"누락된 변수: {missing_vars}\n"
            f"모든 환경변수를 설정한 후 다시 시도해주세요."
        )
    
    logger.info(SecurityConfig.get_environment_status())

# 보안 로거 설정
def setup_secure_logging():
    """보안 로깅 설정"""
    
    class SensitiveDataFilter(logging.Filter):
        """민감한 데이터 필터링"""
        
        def filter(self, record):
            if hasattr(record, 'msg'):
                record.msg = SecurityConfig.mask_sensitive_data(str(record.msg))
            return True
    
    # 루트 로거에 필터 추가
    root_logger = logging.getLogger()
    root_logger.addFilter(SensitiveDataFilter())
    
    logger.info("🔒 보안 로깅 필터 적용 완료")

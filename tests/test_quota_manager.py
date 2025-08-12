# test_quota_manager.py
import unittest
import os
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common_utils.quota_manager import YouTubeQuotaManager, QuotaErrorType, QuotaUsage, APICall


class TestYouTubeQuotaManager(unittest.TestCase):
    """YouTube 할당량 관리자 테스트"""
    
    def setUp(self):
        """테스트 세트업"""
        self.test_api_keys = ['test_key_1', 'test_key_2', 'test_key_3']
        self.quota_manager = YouTubeQuotaManager(
            api_keys=self.test_api_keys,
            daily_limit=1000  # 테스트용 낮은 한도
        )
    
    def test_initialization(self):
        """초기화 테스트"""
        self.assertEqual(len(self.quota_manager.api_keys), 3)
        self.assertEqual(self.quota_manager.daily_limit, 1000)
        self.assertEqual(self.quota_manager.current_key_index, 0)
        self.assertEqual(len(self.quota_manager.quota_usage), 3)
        
        # 각 키의 초기 할당량이 올바르게 설정되었는지 확인
        for i in range(3):
            usage = self.quota_manager.quota_usage[i]
            self.assertEqual(usage.daily_used, 0)
            self.assertEqual(usage.daily_limit, 1000)
    
    def test_get_current_api_key(self):
        """현재 API 키 반환 테스트"""
        key = self.quota_manager.get_current_api_key()
        self.assertEqual(key, 'test_key_1')
        
        # 첫 번째 키를 할당량 초과로 만들고 테스트
        self.quota_manager.quota_usage[0].daily_used = 1000
        key = self.quota_manager.get_current_api_key()
        self.assertEqual(key, 'test_key_2')
        
        # 모든 키를 할당량 초과로 만들고 테스트
        for i in range(3):
            self.quota_manager.quota_usage[i].daily_used = 1000
        key = self.quota_manager.get_current_api_key()
        self.assertIsNone(key)
    
    def test_record_api_call(self):
        """API 호출 기록 테스트"""
        # 성공한 API 호출 기록
        cost = self.quota_manager.record_api_call('search.list', success=True)
        self.assertEqual(cost, 100)  # search.list의 기본 cost
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 100)
        self.assertEqual(len(self.quota_manager.call_history), 1)
        
        # 실패한 API 호출 기록 (할당량은 증가하지 않음)
        cost = self.quota_manager.record_api_call('videos.list', success=False, error_message="Test error")
        self.assertEqual(cost, 1)  # videos.list의 기본 cost
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 100)  # 변화 없음
        self.assertEqual(len(self.quota_manager.call_history), 2)
        
        # 실패한 호출 정보 확인
        failed_call = self.quota_manager.call_history[-1]
        self.assertFalse(failed_call.success)
        self.assertEqual(failed_call.error_message, "Test error")
    
    def test_switch_to_next_key(self):
        """API 키 전환 테스트"""
        # 정상적인 전환
        new_key = self.quota_manager.switch_to_next_key()
        self.assertEqual(new_key, 'test_key_2')
        self.assertEqual(self.quota_manager.current_key_index, 1)
        
        # 모든 키가 할당량 초과인 경우
        for i in range(3):
            self.quota_manager.quota_usage[i].daily_used = 1000
        
        new_key = self.quota_manager.switch_to_next_key()
        self.assertIsNone(new_key)
    
    def test_quota_warning(self):
        """할당량 경고 테스트"""
        # 경고 임계값 (90%)에 도달
        self.quota_manager.quota_usage[0].daily_used = 900
        
        usage = self.quota_manager.quota_usage[0]
        self.assertTrue(usage.is_warning_level())
        self.assertFalse(usage.is_exceeded())
        
        # 할당량 초과
        usage.daily_used = 1000
        self.assertTrue(usage.is_exceeded())
    
    def test_handle_quota_error(self):
        """할당량 오류 처리 테스트"""
        test_cases = [
            ("Daily quota exceeded", QuotaErrorType.DAILY_QUOTA_EXCEEDED),
            ("quotaExceeded", QuotaErrorType.DAILY_QUOTA_EXCEEDED),
            ("Rate limit exceeded", QuotaErrorType.RATE_LIMIT_EXCEEDED),
            ("Invalid API key", QuotaErrorType.API_KEY_INVALID),
            ("Forbidden", QuotaErrorType.API_KEY_INVALID),
            ("Unknown error", QuotaErrorType.UNKNOWN_ERROR),
        ]
        
        for error_message, expected_type in test_cases:
            with self.subTest(error_message=error_message):
                error_type, user_message = self.quota_manager.handle_quota_error(
                    error_message, 'test.endpoint'
                )
                self.assertEqual(error_type, expected_type)
                self.assertIsInstance(user_message, str)
                self.assertGreater(len(user_message), 0)
    
    def test_quota_reset(self):
        """할당량 리셋 테스트"""
        # 할당량을 일부 사용
        self.quota_manager.quota_usage[0].daily_used = 500
        
        # 리셋 시간을 과거로 설정
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.quota_manager.quota_usage[0].reset_time = past_time
        
        # 리셋 확인
        self.quota_manager._check_quota_reset()
        
        # 할당량이 리셋되었는지 확인
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 0)
        self.assertGreater(
            self.quota_manager.quota_usage[0].reset_time, 
            datetime.now(timezone.utc)
        )
    
    def test_quota_status(self):
        """할당량 상태 조회 테스트"""
        # 일부 할당량 사용
        self.quota_manager.record_api_call('search.list', success=True)
        self.quota_manager.record_api_call('videos.list', success=True)
        
        status = self.quota_manager.get_quota_status()
        
        self.assertEqual(status['total_keys'], 3)
        self.assertEqual(status['current_key_index'], 0)
        self.assertEqual(len(status['keys_status']), 3)
        
        key_status = status['keys_status'][0]
        self.assertEqual(key_status['daily_used'], 101)  # 100 + 1
        self.assertEqual(key_status['daily_limit'], 1000)
        self.assertFalse(key_status['is_exceeded'])
    
    def test_usage_statistics(self):
        """사용량 통계 테스트"""
        # 여러 API 호출 시뮬레이션
        endpoints = ['search.list', 'videos.list', 'channels.list']
        for endpoint in endpoints:
            for _ in range(5):  # 각 엔드포인트당 5번 호출
                self.quota_manager.record_api_call(endpoint, success=True)
        
        # 실패한 호출도 추가
        self.quota_manager.record_api_call('search.list', success=False, error_message="Test error")
        
        stats = self.quota_manager.get_usage_statistics(hours=24)
        
        self.assertEqual(stats['total_calls'], 16)  # 15 성공 + 1 실패
        self.assertEqual(stats['successful_calls'], 15)
        self.assertEqual(stats['failed_calls'], 1)
        self.assertEqual(stats['total_cost'], 510)  # 5*100 + 5*1 + 5*1 = 510
        
        # 엔드포인트별 통계 확인
        self.assertIn('search.list', stats['endpoints'])
        self.assertEqual(stats['endpoints']['search.list']['calls'], 6)  # 5 성공 + 1 실패
        self.assertEqual(stats['endpoints']['search.list']['errors'], 1)
    
    def test_korean_error_messages(self):
        """한국어 오류 메시지 테스트"""
        test_cases = [
            QuotaErrorType.DAILY_QUOTA_EXCEEDED,
            QuotaErrorType.RATE_LIMIT_EXCEEDED,
            QuotaErrorType.API_KEY_INVALID,
            QuotaErrorType.UNKNOWN_ERROR,
        ]
        
        for error_type in test_cases:
            with self.subTest(error_type=error_type):
                message = self.quota_manager._generate_korean_error_message(error_type)
                
                # 한글이 포함되어 있는지 확인
                self.assertTrue(any('\uac00' <= char <= '\ud7a3' for char in message))
                
                # 유용한 정보가 포함되어 있는지 확인
                if error_type == QuotaErrorType.DAILY_QUOTA_EXCEEDED:
                    self.assertIn('할당량', message)
                    self.assertIn('리셋', message)
                elif error_type == QuotaErrorType.RATE_LIMIT_EXCEEDED:
                    self.assertIn('속도 제한', message)
                elif error_type == QuotaErrorType.API_KEY_INVALID:
                    self.assertIn('API 키', message)


class TestQuotaUsage(unittest.TestCase):
    """QuotaUsage 클래스 테스트"""
    
    def test_usage_percentage(self):
        """사용률 계산 테스트"""
        usage = QuotaUsage(daily_used=500, daily_limit=1000)
        self.assertEqual(usage.get_usage_percentage(), 50.0)
        
        # 할당량이 0인 경우
        usage = QuotaUsage(daily_used=0, daily_limit=0)
        self.assertEqual(usage.get_usage_percentage(), 0.0)
    
    def test_warning_level(self):
        """경고 수준 테스트"""
        usage = QuotaUsage(daily_used=900, daily_limit=1000, warning_threshold=0.9)
        self.assertTrue(usage.is_warning_level())
        
        usage = QuotaUsage(daily_used=800, daily_limit=1000, warning_threshold=0.9)
        self.assertFalse(usage.is_warning_level())
    
    def test_exceeded(self):
        """할당량 초과 테스트"""
        usage = QuotaUsage(daily_used=1000, daily_limit=1000)
        self.assertTrue(usage.is_exceeded())
        
        usage = QuotaUsage(daily_used=1001, daily_limit=1000)
        self.assertTrue(usage.is_exceeded())
        
        usage = QuotaUsage(daily_used=999, daily_limit=1000)
        self.assertFalse(usage.is_exceeded())


class TestIntegration(unittest.TestCase):
    """통합 테스트"""
    
    def setUp(self):
        self.test_api_keys = ['key1', 'key2']
        self.quota_manager = YouTubeQuotaManager(self.test_api_keys, daily_limit=200)
    
    def test_quota_exhaustion_scenario(self):
        """할당량 소진 시나리오 테스트"""
        # 첫 번째 키의 할당량을 거의 다 사용
        for _ in range(19):  # 19 * 10 = 190
            self.quota_manager.record_api_call('videos.list', success=True)  # cost = 1씩
        
        # 현재 키 확인
        self.assertEqual(self.quota_manager.current_key_index, 0)
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 19)
        
        # 대용량 API 호출 (첫 번째 키 소진)
        for _ in range(2):
            self.quota_manager.record_api_call('search.list', success=True)  # cost = 100씩
        
        # 첫 번째 키 소진 확인
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 219)  # 19 + 200
        self.assertTrue(self.quota_manager.quota_usage[0].is_exceeded())
        
        # 다음 키로 자동 전환 확인
        current_key = self.quota_manager.get_current_api_key()
        self.assertEqual(current_key, 'key2')
        self.assertEqual(self.quota_manager.current_key_index, 1)
    
    def test_all_keys_exhausted_scenario(self):
        """모든 키 소진 시나리오 테스트"""
        # 모든 키의 할당량을 소진
        for i in range(len(self.test_api_keys)):
            self.quota_manager.quota_usage[i].daily_used = 200
        
        # API 키가 없어야 함
        current_key = self.quota_manager.get_current_api_key()
        self.assertIsNone(current_key)
        
        # 전환 시도해도 None이 반환되어야 함
        next_key = self.quota_manager.switch_to_next_key()
        self.assertIsNone(next_key)
    
    @patch('common_utils.quota_manager.datetime')
    def test_quota_reset_timing(self, mock_datetime):
        """할당량 리셋 타이밍 테스트"""
        # 현재 시간 모킹
        mock_now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        
        # 할당량 사용
        self.quota_manager.quota_usage[0].daily_used = 100
        
        # 리셋 시간을 과거로 설정
        reset_time = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        self.quota_manager.quota_usage[0].reset_time = reset_time
        
        # 리셋 실행
        self.quota_manager._check_quota_reset()
        
        # 할당량이 리셋되었는지 확인
        self.assertEqual(self.quota_manager.quota_usage[0].daily_used, 0)


if __name__ == '__main__':
    # 테스트 실행
    unittest.main(verbosity=2)
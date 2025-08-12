# test_quota_monitoring.py
import unittest
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common_utils.quota_monitoring import QuotaMonitor, QuotaAlert
from common_utils.quota_manager import YouTubeQuotaManager, QuotaUsage


class TestQuotaMonitor(unittest.TestCase):
    """할당량 모니터 테스트"""
    
    def setUp(self):
        """테스트 세트업"""
        # 환경변수 모킹
        self.env_patcher = patch.dict(os.environ, {
            'QUOTA_EMAIL_ALERTS': 'true',
            'ADMIN_EMAILS': 'admin1@test.com,admin2@test.com',
            'ALERT_INTERVAL_MINUTES': '30',
            'SMTP_SERVER': 'smtp.test.com',
            'SMTP_USERNAME': 'test@test.com',
            'SMTP_PASSWORD': 'testpass'
        })
        self.env_patcher.start()
        
        self.monitor = QuotaMonitor()
        
        # 테스트용 할당량 관리자 생성
        self.quota_manager = YouTubeQuotaManager(['key1', 'key2'], daily_limit=1000)
    
    def tearDown(self):
        """테스트 정리"""
        self.env_patcher.stop()
    
    def test_initialization(self):
        """초기화 테스트"""
        self.assertTrue(self.monitor.notification_settings['email_enabled'])
        self.assertEqual(len(self.monitor.notification_settings['admin_emails']), 2)
        self.assertEqual(self.monitor.notification_settings['alert_interval_minutes'], 30)
        self.assertEqual(self.monitor.notification_settings['warning_threshold'], 0.9)
    
    def test_check_quota_status_normal(self):
        """정상 상황에서의 할당량 상태 체크"""
        # 정상 사용량 (50%)
        self.quota_manager.quota_usage[0].daily_used = 500
        
        with patch.object(self.monitor, '_send_alert') as mock_send_alert:
            self.monitor.check_quota_status(self.quota_manager)
            mock_send_alert.assert_not_called()
    
    def test_check_quota_status_warning(self):
        """경고 상황에서의 할당량 상태 체크"""
        # 경고 수준 사용량 (90%)
        self.quota_manager.quota_usage[0].daily_used = 900
        
        with patch.object(self.monitor, '_send_alert') as mock_send_alert:
            self.monitor.check_quota_status(self.quota_manager)
            mock_send_alert.assert_called_once_with(
                'warning', 0, unittest.mock.ANY, unittest.mock.ANY
            )
    
    def test_check_quota_status_critical(self):
        """위험 상황에서의 할당량 상태 체크"""
        # 위험 수준 사용량 (95%)
        self.quota_manager.quota_usage[0].daily_used = 950
        
        with patch.object(self.monitor, '_send_alert') as mock_send_alert:
            self.monitor.check_quota_status(self.quota_manager)
            mock_send_alert.assert_called_once_with(
                'critical', 0, unittest.mock.ANY, unittest.mock.ANY
            )
    
    def test_is_recent_alert(self):
        """최근 알림 중복 방지 테스트"""
        current_time = datetime.now(timezone.utc)
        
        # 최근 알림 추가 (20분 전)
        recent_alert = QuotaAlert(
            alert_type='warning',
            key_index=0,
            usage_percentage=90.0,
            daily_used=900,
            daily_limit=1000,
            timestamp=current_time - timedelta(minutes=20),
            message="Test alert"
        )
        self.monitor.alerts_history.append(recent_alert)
        
        # 같은 키, 같은 타입의 알림은 차단되어야 함
        self.assertTrue(
            self.monitor._is_recent_alert(0, 'warning', current_time)
        )
        
        # 다른 키는 허용
        self.assertFalse(
            self.monitor._is_recent_alert(1, 'warning', current_time)
        )
        
        # 다른 타입은 허용
        self.assertFalse(
            self.monitor._is_recent_alert(0, 'critical', current_time)
        )
        
        # 충분히 시간이 지난 경우는 허용 (40분 전)
        old_alert = QuotaAlert(
            alert_type='warning',
            key_index=0,
            usage_percentage=90.0,
            daily_used=900,
            daily_limit=1000,
            timestamp=current_time - timedelta(minutes=40),
            message="Old alert"
        )
        self.monitor.alerts_history[0] = old_alert
        
        self.assertFalse(
            self.monitor._is_recent_alert(0, 'warning', current_time)
        )
    
    def test_generate_alert_message(self):
        """알림 메시지 생성 테스트"""
        key_status = {
            'key_index': 0,
            'usage_percentage': 90.5,
            'daily_used': 905,
            'daily_limit': 1000
        }
        
        # 경고 메시지
        warning_msg = self.monitor._generate_alert_message('warning', key_status)
        self.assertIn('경고', warning_msg)
        self.assertIn('90.5%', warning_msg)
        self.assertIn('905', warning_msg)
        
        # 위험 메시지
        critical_msg = self.monitor._generate_alert_message('critical', key_status)
        self.assertIn('위험', critical_msg)
        self.assertIn('곧 소진', critical_msg)
    
    @patch('smtplib.SMTP')
    def test_send_email_alert_success(self, mock_smtp_class):
        """이메일 알림 발송 성공 테스트"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        
        alert = QuotaAlert(
            alert_type='warning',
            key_index=0,
            usage_percentage=90.0,
            daily_used=900,
            daily_limit=1000,
            timestamp=datetime.now(timezone.utc),
            message="Test warning message"
        )
        
        self.monitor._send_email_alert(alert)
        
        # SMTP 서버 연결 및 로그인 확인
        mock_smtp_class.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()
    
    @patch('smtplib.SMTP')
    def test_send_email_alert_failure(self, mock_smtp_class):
        """이메일 알림 발송 실패 테스트"""
        mock_smtp_class.side_effect = Exception("SMTP connection failed")
        
        alert = QuotaAlert(
            alert_type='critical',
            key_index=1,
            usage_percentage=95.0,
            daily_used=950,
            daily_limit=1000,
            timestamp=datetime.now(timezone.utc),
            message="Test critical message"
        )
        
        # 예외 발생해도 프로그램이 중단되지 않아야 함
        try:
            self.monitor._send_email_alert(alert)
        except Exception:
            self.fail("이메일 발송 실패 시 예외가 전파되면 안됨")
    
    def test_generate_email_html(self):
        """이메일 HTML 생성 테스트"""
        alert = QuotaAlert(
            alert_type='warning',
            key_index=0,
            usage_percentage=90.5,
            daily_used=905,
            daily_limit=1000,
            timestamp=datetime.now(timezone.utc),
            message="Test warning message"
        )
        
        html = self.monitor._generate_email_html(alert)
        
        # HTML 구조 확인
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('<html>', html)
        self.assertIn('<body>', html)
        
        # 알림 정보 포함 확인
        self.assertIn('90.5%', html)
        self.assertIn('905', html)
        self.assertIn('1,000', html)
        self.assertIn('키 #1', html)
        
        # 한글 포함 확인
        self.assertTrue(any('\uac00' <= char <= '\ud7a3' for char in html))
    
    @patch('requests.post')
    def test_send_slack_alert_success(self, mock_post):
        """슬랙 알림 발송 성공 테스트"""
        # 슬랙 웹훅 URL 설정
        self.monitor.slack_webhook_url = 'https://hooks.slack.com/test'
        self.monitor.slack_enabled = True
        
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        alert = QuotaAlert(
            alert_type='critical',
            key_index=1,
            usage_percentage=95.0,
            daily_used=950,
            daily_limit=1000,
            timestamp=datetime.now(timezone.utc),
            message="Test critical message"
        )
        
        self.monitor._send_slack_alert(alert)
        
        # HTTP POST 요청 확인
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # 요청 URL 확인
        self.assertEqual(call_args[0][0], 'https://hooks.slack.com/test')
        
        # 요청 본문 확인
        payload = call_args[1]['json']
        self.assertIn('attachments', payload)
        self.assertEqual(payload['attachments'][0]['color'], 'danger')
    
    def test_get_alerts_summary(self):
        """알림 요약 정보 테스트"""
        current_time = datetime.now(timezone.utc)
        
        # 테스트 알림 추가
        alerts = [
            QuotaAlert('warning', 0, 90.0, 900, 1000, current_time - timedelta(hours=2), "Warning 1"),
            QuotaAlert('critical', 1, 95.0, 950, 1000, current_time - timedelta(hours=1), "Critical 1"),
            QuotaAlert('warning', 0, 92.0, 920, 1000, current_time - timedelta(minutes=30), "Warning 2"),
            # 24시간 이전 알림 (제외되어야 함)
            QuotaAlert('warning', 2, 88.0, 880, 1000, current_time - timedelta(hours=25), "Old warning"),
        ]
        
        self.monitor.alerts_history.extend(alerts)
        
        summary = self.monitor.get_alerts_summary(hours=24)
        
        self.assertEqual(summary['total_alerts'], 3)  # 최근 24시간 내 3개
        self.assertEqual(summary['warning_alerts'], 2)
        self.assertEqual(summary['critical_alerts'], 1)
        self.assertEqual(summary['affected_keys'], 2)  # 키 0, 1
        self.assertEqual(len(summary['recent_alerts']), 3)
    
    def test_cleanup_old_alerts(self):
        """오래된 알림 정리 테스트"""
        current_time = datetime.now(timezone.utc)
        
        # 다양한 시점의 알림 추가
        alerts = [
            QuotaAlert('warning', 0, 90.0, 900, 1000, current_time - timedelta(days=1), "Recent"),
            QuotaAlert('warning', 0, 90.0, 900, 1000, current_time - timedelta(days=5), "Medium old"),
            QuotaAlert('warning', 0, 90.0, 900, 1000, current_time - timedelta(days=10), "Very old"),
        ]
        
        self.monitor.alerts_history.extend(alerts)
        
        # 7일 이상 된 알림 정리
        self.monitor.cleanup_old_alerts(days=7)
        
        # 최근 7일 내 알림만 남아있어야 함
        self.assertEqual(len(self.monitor.alerts_history), 2)
        
        # 가장 오래된 알림이 제거되었는지 확인
        remaining_messages = [alert.message for alert in self.monitor.alerts_history]
        self.assertNotIn("Very old", remaining_messages)
        self.assertIn("Recent", remaining_messages)
        self.assertIn("Medium old", remaining_messages)


class TestQuotaAlert(unittest.TestCase):
    """QuotaAlert 데이터 클래스 테스트"""
    
    def test_quota_alert_creation(self):
        """QuotaAlert 생성 테스트"""
        timestamp = datetime.now(timezone.utc)
        
        alert = QuotaAlert(
            alert_type='warning',
            key_index=2,
            usage_percentage=85.5,
            daily_used=855,
            daily_limit=1000,
            timestamp=timestamp,
            message="Test alert message"
        )
        
        self.assertEqual(alert.alert_type, 'warning')
        self.assertEqual(alert.key_index, 2)
        self.assertEqual(alert.usage_percentage, 85.5)
        self.assertEqual(alert.daily_used, 855)
        self.assertEqual(alert.daily_limit, 1000)
        self.assertEqual(alert.timestamp, timestamp)
        self.assertEqual(alert.message, "Test alert message")


class TestIntegrationQuotaMonitoring(unittest.TestCase):
    """할당량 모니터링 통합 테스트"""
    
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {
            'QUOTA_EMAIL_ALERTS': 'true',
            'ADMIN_EMAILS': 'admin@test.com'
        })
        self.env_patcher.start()
        
        self.quota_manager = YouTubeQuotaManager(['key1', 'key2'], daily_limit=1000)
        self.monitor = QuotaMonitor()
    
    def tearDown(self):
        self.env_patcher.stop()
    
    @patch.object(QuotaMonitor, '_send_email_alert')
    @patch.object(QuotaMonitor, '_send_slack_alert')
    def test_full_monitoring_workflow(self, mock_slack, mock_email):
        """전체 모니터링 워크플로우 테스트"""
        # 1단계: 정상 사용량 - 알림 없음
        self.quota_manager.quota_usage[0].daily_used = 800  # 80%
        self.monitor.check_quota_status(self.quota_manager)
        mock_email.assert_not_called()
        mock_slack.assert_not_called()
        
        # 2단계: 경고 수준 도달 - 경고 알림 발송
        self.quota_manager.quota_usage[0].daily_used = 900  # 90%
        self.monitor.check_quota_status(self.quota_manager)
        
        # 경고 알림 발송 확인
        self.assertEqual(mock_email.call_count, 1)
        sent_alert = mock_email.call_args[0][0]
        self.assertEqual(sent_alert.alert_type, 'warning')
        self.assertEqual(sent_alert.key_index, 0)
        
        # 3단계: 동일한 경고 - 중복 알림 방지
        mock_email.reset_mock()
        self.monitor.check_quota_status(self.quota_manager)
        mock_email.assert_not_called()  # 중복 알림 방지됨
        
        # 4단계: 위험 수준 도달 - 위험 알림 발송
        self.quota_manager.quota_usage[0].daily_used = 950  # 95%
        self.monitor.check_quota_status(self.quota_manager)
        
        # 위험 알림 발송 확인
        self.assertEqual(mock_email.call_count, 1)
        sent_alert = mock_email.call_args[0][0]
        self.assertEqual(sent_alert.alert_type, 'critical')
        
        # 알림 이력 확인
        self.assertEqual(len(self.monitor.alerts_history), 2)  # warning + critical
    
    def test_multiple_keys_monitoring(self):
        """여러 키 모니터링 테스트"""
        with patch.object(self.monitor, '_send_alert') as mock_send_alert:
            # 첫 번째 키: 경고 수준
            self.quota_manager.quota_usage[0].daily_used = 900
            
            # 두 번째 키: 위험 수준
            self.quota_manager.quota_usage[1].daily_used = 950
            
            self.monitor.check_quota_status(self.quota_manager)
            
            # 두 번의 알림이 발송되어야 함
            self.assertEqual(mock_send_alert.call_count, 2)
            
            # 호출 인자 확인
            calls = mock_send_alert.call_args_list
            
            # 첫 번째 호출: 키 0의 경고
            self.assertEqual(calls[0][0][0], 'warning')  # alert_type
            self.assertEqual(calls[0][0][1], 0)  # key_index
            
            # 두 번째 호출: 키 1의 위험
            self.assertEqual(calls[1][0][0], 'critical')  # alert_type  
            self.assertEqual(calls[1][0][1], 1)  # key_index


if __name__ == '__main__':
    unittest.main(verbosity=2)
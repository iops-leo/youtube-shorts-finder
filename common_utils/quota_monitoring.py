# quota_monitoring.py
import os
import json
import smtplib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, asdict
import pytz
from jinja2 import Template

logger = logging.getLogger(__name__)

@dataclass
class QuotaAlert:
    """할당량 알림 정보"""
    alert_type: str  # warning, critical, reset
    key_index: int
    usage_percentage: float
    daily_used: int
    daily_limit: int
    timestamp: datetime
    message: str

class QuotaMonitor:
    """YouTube API 할당량 모니터링 시스템"""
    
    def __init__(self, app_config=None):
        self.app_config = app_config
        self.alerts_history: List[QuotaAlert] = []
        self.notification_settings = {
            'warning_threshold': 0.9,  # 90%에서 경고
            'critical_threshold': 0.95,  # 95%에서 위험 알림
            'email_enabled': os.environ.get('QUOTA_EMAIL_ALERTS', 'false').lower() == 'true',
            'admin_emails': os.environ.get('ADMIN_EMAILS', '').split(','),
            'alert_interval_minutes': int(os.environ.get('ALERT_INTERVAL_MINUTES', '30'))
        }
        
        # 슬랙 설정 (선택사항)
        self.slack_webhook_url = os.environ.get('SLACK_WEBHOOK_URL', '')
        self.slack_enabled = bool(self.slack_webhook_url)
    
    def check_quota_status(self, quota_manager):
        """할당량 상태 확인 및 알림 발송"""
        if not quota_manager:
            return
        
        status = quota_manager.get_quota_status()
        current_time = datetime.now(timezone.utc)
        
        for key_status in status['keys_status']:
            key_index = key_status['key_index']
            usage_percentage = key_status['usage_percentage'] / 100  # 0-1 범위로 변환
            
            # 경고 레벨 확인
            if usage_percentage >= self.notification_settings['critical_threshold']:
                self._send_alert('critical', key_index, key_status, current_time)
            elif usage_percentage >= self.notification_settings['warning_threshold']:
                self._send_alert('warning', key_index, key_status, current_time)
    
    def _send_alert(self, alert_type: str, key_index: int, key_status: dict, timestamp: datetime):
        """알림 발송"""
        # 중복 알림 방지 (같은 키에 대해 설정된 간격 내에는 알림 안함)
        if self._is_recent_alert(key_index, alert_type, timestamp):
            return
        
        alert = QuotaAlert(
            alert_type=alert_type,
            key_index=key_index,
            usage_percentage=key_status['usage_percentage'],
            daily_used=key_status['daily_used'],
            daily_limit=key_status['daily_limit'],
            timestamp=timestamp,
            message=self._generate_alert_message(alert_type, key_status)
        )
        
        # 알림 이력 저장
        self.alerts_history.append(alert)
        
        # 로그 기록
        logger.warning(f"YouTube API 할당량 {alert_type} 알림: {alert.message}")
        
        # 이메일 알림 발송
        if self.notification_settings['email_enabled']:
            self._send_email_alert(alert)
        
        # 슬랙 알림 발송
        if self.slack_enabled:
            self._send_slack_alert(alert)
    
    def _is_recent_alert(self, key_index: int, alert_type: str, current_time: datetime) -> bool:
        """최근에 동일한 알림을 보냈는지 확인"""
        interval_minutes = self.notification_settings['alert_interval_minutes']
        cutoff_time = current_time - timedelta(minutes=interval_minutes)
        
        for alert in self.alerts_history:
            if (alert.key_index == key_index and 
                alert.alert_type == alert_type and 
                alert.timestamp > cutoff_time):
                return True
        
        return False
    
    def _generate_alert_message(self, alert_type: str, key_status: dict) -> str:
        """알림 메시지 생성"""
        key_index = key_status['key_index']
        usage_percentage = key_status['usage_percentage']
        daily_used = key_status['daily_used']
        daily_limit = key_status['daily_limit']
        
        if alert_type == 'warning':
            return (f"API 키 #{key_index + 1} 할당량 경고: {usage_percentage:.1f}% 사용됨 "
                   f"({daily_used:,}/{daily_limit:,} 요청)")
        elif alert_type == 'critical':
            return (f"API 키 #{key_index + 1} 할당량 위험: {usage_percentage:.1f}% 사용됨 "
                   f"({daily_used:,}/{daily_limit:,} 요청) - 곧 소진될 예정")
        else:
            return (f"API 키 #{key_index + 1} 상태: {usage_percentage:.1f}% 사용됨 "
                   f"({daily_used:,}/{daily_limit:,} 요청)")
    
    def _send_email_alert(self, alert: QuotaAlert):
        """이메일 알림 발송"""
        try:
            if not self.notification_settings['admin_emails']:
                return
            
            # 이메일 설정
            smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            smtp_username = os.environ.get('SMTP_USERNAME', '')
            smtp_password = os.environ.get('SMTP_PASSWORD', '')
            sender_email = os.environ.get('SENDER_EMAIL', smtp_username)
            
            if not all([smtp_username, smtp_password]):
                logger.warning("이메일 설정이 완료되지 않아 할당량 알림 이메일을 발송할 수 없습니다.")
                return
            
            # 이메일 생성
            msg = MIMEMultipart('alternative')
            
            if alert.alert_type == 'critical':
                subject = f"🚨 [긴급] YouTube API 할당량 위험 알림 - 키 #{alert.key_index + 1}"
            else:
                subject = f"⚠️ YouTube API 할당량 경고 - 키 #{alert.key_index + 1}"
            
            msg['Subject'] = subject
            msg['From'] = sender_email
            msg['To'] = ', '.join(self.notification_settings['admin_emails'])
            
            # HTML 이메일 내용
            html_content = self._generate_email_html(alert)
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 이메일 발송
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            logger.info(f"YouTube API 할당량 알림 이메일 발송 완료: {alert.alert_type}")
            
        except Exception as e:
            logger.error(f"할당량 알림 이메일 발송 실패: {str(e)}")
    
    def _generate_email_html(self, alert: QuotaAlert) -> str:
        """이메일 HTML 생성"""
        kst = pytz.timezone('Asia/Seoul')
        alert_time_kst = alert.timestamp.astimezone(kst)
        
        # 알림 타입별 스타일
        if alert.alert_type == 'critical':
            alert_color = '#dc3545'  # 빨간색
            alert_icon = '🚨'
            alert_title = '긴급: API 할당량 위험'
        else:
            alert_color = '#ffc107'  # 노란색
            alert_icon = '⚠️'
            alert_title = 'API 할당량 경고'
        
        template_str = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
                .container { max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
                .header { background-color: {{ alert_color }}; color: white; padding: 20px; text-align: center; }
                .header h1 { margin: 0; font-size: 24px; }
                .content { padding: 30px; }
                .alert-info { background-color: #f8f9fa; border-left: 4px solid {{ alert_color }}; padding: 15px; margin: 20px 0; }
                .stats-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                .stats-table th, .stats-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                .stats-table th { background-color: #f8f9fa; }
                .progress-bar { background-color: #e9ecef; border-radius: 10px; height: 20px; margin: 10px 0; }
                .progress-fill { background-color: {{ alert_color }}; height: 100%; border-radius: 10px; width: {{ usage_percentage }}%; }
                .footer { background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 14px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{{ alert_icon }} {{ alert_title }}</h1>
                </div>
                <div class="content">
                    <div class="alert-info">
                        <h3>알림 내용</h3>
                        <p><strong>{{ alert.message }}</strong></p>
                        <p>발생 시간: {{ alert_time_formatted }}</p>
                    </div>
                    
                    <h3>할당량 사용 현황</h3>
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                    <p style="text-align: center; margin: 5px 0;"><strong>{{ usage_percentage }}%</strong> 사용됨</p>
                    
                    <table class="stats-table">
                        <tr>
                            <th>API 키</th>
                            <td>키 #{{ alert.key_index + 1 }}</td>
                        </tr>
                        <tr>
                            <th>일일 사용량</th>
                            <td>{{ '{:,}'.format(alert.daily_used) }} / {{ '{:,}'.format(alert.daily_limit) }} 요청</td>
                        </tr>
                        <tr>
                            <th>남은 할당량</th>
                            <td>{{ '{:,}'.format(alert.daily_limit - alert.daily_used) }} 요청</td>
                        </tr>
                        <tr>
                            <th>예상 리셋 시간</th>
                            <td>다음날 오전 9시 (한국시간)</td>
                        </tr>
                    </table>
                    
                    {% if alert.alert_type == 'critical' %}
                    <div style="background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h4 style="color: #856404; margin-top: 0;">⚠️ 권장 조치사항</h4>
                        <ul style="color: #856404; margin-bottom: 0;">
                            <li>추가 API 키 확보를 검토해주세요</li>
                            <li>캐시 설정을 확인하여 불필요한 API 호출을 줄여주세요</li>
                            <li>사용량 급증 원인을 분석해주세요</li>
                            <li>필요시 일시적으로 검색 기능 제한을 고려해주세요</li>
                        </ul>
                    </div>
                    {% endif %}
                </div>
                <div class="footer">
                    <p>YouTube Shorts Finder - 할당량 모니터링 시스템</p>
                    <p>이 알림을 중지하려면 QUOTA_EMAIL_ALERTS 환경변수를 false로 설정하세요.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        template = Template(template_str)
        return template.render(
            alert=alert,
            alert_color=alert_color,
            alert_icon=alert_icon,
            alert_title=alert_title,
            usage_percentage=f"{alert.usage_percentage:.1f}",
            alert_time_formatted=alert_time_kst.strftime('%Y년 %m월 %d일 %H:%M:%S (KST)')
        )
    
    def _send_slack_alert(self, alert: QuotaAlert):
        """슬랙 알림 발송"""
        try:
            import requests
            
            kst = pytz.timezone('Asia/Seoul')
            alert_time_kst = alert.timestamp.astimezone(kst)
            
            if alert.alert_type == 'critical':
                color = 'danger'
                icon = '🚨'
            else:
                color = 'warning' 
                icon = '⚠️'
            
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"{icon} YouTube API 할당량 {alert.alert_type.upper()} 알림",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "API 키",
                                "value": f"키 #{alert.key_index + 1}",
                                "short": True
                            },
                            {
                                "title": "사용률",
                                "value": f"{alert.usage_percentage:.1f}%",
                                "short": True
                            },
                            {
                                "title": "사용량",
                                "value": f"{alert.daily_used:,} / {alert.daily_limit:,}",
                                "short": True
                            },
                            {
                                "title": "발생 시간",
                                "value": alert_time_kst.strftime('%Y-%m-%d %H:%M:%S KST'),
                                "short": True
                            }
                        ],
                        "footer": "YouTube Shorts Finder",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            response = requests.post(self.slack_webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"슬랙 할당량 알림 발송 완료: {alert.alert_type}")
            
        except Exception as e:
            logger.error(f"슬랙 할당량 알림 발송 실패: {str(e)}")
    
    def get_alerts_summary(self, hours: int = 24) -> Dict:
        """최근 알림 요약 정보 반환"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_alerts = [alert for alert in self.alerts_history if alert.timestamp > since]
        
        summary = {
            'total_alerts': len(recent_alerts),
            'warning_alerts': len([a for a in recent_alerts if a.alert_type == 'warning']),
            'critical_alerts': len([a for a in recent_alerts if a.alert_type == 'critical']),
            'affected_keys': len(set(a.key_index for a in recent_alerts)),
            'recent_alerts': [asdict(alert) for alert in recent_alerts[-10:]]  # 최근 10개
        }
        
        return summary
    
    def cleanup_old_alerts(self, days: int = 7):
        """오래된 알림 이력 정리"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        
        before_count = len(self.alerts_history)
        self.alerts_history = [alert for alert in self.alerts_history if alert.timestamp > cutoff_time]
        after_count = len(self.alerts_history)
        
        if before_count > after_count:
            logger.info(f"할당량 알림 이력 정리: {before_count - after_count}개 항목 삭제")

# 전역 인스턴스
_quota_monitor: Optional[QuotaMonitor] = None

def get_quota_monitor() -> Optional[QuotaMonitor]:
    """할당량 모니터 인스턴스 반환"""
    global _quota_monitor
    return _quota_monitor

def initialize_quota_monitor(app_config=None) -> QuotaMonitor:
    """할당량 모니터 초기화"""
    global _quota_monitor
    _quota_monitor = QuotaMonitor(app_config)
    logger.info("YouTube API 할당량 모니터링 시스템 초기화 완료")
    return _quota_monitor

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
from jinja2 import Template

class EmailService:
    def __init__(self, app):
        self.app = app
        self.smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_username = os.environ.get('SMTP_USERNAME', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.sender_email = os.environ.get('SENDER_EMAIL', 'leaflife84@gmail.com')
    
    def send_email(self, recipient, subject, html_content):
        """이메일 발송 함수"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            self.app.logger.error(f"이메일 발송 오류: {str(e)}")
            return False
    
    def format_shorts_email(self, user, search_results, timestamp):
        """쇼츠 이메일 포맷팅"""
        try:
            # 이메일 템플릿 로드 (실제로는 파일에서 로드할 수 있음)
            template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .video-card { border: 1px solid #ddd; margin-bottom: 15px; padding: 10px; border-radius: 5px; }
                    .video-title { font-weight: bold; }
                    .video-stats { color: #666; font-size: 14px; }
                    .category-section { margin-bottom: 25px; }
                    .category-title { background-color: #f0f0f0; padding: 5px; border-radius: 3px; }
                </style>
            </head>
            <body>
                <h2>YouTube Shorts 인기 영상 알림</h2>
                <p>안녕하세요, {{ user.name }}님!</p>
                <p>구독하신 채널 카테고리의 인기 YouTube Shorts를 알려드립니다.</p>
                <p>검색 시간: {{ timestamp }}</p>
                
                {% for category in results %}
                <div class="category-section">
                    <h3 class="category-title">{{ category.name }} ({{ category.videos|length }}개 영상)</h3>
                    
                    {% if category.videos %}
                        {% for video in category.videos %}
                        <div class="video-card">
                            <div class="video-title">
                                <a href="{{ video.url }}" target="_blank">{{ video.title }}</a>
                            </div>
                            <div class="video-channel">채널: {{ video.channelTitle }}</div>
                            <div class="video-stats">
                                조회수: {{ video.viewCount }}회 | 
                                좋아요: {{ video.likeCount }}개 | 
                                댓글: {{ video.commentCount }}개
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p>조건에 맞는 영상이 없습니다.</p>
                    {% endif %}
                </div>
                {% endfor %}
                
                <p>
                    <small>이 이메일은 YouTube Shorts 도구에서 자동으로 발송되었습니다.<br>
                    알림 설정을 변경하시려면 <a href="https://shorts.ddns.net/notifications">알림 설정</a>에서 변경하실 수 있습니다.</small>
                </p>
            </body>
            </html>
            """
            
            template = Template(template_str)
            return template.render(user=user, results=search_results, timestamp=timestamp)
        except Exception as e:
            self.app.logger.error(f"이메일 포맷팅 오류: {str(e)}")
            return "<p>이메일 생성 중 오류가 발생했습니다.</p>"
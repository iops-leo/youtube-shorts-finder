
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
        """쇼츠 이메일 포맷팅 - 깔끔한 디자인"""
        try:
            from datetime import datetime
            import pytz

            # timestamp가 문자열이면 datetime으로 파싱
            if isinstance(timestamp, str):
                try:
                    # UTC 시간 파싱 (여러 형식 시도)
                    for fmt in ('%Y-%m-%d %H:%M:%S UTC', '%Y-%m-%d %H:%M:%S'):
                        try:
                            dt = datetime.strptime(timestamp, fmt)
                            dt = dt.replace(tzinfo=pytz.UTC)
                            break
                        except ValueError:
                            continue
                except:
                    # 파싱 실패 시 현재 시간 사용
                    dt = datetime.now(pytz.UTC)
            else:
                # datetime 객체이면 UTC 시간대 설정
                dt = timestamp.replace(tzinfo=pytz.UTC) if timestamp.tzinfo is None else timestamp
            
            # KST로 변환
            kst = pytz.timezone('Asia/Seoul')
            kst_time = dt.astimezone(kst)
            formatted_time = kst_time.strftime('%Y-%m-%d %H:%M:%S KST')
            
            # 개선된 이메일 템플릿
            template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { 
                        font-family: Arial, sans-serif; 
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                    }
                    .header {
                        background-color: #4285f4;
                        color: white;
                        padding: 20px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                    }
                    .content {
                        padding: 20px;
                    }
                    .category {
                        margin: 30px 0 15px 0;
                        border-bottom: 2px solid #4285f4;
                        padding-bottom: 5px;
                        font-size: 18px;
                        font-weight: bold;
                    }
                    .video {
                        background-color: #f9f9f9;
                        border-left: 4px solid #4285f4;
                        padding: 12px;
                        margin-bottom: 15px;
                        border-radius: 0 5px 5px 0;
                    }
                    .video-title {
                        font-weight: bold;
                        margin-bottom: 5px;
                    }
                    .video-channel {
                        color: #666;
                        font-size: 14px;
                        margin-bottom: 5px;
                    }
                    .video-stats {
                        color: #888;
                        font-size: 13px;
                        display: flex;
                        justify-content: space-between;
                    }
                    .footer {
                        background-color: #f1f1f1;
                        padding: 15px;
                        text-align: center;
                        font-size: 12px;
                        color: #666;
                        border-radius: 0 0 5px 5px;
                    }
                    a {
                        color: #4285f4;
                        text-decoration: none;
                    }
                    a:hover {
                        text-decoration: underline;
                    }
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>YouTube Shorts 인기 영상 알림</h2>
                </div>
                
                <div class="content">
                    <p>안녕하세요, {{ user.name }}님!</p>
                    <p>구독하신 채널 카테고리의 인기 YouTube Shorts를 알려드립니다.</p>
                    <p><strong>검색 시간:</strong> {{ timestamp }}</p>
                    
                    {% for category in results %}
                    <div class="category">{{ category.name }} ({{ category.videos|length }}개)</div>
                    
                    {% if category.videos %}
                        {% for video in category.videos %}
                        <div class="video">
                            <div class="video-title">
                                <a href="{{ video.url }}" target="_blank">{{ video.title }}</a>
                            </div>
                            <div class="video-channel">채널: {{ video.channelTitle }}</div>
                            <div class="video-stats">
                                <span>👁️ {{ video.viewCount }}회</span>
                                <span>👍 {{ video.likeCount }}개</span>
                                <span>💬 {{ video.commentCount }}개</span>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p>조건에 맞는 영상이 없습니다.</p>
                    {% endif %}
                    {% endfor %}
                </div>
                
                <div class="footer">
                    <p>이 이메일은 YouTube Shorts 도구에서 자동으로 발송되었습니다.<br>
                    알림 설정을 변경하시려면 <a href="https://shorts.ddns.net/notifications">알림 설정</a>에서 변경하실 수 있습니다.</p>
                </div>
            </body>
            </html>
            """
            
            template = Template(template_str)
            return template.render(user=user, results=search_results, timestamp=timestamp)
        except Exception as e:
            self.app.logger.error(f"이메일 포맷팅 오류: {str(e)}")
            return "<p>이메일 생성 중 오류가 발생했습니다.</p>"
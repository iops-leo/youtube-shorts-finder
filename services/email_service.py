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
        self.sender_email = os.environ.get('SENDER_EMAIL', 'youtubeshortstool@gmail.com')
    
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
                <meta charset="UTF-8">
                <style>
                    body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f9f9f9; color: #333; }
                    .container { max-width: 700px; margin: 0 auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
                    .header { background-color: #3498db; color: white; padding: 15px; text-align: center; border-radius: 6px 6px 0 0; margin-bottom: 20px; }
                    .video-card { border: 1px solid #ddd; margin-bottom: 15px; padding: 15px; border-radius: 5px; background-color: #fff; transition: transform 0.3s ease; }
                    .video-card:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
                    .video-title { font-weight: bold; font-size: 16px; margin-bottom: 8px; }
                    .video-stats { color: #666; font-size: 14px; display: flex; justify-content: space-between; flex-wrap: wrap; margin-top: 10px; }
                    .stat-item { margin-right: 10px; }
                    .category-section { margin-bottom: 25px; }
                    .category-title { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 15px; font-size: 18px; font-weight: bold; }
                    .footer { font-size: 12px; color: #777; text-align: center; margin-top: 30px; padding-top: 15px; border-top: 1px solid #ddd; }
                    a { color: #3498db; text-decoration: none; }
                    a:hover { text-decoration: underline; }
                    .video-meta { display: flex; justify-content: space-between; align-items: center; }
                    .view-more { text-align: center; margin-top: 10px; }
                    .summary { background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 20px; }
                    .summary-title { font-weight: bold; margin-bottom: 5px; }
                    .summary-item { margin-bottom: 5px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1 style="margin:0;">YouTube Shorts 인기 영상 알림</h1>
                    </div>
                    
                    <p>안녕하세요, <strong>{{ user.name }}</strong>님!</p>
                    <p>구독하신 채널 카테고리의 인기 YouTube Shorts를 알려드립니다.</p>
                    <p><strong>검색 시간:</strong> {{ timestamp }}</p>
                    
                    <!-- 검색 결과 요약 -->
                    <div class="summary">
                        <div class="summary-title">🔍 검색 결과 요약</div>
                        {% set total_videos = 0 %}
                        {% for category in results %}
                            {% set total_videos = total_videos + category.videos|length %}
                            <div class="summary-item">• <strong>{{ category.name }}</strong>: {{ category.videos|length }}개 영상</div>
                        {% endfor %}
                        <div style="margin-top: 8px;"><strong>🎬 총 {{ total_videos }}개의 인기 Shorts 영상</strong></div>
                    </div>
                    
                    {% for category in results %}
                    <div class="category-section">
                        <h3 class="category-title">
                            📂 {{ category.name }} ({{ category.videos|length }}개 영상)
                        </h3>
                        
                        {% if category.videos %}
                            {% for video in category.videos %}
                            <div class="video-card">
                                <div class="video-title">
                                    <a href="{{ video.url }}" target="_blank">{{ video.title }}</a>
                                </div>
                                
                                {% if video.translated_title %}
                                <div style="color: #777; font-size: 14px; margin-bottom: 8px;">
                                    <span style="color: #888;"><i>{{ video.translated_title }}</i></span>
                                </div>
                                {% endif %}
                                
                                <div class="video-meta">
                                    <div style="font-size: 14px;">
                                        <a href="https://www.youtube.com/channel/{{ video.channelId }}" target="_blank">{{ video.channelTitle }}</a>
                                    </div>
                                    <div style="font-size: 13px; color: #777;">
                                        게시일: {{ video.publishedAt.split('T')[0] }}
                                    </div>
                                </div>
                                
                                <div class="video-stats">
                                    <span class="stat-item">👁️ 조회수: {{ '{:,}'.format(video.viewCount) }}회</span>
                                    <span class="stat-item">👍 좋아요: {{ '{:,}'.format(video.likeCount) }}개</span>
                                    <span class="stat-item">💬 댓글: {{ '{:,}'.format(video.commentCount) }}개</span>
                                    <span class="stat-item">⏱️ 길이: {{ video.duration }}초</span>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p style="text-align: center; color: #777;">조건에 맞는 영상이 없습니다.</p>
                        {% endif %}
                    </div>
                    {% endfor %}
                    
                    <div class="footer">
                        <p>
                            이 이메일은 YouTube Shorts 도구에서 자동으로 발송되었습니다.<br>
                            알림 설정을 변경하시려면 <a href="https://shorts.ddns.net/notifications">알림 설정</a>에서 변경하실 수 있습니다.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            template = Template(template_str)
            return template.render(user=user, results=search_results, timestamp=timestamp)
        except Exception as e:
            self.app.logger.error(f"이메일 포맷팅 오류: {str(e)}")
            return "<p>이메일 생성 중 오류가 발생했습니다.</p>"
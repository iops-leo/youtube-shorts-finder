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
            # 검색 결과를 조회수 순으로 정렬
            for category in search_results:
                if category.get('videos'):
                    category['videos'].sort(key=lambda x: x.get('viewCount', 0), reverse=True)
            
            # 통계 계산
            total_videos = sum(len(category.get('videos', [])) for category in search_results)
            total_categories = sum(1 for category in search_results if len(category.get('videos', [])) > 0)
            # 이메일 템플릿 로드 (실제로는 파일에서 로드할 수 있음)
            template_str = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { 
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                        margin: 0; padding: 0; background-color: #f5f7fa; color: #2c3e50; 
                        line-height: 1.6;
                    }
                    .container { 
                        max-width: 800px; margin: 20px auto; padding: 0; 
                        background-color: #fff; border-radius: 12px; 
                        box-shadow: 0 4px 25px rgba(0,0,0,0.1); overflow: hidden;
                    }
                    .header { 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; padding: 30px 20px; text-align: center; 
                    }
                    .header h1 { 
                        margin: 0; font-size: 28px; font-weight: 600; 
                        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
                    }
                    .content { padding: 30px; }
                    .greeting { 
                        font-size: 18px; margin-bottom: 25px; color: #34495e;
                        text-align: center;
                    }
                    .timestamp {
                        background-color: #ecf0f1; padding: 15px; border-radius: 8px;
                        text-align: center; margin-bottom: 25px; color: #7f8c8d;
                        font-size: 14px;
                    }
                    
                    .video-card { 
                        border: 1px solid #e8ecef; margin-bottom: 20px; 
                        border-radius: 10px; background-color: #fff; 
                        transition: all 0.3s ease; overflow: hidden;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.08); position: relative;
                    }
                    .video-card:hover { 
                        transform: translateY(-2px); 
                        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                        border-color: #3498db;
                    }
                    
                    .video-rank {
                        position: absolute; top: 15px; left: 15px;
                        background: linear-gradient(135deg, #f39c12, #e67e22);
                        color: white; width: 30px; height: 30px;
                        border-radius: 50%; display: flex; align-items: center;
                        justify-content: center; font-weight: bold; font-size: 14px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2); z-index: 1;
                    }
                    
                    .video-content {
                        padding: 20px; padding-left: 60px;
                    }
                    
                    .video-title { 
                        font-weight: 600; font-size: 17px; margin-bottom: 12px; 
                        line-height: 1.4; color: #2c3e50;
                    }
                    .video-title a { 
                        color: #2c3e50; text-decoration: none; 
                        transition: color 0.3s ease;
                    }
                    .video-title a:hover { color: #3498db; }
                    
                    .translated-title {
                        color: #7f8c8d; font-size: 15px; margin-bottom: 12px;
                        font-style: italic; border-left: 3px solid #3498db;
                        padding: 8px 12px; background-color: #f8f9fa;
                        border-radius: 0 6px 6px 0; margin-left: -12px;
                    }
                    
                    .video-meta { 
                        display: flex; justify-content: space-between; 
                        align-items: center; margin-bottom: 15px;
                        flex-wrap: wrap; gap: 10px;
                    }
                    .channel-name { 
                        font-weight: 500; color: #34495e; font-size: 15px;
                    }
                    .channel-name a { color: #34495e; text-decoration: none; }
                    .channel-name a:hover { color: #3498db; }
                    .publish-date { 
                        color: #95a5a6; font-size: 13px; 
                    }
                    
                    .video-stats { 
                        display: flex; flex-wrap: wrap; gap: 20px;
                        padding: 15px; background-color: #f8f9fa;
                        border-radius: 8px; margin-top: 15px;
                    }
                    .stat-item { 
                        display: flex; align-items: center; gap: 6px;
                        font-size: 14px; color: #5a6c7d;
                    }
                    .stat-icon { font-size: 16px; }
                    .stat-number { font-weight: 600; color: #2c3e50; }
                    
                    .category-section { margin-bottom: 40px; }
                    .category-title { 
                        background: linear-gradient(135deg, #74b9ff, #0984e3);
                        color: white; padding: 18px 25px; margin-bottom: 25px; 
                        font-size: 20px; font-weight: 600; border-radius: 10px;
                        display: flex; align-items: center; gap: 10px;
                        box-shadow: 0 4px 15px rgba(116, 185, 255, 0.3);
                    }
                    
                    .summary { 
                        background: linear-gradient(135deg, #a8edea, #fed6e3);
                        padding: 25px; border-radius: 12px; margin-bottom: 30px;
                        text-align: center;
                    }
                    .summary-title { 
                        font-weight: 600; margin-bottom: 15px; 
                        font-size: 18px; color: #2c3e50;
                    }
                    .summary-stats {
                        display: flex; justify-content: center; gap: 30px;
                        flex-wrap: wrap; margin-top: 15px;
                    }
                    .summary-stat {
                        text-align: center;
                    }
                    .summary-number {
                        font-size: 24px; font-weight: bold; color: #2c3e50;
                        display: block;
                    }
                    .summary-label {
                        font-size: 13px; color: #7f8c8d; margin-top: 5px;
                    }
                    
                    .no-videos {
                        text-align: center; padding: 40px 20px;
                        color: #95a5a6; font-style: italic;
                        background-color: #f8f9fa; border-radius: 8px;
                    }
                    
                    .footer { 
                        background-color: #2c3e50; color: #bdc3c7; 
                        padding: 25px; text-align: center; font-size: 13px;
                        line-height: 1.6;
                    }
                    .footer a { color: #74b9ff; text-decoration: none; }
                    .footer a:hover { text-decoration: underline; }
                    
                    @media (max-width: 600px) {
                        .container { margin: 10px; border-radius: 8px; }
                        .content { padding: 20px; }
                        .video-content { padding-left: 20px; }
                        .video-rank { position: static; margin-bottom: 10px; }
                        .video-stats { gap: 15px; }
                        .summary-stats { gap: 20px; }
                        .category-title { font-size: 18px; padding: 15px 20px; }
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🎬 YouTube Shorts 인기 영상 알림</h1>
                    </div>
                    
                    <div class="content">
                        <div class="greeting">
                            안녕하세요, <strong>{{ user.name }}</strong>님!<br>
                            구독하신 채널 카테고리의 인기 YouTube Shorts를 알려드립니다.
                        </div>
                        
                        <div class="timestamp">
                            📅 검색 시간: {{ timestamp }}
                        </div>
                        
                        <!-- 검색 결과 요약 -->
                        <div class="summary">
                            <div class="summary-title">📊 검색 결과 요약</div>
                            <div class="summary-stats">
                                <div class="summary-stat">
                                    <span class="summary-number">{{ total_videos }}</span>
                                    <div class="summary-label">인기 Shorts 영상</div>
                                </div>
                                <div class="summary-stat">
                                    <span class="summary-number">{{ total_categories }}</span>
                                    <div class="summary-label">활성 카테고리</div>
                                </div>
                            </div> 
                        </div>
                        
                        {% for category in results %}
                        <div class="category-section">
                            <div class="category-title">
                                <span>📁</span>
                                <span>{{ category.name }}</span>
                                <span style="margin-left: auto; font-size: 16px; opacity: 0.9;">
                                    {{ category.videos|length }}개 영상
                                </span>
                            </div>
                            
                            {% if category.videos %}
                                {% for video in category.videos %}
                                <div class="video-card">
                                    <div class="video-rank">{{ loop.index }}</div>
                                    <div class="video-content">
                                        <div class="video-title">
                                            <a href="{{ video.url }}" target="_blank">{{ video.title }}</a>
                                        </div>
                                        
                                        {% if video.translated_title %}
                                        <div class="translated-title">
                                            {{ video.translated_title }}
                                        </div>
                                        {% endif %}
                                        
                                        <div class="video-meta">
                                            <div class="channel-name">
                                                <a href="https://www.youtube.com/channel/{{ video.channelId }}" target="_blank">
                                                    {{ video.channelTitle }}
                                                </a>
                                            </div>
                                            <div class="publish-date">
                                                📅 {{ video.publishedAt.split('T')[0] }}
                                            </div>
                                        </div>
                                        
                                        <div class="video-stats">
                                            <div class="stat-item">
                                                <span class="stat-icon">👁️</span>
                                                <span class="stat-number">{{ '{:,}'.format(video.viewCount) }}</span>
                                                <span>회</span>
                                            </div>
                                            <div class="stat-item">
                                                <span class="stat-icon">👍</span>
                                                <span class="stat-number">{{ '{:,}'.format(video.likeCount) }}</span>
                                                <span>개</span>
                                            </div>
                                            <div class="stat-item">
                                                <span class="stat-icon">💬</span>
                                                <span class="stat-number">{{ '{:,}'.format(video.commentCount) }}</span>
                                                <span>개</span>
                                            </div>
                                            <div class="stat-item">
                                                <span class="stat-icon">⏱️</span>
                                                <span class="stat-number">{{ video.duration }}</span>
                                                <span>초</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                {% endfor %}
                            {% else %}
                                <div class="no-videos">
                                    📭 조건에 맞는 영상이 없습니다.
                                </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    </div>
                    
                    <div class="footer">
                        <div style="margin-bottom: 15px;">
                            ⚙️ 이 이메일은 YouTube Shorts 도구에서 자동으로 발송되었습니다.
                        </div>
                        <div>
                            알림 설정을 변경하시려면 <a href="https://shorts.ddns.net/notifications">여기</a>를 클릭하세요.<br>
                            언급해주시면 언제든 도움을 드리겠습니다! 📧
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            template = Template(template_str)
            return template.render(
                user=user, 
                results=search_results, 
                timestamp=timestamp,
                total_videos=total_videos,
                total_categories=total_categories
            )
        except Exception as e:
            self.app.logger.error(f"이메일 포맷팅 오류: {str(e)}")
            return "<p>이메일 생성 중 오류가 발생했습니다.</p>"
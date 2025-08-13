# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

YouTube Shorts discovery and management platform built with Flask, featuring user authentication, channel categorization, email notifications, and YouTube management tools. Designed for Korean users with comprehensive API quota management and business management features.

## Tech Stack

- **Framework**: Flask 2.2.5 with Jinja2 templates
- **Language**: Python 3.9+
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Google OAuth 2.0 with Flask-Login
- **Background Tasks**: APScheduler for email notifications
- **Email Service**: SMTP with HTML templates
- **APIs**: YouTube Data API v3 (multiple API key support)
- **Additional**: MoviePy, speech recognition, translation (GoogleTranslator)
- **Deployment**: Railway/Heroku compatible with gunicorn

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start development server (using start.command)
./start.command

# Or start manually
python app.py

# Start with gunicorn (production)
gunicorn app:app --bind 0.0.0.0:8080 --timeout 300 --workers 2 --threads 4

# Run tests
python -m unittest tests/test_quota_manager.py
python -m unittest tests/test_quota_monitoring.py

# Test specific functionality
python test_search.py
```

Development server runs on http://localhost:8080

## Architecture & Code Structure

### Core Application Structure
- **Main Application**: `app.py` - Flask app with comprehensive routing and authentication
- **Database Models**: `models.py` - SQLAlchemy models for users, channels, categories, notifications, YouTube management
- **Search Engine**: `common_utils/search.py` - YouTube API integration with multi-key rotation and caching
- **Email Service**: `services/email_service.py` - SMTP email service with HTML templates
- **Notification Scheduler**: `services/notification_scheduler.py` - Background task scheduler for automated emails
- **YouTube Management**: `youtube_management.py` - Business management features (editors, works, revenue tracking)
- **Templates**: `templates/` - Jinja2 HTML templates with responsive design
- **Static Assets**: `static/` - CSS, JavaScript, and image assets

### Database Architecture
SQLAlchemy models with comprehensive relationships:
- **User Management**: `User`, `ApiLog`, role-based access control (pending/approved/admin)
- **Channel System**: `Channel`, `ChannelCategory`, `CategoryChannel` for organization
- **Search Features**: `SearchPreference`, `SearchHistory`, `SavedVideo` for user experience
- **API Management**: `UserApiKey`, `ApiKeyUsage`, `ApiKeyRotation` for quota tracking
- **Notifications**: `EmailNotification`, `NotificationSearch` for automated emails
- **Business Management**: `Editor`, `Work`, `Revenue`, `EditorRateHistory` for YouTube business tracking

### YouTube API Integration
Multi-layered API management system:
- **Quota Manager** (`common_utils/quota_manager.py`): Intelligent API key rotation with quota tracking
- **Search Service** (`common_utils/search.py`): Core YouTube API integration with caching
- **User API Service** (`services/user_api_service.py`): User-specific API key management
- **Monitoring** (`common_utils/quota_monitoring.py`): Real-time quota usage monitoring

Key features:
- Multi-API key support with automatic rotation when quota exceeded
- Intelligent caching system (28800s timeout) for API results
- Error handling and fallback mechanisms
- User-specific API key management for power users

### Authentication & Authorization
- Google OAuth 2.0 integration with proper credential management
- Role-based access control: `pending` → `approved` → `admin`
- Admin approval workflow for new users
- Session management with Flask-Login
- Security headers and CSRF protection

### Background Services
- **APScheduler**: Email notification scheduling with timezone support
- **ThreadPoolExecutor**: Concurrent API requests for improved performance
- **Email Service**: HTML email templates with SMTP delivery
- **Notification System**: Customizable email schedules for search results

## Key Technical Patterns

### Security Implementation
- Environment-based configuration with required variable validation
- API key rotation and quota management to prevent service disruption
- Secure logging filters to prevent sensitive data leakage
- ProxyFix middleware for proper header handling behind reverse proxies
- Rate limiting and quota monitoring for API usage

### Performance Optimization
- Multi-level caching: memory cache for API results, translation cache
- Connection pooling for database connections
- ThreadPoolExecutor for concurrent operations
- Efficient pagination for large datasets
- Background task processing for email notifications

### Error Handling & Resilience
- Comprehensive API error handling with automatic key switching
- Database transaction management with rollback capability
- Graceful degradation when external services are unavailable
- Detailed logging with rotation for debugging and monitoring

### Business Logic Architecture
YouTube Management system with comprehensive features:
- **Editor Management**: Contact information, rate tracking for basic/Japanese content
- **Work Tracking**: Status management (pending/in_progress/completed/cancelled)
- **Revenue Tracking**: Monthly revenue tracking with multi-channel support
- **Dashboard Analytics**: Weekly/monthly summaries with performance metrics

## Environment Configuration

Required environment variables:
```bash
# Security
SECRET_KEY=your_secret_key

# Database
DATABASE_URL=postgresql://...

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# YouTube API (multiple keys comma-separated)
YOUTUBE_API_KEY=key1,key2,key3

# Email Service
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_password
SENDER_EMAIL=your_sender@gmail.com

# Optional
FLASK_ENV=dev  # for development
PORT=8080
OAUTHLIB_INSECURE_TRANSPORT=1  # for local OAuth
```

## Common Development Tasks

1. **Database Schema Changes**: Use migration scripts in root directory (e.g., `migrate_*.py`)
2. **API Key Management**: Monitor quota usage through admin dashboard, add keys as comma-separated values
3. **Email Testing**: Use `/api/notifications/test` endpoint to verify email delivery
4. **Authentication Flow**: Test Google OAuth with both development and production callback URLs
5. **Background Tasks**: Verify APScheduler is running and email notifications are scheduled correctly
6. **Performance Monitoring**: Monitor API usage, database query performance, and cache hit rates
7. **Admin Features**: Test user approval workflow and admin panel functionality through `/admin/users`

### Development Environment Setup
1. Set `FLASK_ENV=dev` for local development
2. Use `OAUTHLIB_INSECURE_TRANSPORT=1` for local OAuth testing
3. Ensure PostgreSQL is running and DATABASE_URL is properly configured
4. Use admin panel to approve test users during development
5. Check `/logs/app.log` for debugging information

### API Integration Testing
- Test with multiple YouTube API keys to verify rotation functionality
- Monitor quota usage through `/api/quota/status` endpoint
- Test search functionality with various filters and parameters
- Verify caching behavior for repeated API calls
- Test error handling when API quotas are exceeded

## Git Commit Guidelines

**ALWAYS use Korean for commit messages** - 모든 커밋 메시지는 한글로 작성

Format:
```
기능명: 구체적인 변경사항 설명

- 세부 변경사항 1
- 세부 변경사항 2
- 기타 개선사항

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

Categories:
- **기능**: 새로운 기능 추가
- **수정**: 버그 수정
- **개선**: 기존 기능 향상
- **리팩토링**: 코드 구조 개선
- **보안**: 보안 관련 개선
- **데이터베이스**: 스키마 변경
- **API**: API 관련 변경
- **관리**: 관리 기능 개선
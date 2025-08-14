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
- **User Search Service**: `common_utils/user_search.py` - User-specific search functionality with personal API keys
- **Email Service**: `services/email_service.py` - SMTP email service with HTML templates
- **Notification Scheduler**: `services/notification_scheduler.py` - Background task scheduler for automated emails
- **User API Service**: `services/user_api_service.py` - User API key management with encryption and quota tracking
- **YouTube Management**: `youtube_management.py` - Business management features (editors, works, revenue tracking)
- **Templates**: `templates/` - Jinja2 HTML templates with responsive design (includes `api_keys.html`)
- **Static Assets**: `static/` - CSS, JavaScript, and image assets

### Database Architecture
SQLAlchemy models with comprehensive relationships:
- **User Management**: `User`, `ApiLog`, role-based access control (pending/approved/admin)
- **Channel System**: `Channel`, `ChannelCategory`, `CategoryChannel` for organization
- **Search Features**: `SearchPreference`, `SearchHistory`, `SavedVideo` for user experience
- **User API Management**: 
  - `UserApiKey`: 사용자별 암호화된 API 키 저장 (일일 할당량, 사용량 추적)
  - `ApiKeyUsage`: API 호출 이력 및 성능 메트릭 (응답시간, 성공률)
  - `ApiKeyRotation`: API 키 순환 로그 (할당량 초과, 오류 등)
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
- **User API Key Encryption**: Cryptography library를 사용한 API 키 암호화 저장
- Secure logging filters to prevent sensitive data leakage
- ProxyFix middleware for proper header handling behind reverse proxies
- Rate limiting and quota monitoring for API usage
- User-specific API key isolation and access control

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
2. **API Key Management System (NEW)**: 
   - **사용자 API 키 관리**: `/api-keys` 페이지에서 개인 API 키 추가/수정/삭제
   - **키 테스트**: `/api/user-api-keys/test/<key_id>` 엔드포인트로 API 키 유효성 검증
   - **할당량 모니터링**: 일일 사용량 및 할당량 추적 (`daily_quota`: 1,000-50,000)
   - **암호화 보안**: Fernet 대칭 암호화로 API 키 보안 저장
   - **자동 순환**: 할당량 초과 시 다음 키로 자동 전환
3. **시스템 API 키 관리**: 
   - Monitor quota usage through admin dashboard, add keys as comma-separated values
4. **Email Testing**: Use `/api/notifications/test` endpoint to verify email delivery
5. **Authentication Flow**: Test Google OAuth with both development and production callback URLs
6. **Background Tasks**: Verify APScheduler is running and email notifications are scheduled correctly
7. **Performance Monitoring**: Monitor API usage, database query performance, and cache hit rates
8. **Admin Features**: Test user approval workflow and admin panel functionality through `/admin/users`

## ⚠️ 중요: API 키 관리 시스템 마이그레이션 (2024-12-20)

**현재 진행 중인 대규모 마이그레이션**: 공용 API 키 → 사용자별 개인 API 키 시스템

### 📋 필수 참고 문서
**작업 전 반드시 확인**: `API_MIGRATION_LOG.md` 파일로 현재 진행 상황과 다음 작업 확인 필수

### 🔄 Phase 기반 순차 진행 (세션 연속성 보장)
현재 **Phase 1** 진행 중 - 각 Phase 완료 시 `API_MIGRATION_LOG.md` 업데이트 필수

#### Phase 1: 기본 기능 완성 (진행 중)
1. **데이터베이스 마이그레이션**: `python migrate_user_api_keys.py` 실행
2. **프론트엔드 완성**: `templates/api_keys.html` 완성
3. **CRUD 테스트**: 기본 API 키 관리 기능 검증

#### Phase 2: 시스템 통합 (대기 중)
1. 모든 검색 API를 사용자별 키로 전환
2. 에러 처리 및 사용자 경험 개선
3. 관리자 모니터링 대시보드 추가

#### Phase 3: 최적화 및 보안 (대기 중)
1. 성능 최적화 및 캐싱 개선
2. 보안 감사 및 강화
3. 사용자 가이드 문서화

#### Phase 4: 공용 키 시스템 제거 (최종)
1. 모든 사용자 개인 키 설정 확인
2. 공용 키 관련 코드 제거
3. 최종 검증

### ✅ 완료된 작업
- 사용자 API 키 데이터베이스 모델 (`UserApiKey`, `ApiKeyUsage`, `ApiKeyRotation`)
- 암호화 서비스 및 할당량 관리 시스템 (`services/user_api_service.py`)
- 사용자별 검색 서비스 (`common_utils/user_search.py`)
- API 키 관리 UI 엔드포인트 (10개 라우트 추가)
- 기존 검색 API 업데이트 (사용자별 키 우선 사용)

### ⏳ 현재 진행 중 (Phase 1)
- 프론트엔드 API 키 관리 페이지 완성 (`templates/api_keys.html`)
- 데이터베이스 마이그레이션 실행 (`migrate_user_api_keys.py`)
- 전체 시스템 테스트 및 검증

### 🚨 작업 규칙
1. **문서 우선**: 작업 시작 전 `API_MIGRATION_LOG.md` 확인 필수
2. **Phase 순서**: 반드시 Phase 1 → 2 → 3 → 4 순서로 진행
3. **업데이트 의무**: 각 작업 완료 시 마이그레이션 로그 즉시 업데이트
4. **세션 연속성**: 중단 시에도 문서를 통해 작업 연속성 유지
5. **테스트 필수**: 각 Phase 완료 전 기능 테스트 반드시 수행

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
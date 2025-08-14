# 로컬 개발 환경 설정 가이드

YouTube Shorts Finder를 로컬에서 개발하고 테스트하기 위한 설정 가이드입니다.

## 📋 사전 요구사항

1. **Python 3.9+** 설치
2. **PostgreSQL** 설치 및 실행
3. **Git** 설치

## 🚀 빠른 시작

### 1. 레포지토리 복제 및 이동
```bash
git clone <repository-url>
cd youtube-shorts-finder
```

### 2. 환경변수 설정
```bash
# .env.example 파일을 .env로 복사
cp .env.example .env

# .env 파일을 열어서 실제 값으로 수정
nano .env  # 또는 원하는 텍스트 에디터 사용
```

### 3. 필수 환경변수 설정

`.env` 파일에서 다음 값들을 실제 값으로 변경하세요:

```bash
# 보안 키 (랜덤 문자열 생성)
SECRET_KEY=생성한_랜덤_문자열

# 로컬 PostgreSQL 데이터베이스
DATABASE_URL=postgresql://username:password@localhost:5432/youtube_shorts_db

# Google OAuth (Google Cloud Console에서 생성)
GOOGLE_CLIENT_ID=생성한_클라이언트_ID
GOOGLE_CLIENT_SECRET=생성한_클라이언트_시크릿

# YouTube Data API 키 (Google Cloud Console에서 생성)
YOUTUBE_API_KEY=생성한_API_키1,생성한_API_키2
```

### 4. 애플리케이션 실행
```bash
# 실행 권한 부여
chmod +x start.command

# 애플리케이션 시작
./start.command
```

브라우저에서 `http://localhost:8080`으로 접속하세요.

## 🔧 상세 설정 가이드

### PostgreSQL 설정

1. **PostgreSQL 설치** (macOS)
```bash
brew install postgresql
brew services start postgresql
```

2. **데이터베이스 생성**
```bash
createdb youtube_shorts_db
```

3. **사용자 생성 (선택사항)**
```sql
psql postgres
CREATE USER youtuber WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE youtube_shorts_db TO youtuber;
```

### Google Cloud Console 설정

1. **프로젝트 생성**: Google Cloud Console에서 새 프로젝트 생성
2. **API 활성화**: YouTube Data API v3 활성화
3. **OAuth 2.0 설정**:
   - 승인된 리디렉션 URI: `http://localhost:8080/login/google/callback`
   - 승인된 JavaScript 원본: `http://localhost:8080`

### 환경변수 상세 설명

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `SECRET_KEY` | Flask 세션 암호화 키 | `your-random-secret-key-here` |
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql://user:pass@localhost:5432/db` |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | `123456789.apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 시크릿 | `GOCSPX-xxxxxxxxxxxxxxxx` |
| `YOUTUBE_API_KEY` | YouTube API 키 (콤마 구분) | `AIzaSyXXXXX,AIzaSyYYYYY` |

## 🧪 테스트 실행

```bash
# 단위 테스트 실행
python -m unittest tests/test_quota_manager.py
python -m unittest tests/test_quota_monitoring.py

# 특정 기능 테스트
python test_search.py
python test_user_api_service.py
```

## 📝 데이터베이스 마이그레이션

초기 데이터베이스 설정:
```bash
# 데이터베이스 테이블 생성
python migrate_db.py

# 사용자 API 키 테이블 생성 (최신 기능)
python migrate_user_api_keys.py
```

## 🚨 문제 해결

### 1. 데이터베이스 연결 오류
- PostgreSQL이 실행 중인지 확인
- DATABASE_URL이 올바른지 확인
- 데이터베이스와 사용자 권한 확인

### 2. Google OAuth 오류
- 클라이언트 ID/시크릿이 올바른지 확인
- 리디렉션 URI가 정확히 설정되었는지 확인
- `OAUTHLIB_INSECURE_TRANSPORT=1`이 설정되었는지 확인

### 3. YouTube API 오류
- API 키가 유효한지 확인
- YouTube Data API v3가 활성화되었는지 확인
- 할당량이 충분한지 확인

### 4. 포트 충돌
```bash
# 다른 포트 사용
export PORT=8081
python app.py --port=8081
```

## 🔒 보안 주의사항

1. **절대 커밋하지 말 것**: `.env` 파일은 `.gitignore`에 포함되어 있음
2. **API 키 관리**: 프로덕션과 개발용 키를 분리하여 사용
3. **SECRET_KEY**: 랜덤한 문자열로 생성 (최소 32자)

## 📊 개발 도구

### 로그 확인
```bash
tail -f logs/app.log
```

### 데이터베이스 직접 접근
```bash
psql postgresql://username:password@localhost:5432/youtube_shorts_db
```

### API 할당량 모니터링
브라우저에서 `/api/quota/status` 접속하여 현재 할당량 확인

## 🤝 기여하기

1. 기능 개발 시 새 브랜치 생성
2. 변경사항 테스트
3. 한글 커밋 메시지 사용 (CLAUDE.md 참조)
4. Pull Request 생성

## 📞 지원

문제가 발생하면 로그 파일(`logs/app.log`)을 확인하고, 필요시 이슈를 생성해주세요.
# migrate_user_api_keys.py
import os
import sys
from datetime import datetime

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from models import db
from sqlalchemy import text

def create_app():
    """Flask 앱 생성 및 설정"""
    app = Flask(__name__)
    
    # 환경변수에서 DATABASE_URL 가져오기
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app

def run_migration():
    """사용자 API 키 관련 테이블 마이그레이션 실행"""
    app = create_app()
    
    with app.app_context():
        try:
            print("🚀 사용자 API 키 테이블 마이그레이션 시작...")
            
            # 1. user_api_keys 테이블 생성
            print("📋 user_api_keys 테이블 생성 중...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    name VARCHAR(100) NOT NULL,
                    api_key VARCHAR(256) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    daily_quota INTEGER DEFAULT 10000,
                    usage_count INTEGER DEFAULT 0,
                    last_reset_date DATE DEFAULT CURRENT_DATE,
                    last_error TEXT,
                    error_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # 2. api_key_usage 테이블 생성
            print("📊 api_key_usage 테이블 생성 중...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS api_key_usage (
                    id SERIAL PRIMARY KEY,
                    api_key_id INTEGER NOT NULL REFERENCES user_api_keys(id) ON DELETE CASCADE,
                    user_id VARCHAR(128) NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    endpoint VARCHAR(50) NOT NULL,
                    quota_cost INTEGER DEFAULT 1,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    response_time FLOAT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # 3. api_key_rotations 테이블 생성
            print("🔄 api_key_rotations 테이블 생성 중...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS api_key_rotations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
                    from_key_id INTEGER REFERENCES user_api_keys(id) ON DELETE SET NULL,
                    to_key_id INTEGER REFERENCES user_api_keys(id) ON DELETE SET NULL,
                    reason VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # 4. 인덱스 생성
            print("🗂️  인덱스 생성 중...")
            
            # user_api_keys 인덱스
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_active 
                ON user_api_keys(user_id, is_active);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_reset_date 
                ON user_api_keys(user_id, last_reset_date);
            """))
            
            # api_key_usage 인덱스
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_key_timestamp 
                ON api_key_usage(api_key_id, timestamp);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_user_timestamp 
                ON api_key_usage(user_id, timestamp);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_api_key_usage_date_success 
                ON api_key_usage(DATE(timestamp), success);
            """))
            
            # 5. 트리거 생성 (updated_at 자동 업데이트)
            print("⚡ 트리거 생성 중...")
            db.session.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            db.session.execute(text("""
                DROP TRIGGER IF EXISTS update_user_api_keys_updated_at ON user_api_keys;
                CREATE TRIGGER update_user_api_keys_updated_at
                BEFORE UPDATE ON user_api_keys
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """))
            
            # 6. 커밋
            db.session.commit()
            print("✅ 모든 테이블과 인덱스가 성공적으로 생성되었습니다!")
            
            # 7. 테이블 목록 확인
            print("\n📋 생성된 테이블 확인:")
            result = db.session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('user_api_keys', 'api_key_usage', 'api_key_rotations')
                ORDER BY table_name;
            """))
            
            for row in result:
                print(f"  ✓ {row[0]}")
            
            # 8. 관리자 사용자에게 안내 메시지
            print("\n" + "="*60)
            print("🎉 사용자 API 키 관리 기능이 활성화되었습니다!")
            print("="*60)
            print("이제 사용자들이 다음을 할 수 있습니다:")
            print("  • 개인 YouTube Data API v3 키 등록 (최대 5개)")
            print("  • API 키별 일일 할당량 설정 및 관리")
            print("  • API 사용량 통계 확인")
            print("  • 키 순환 및 오류 모니터링")
            print("\n접속 방법:")
            print("  1. 로그인 후 'API 키' 메뉴 클릭")
            print("  2. Google Cloud Console에서 YouTube Data API v3 키 발급")
            print("  3. 발급받은 키를 등록하여 개인 할당량 사용")
            print("\n⚠️  중요 사항:")
            print("  • 환경변수에 API_ENCRYPTION_KEY 설정 권장")
            print("  • 기존 시스템 API 키는 계속 사용 가능 (백업용)")
            print("  • 사용자별 API 키 우선 사용, 없으면 시스템 키 사용")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 마이그레이션 중 오류 발생: {str(e)}")
            print("상세 오류 정보:")
            import traceback
            traceback.print_exc()
            return False
    
    return True

def verify_migration():
    """마이그레이션 결과 검증"""
    app = create_app()
    
    with app.app_context():
        try:
            # 테이블 존재 확인
            tables_to_check = ['user_api_keys', 'api_key_usage', 'api_key_rotations']
            
            for table in tables_to_check:
                result = db.session.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = '{table}';
                """))
                
                count = result.scalar()
                if count == 0:
                    print(f"❌ 테이블 {table}이 생성되지 않았습니다.")
                    return False
                else:
                    print(f"✅ 테이블 {table} 확인됨")
            
            # 인덱스 확인
            result = db.session.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename IN ('user_api_keys', 'api_key_usage', 'api_key_rotations')
                AND schemaname = 'public';
            """))
            
            indexes = [row[0] for row in result]
            print(f"✅ 생성된 인덱스 수: {len(indexes)}개")
            
            return True
            
        except Exception as e:
            print(f"❌ 검증 중 오류: {str(e)}")
            return False

if __name__ == "__main__":
    print("🔧 사용자 API 키 관리 시스템 마이그레이션")
    print("=" * 50)
    
    if run_migration():
        print("\n🔍 마이그레이션 결과 검증 중...")
        if verify_migration():
            print("\n🎉 마이그레이션이 성공적으로 완료되었습니다!")
            
            # 다음 단계 안내
            print("\n📝 다음 단계:")
            print("1. app.py에 API 키 관리 라우트 추가")
            print("2. models.py에 새 모델 클래스 추가")
            print("3. 템플릿에서 API 키 관리 메뉴 링크 추가")
            print("4. 웹 서버 재시작")
            
        else:
            print("\n❌ 마이그레이션 검증에 실패했습니다.")
            sys.exit(1)
    else:
        print("\n❌ 마이그레이션에 실패했습니다.")
        sys.exit(1)

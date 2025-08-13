#!/usr/bin/env python3
"""
사용자 API 키 테이블에 last_used 컬럼 추가하는 마이그레이션 스크립트
"""

import os
import sys
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Flask 앱 초기화
app = Flask(__name__)

# 환경 변수에서 데이터베이스 URL 가져오기
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

if not db_url:
    print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
    sys.exit(1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SQLAlchemy 초기화
db = SQLAlchemy(app)

def migrate_add_last_used_column():
    """사용자 API 키 테이블에 last_used 컬럼 추가"""
    
    with app.app_context():
        try:
            print("🔍 데이터베이스 연결 확인 중...")
            
            # 테이블 존재 여부 확인
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'user_api_keys'
                );
            """)).fetchone()
            
            if not result[0]:
                print("⚠️ user_api_keys 테이블이 존재하지 않습니다.")
                return False
                
            # last_used 컬럼 존재 여부 확인
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'user_api_keys' AND column_name = 'last_used'
                );
            """)).fetchone()
            
            if result[0]:
                print("✅ last_used 컬럼이 이미 존재합니다.")
                return True
                
            print("📝 last_used 컬럼 추가 중...")
            
            # last_used 컬럼 추가
            db.session.execute(text("""
                ALTER TABLE user_api_keys 
                ADD COLUMN last_used TIMESTAMP NULL;
            """))
            
            print("💾 컬럼 추가 인덱스 생성 중...")
            
            # 인덱스 추가 (선택사항 - 성능 향상을 위해)
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_user_api_keys_last_used 
                    ON user_api_keys (last_used);
                """))
                print("✅ 인덱스가 생성되었습니다.")
            except Exception as e:
                print(f"⚠️ 인덱스 생성 경고 (무시 가능): {e}")
            
            # 변경사항 커밋
            db.session.commit()
            
            print("✅ last_used 컬럼이 성공적으로 추가되었습니다!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ 마이그레이션 실패: {e}")
            return False

def verify_migration():
    """마이그레이션 결과 검증"""
    
    with app.app_context():
        try:
            # 컬럼 정보 조회
            result = db.session.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'user_api_keys' AND column_name = 'last_used';
            """)).fetchone()
            
            if result:
                column_name, data_type, is_nullable = result
                print(f"✅ 검증 완료:")
                print(f"   - 컬럼명: {column_name}")
                print(f"   - 데이터 타입: {data_type}")
                print(f"   - NULL 허용: {is_nullable}")
                return True
            else:
                print("❌ 검증 실패: last_used 컬럼을 찾을 수 없습니다.")
                return False
                
        except Exception as e:
            print(f"❌ 검증 중 오류: {e}")
            return False

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📊 사용자 API 키 테이블 last_used 컬럼 추가 마이그레이션")
    print("=" * 60)
    
    # 마이그레이션 실행
    if migrate_add_last_used_column():
        print("\n🔍 마이그레이션 결과 검증 중...")
        if verify_migration():
            print("\n🎉 마이그레이션이 성공적으로 완료되었습니다!")
            print("\n📝 다음 단계:")
            print("   1. 애플리케이션 재시작")
            print("   2. API 키 관리 페이지에서 기능 테스트")
            print("   3. 사용 통계 확인")
        else:
            print("\n❌ 마이그레이션 검증에 실패했습니다.")
            return 1
    else:
        print("\n❌ 마이그레이션에 실패했습니다.")
        return 1
    
    return 0

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
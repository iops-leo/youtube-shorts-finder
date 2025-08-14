#!/usr/bin/env python3
"""
EmailNotification 테이블의 active 컬럼을 is_active로 변경하는 마이그레이션 스크립트
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# .env 파일 로드 (개발 환경)
if os.environ.get('FLASK_ENV') != 'production':
    load_dotenv()

def fix_email_notification_column():
    """EmailNotification 테이블의 active 컬럼을 is_active로 변경"""
    
    # 데이터베이스 URL 가져오기
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    # Heroku 호환성을 위해 postgres://를 postgresql://로 변경
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        # 엔진 생성
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 트랜잭션 시작
            trans = conn.begin()
            
            try:
                print("🔄 EmailNotification 테이블 컬럼 변경 시작...")
                
                # 1. 컬럼이 이미 존재하는지 확인
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'email_notification' 
                    AND column_name IN ('active', 'is_active')
                """))
                
                existing_columns = [row[0] for row in result.fetchall()]
                print(f"📋 기존 컬럼: {existing_columns}")
                
                if 'is_active' in existing_columns:
                    print("✅ is_active 컬럼이 이미 존재합니다.")
                    trans.commit()
                    return True
                
                if 'active' in existing_columns:
                    # 2. active 컬럼을 is_active로 변경
                    print("🔄 active 컬럼을 is_active로 변경 중...")
                    conn.execute(text("""
                        ALTER TABLE email_notification 
                        RENAME COLUMN active TO is_active
                    """))
                    print("✅ active 컬럼을 is_active로 변경 완료")
                else:
                    # 3. is_active 컬럼이 없으면 새로 생성
                    print("🔄 is_active 컬럼 추가 중...")
                    conn.execute(text("""
                        ALTER TABLE email_notification 
                        ADD COLUMN is_active BOOLEAN DEFAULT TRUE
                    """))
                    print("✅ is_active 컬럼 추가 완료")
                
                # 4. 변경 사항 커밋
                trans.commit()
                print("✅ EmailNotification 테이블 마이그레이션 완료")
                return True
                
            except Exception as e:
                # 오류 발생 시 롤백
                trans.rollback()
                print(f"❌ 마이그레이션 중 오류 발생: {str(e)}")
                return False
                
    except Exception as e:
        print(f"❌ 데이터베이스 연결 오류: {str(e)}")
        return False

def verify_migration():
    """마이그레이션 결과 확인"""
    
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 컬럼 존재 확인
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'email_notification' 
                AND column_name = 'is_active'
            """))
            
            columns = result.fetchall()
            if columns:
                column = columns[0]
                print(f"✅ 검증 완료: is_active 컬럼이 존재합니다.")
                print(f"   - 데이터 타입: {column[1]}")
                print(f"   - NULL 허용: {column[2]}")
                print(f"   - 기본값: {column[3]}")
                
                # 데이터 확인
                count_result = conn.execute(text("""
                    SELECT COUNT(*) as total_count,
                           COUNT(CASE WHEN is_active = true THEN 1 END) as active_count,
                           COUNT(CASE WHEN is_active = false THEN 1 END) as inactive_count
                    FROM email_notification
                """))
                
                counts = count_result.fetchone()
                if counts:
                    print(f"   - 전체 레코드: {counts[0]}")
                    print(f"   - 활성 레코드: {counts[1]}")
                    print(f"   - 비활성 레코드: {counts[2]}")
                
                return True
            else:
                print("❌ 검증 실패: is_active 컬럼을 찾을 수 없습니다.")
                return False
                
    except Exception as e:
        print(f"❌ 검증 중 오류: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("📧 EmailNotification 테이블 컬럼 마이그레이션")
    print("=" * 60)
    
    # 마이그레이션 실행
    success = fix_email_notification_column()
    
    if success:
        print("\n🔍 마이그레이션 결과 검증 중...")
        verify_migration()
    
    print("\n" + "=" * 60)
    print("✅ 마이그레이션 완료" if success else "❌ 마이그레이션 실패")
    print("=" * 60)
#!/usr/bin/env python3
"""
정산 기능을 위한 데이터베이스 마이그레이션 스크립트
Work 테이블에 정산 관련 컬럼 추가
"""

import os
import sys
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# 환경 변수 로드
if os.environ.get('FLASK_ENV') != 'production':
    from dotenv import load_dotenv
    load_dotenv()

app = Flask(__name__)

# 데이터베이스 설정
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

def run_migration():
    """정산 관련 컬럼 추가 마이그레이션 실행"""
    try:
        with app.app_context():
            print("정산 기능 마이그레이션 시작...")
            
            # 1. works 테이블에 정산 관련 컬럼 추가
            migrations = [
                """
                ALTER TABLE works 
                ADD COLUMN IF NOT EXISTS settlement_status VARCHAR(20) DEFAULT 'pending';
                """,
                """
                ALTER TABLE works 
                ADD COLUMN IF NOT EXISTS settlement_date DATE;
                """,
                """
                ALTER TABLE works 
                ADD COLUMN IF NOT EXISTS settlement_amount INTEGER;
                """,
                """
                COMMENT ON COLUMN works.settlement_status IS '정산 상태: pending, settled';
                """,
                """
                COMMENT ON COLUMN works.settlement_date IS '정산 완료 날짜';
                """,
                """
                COMMENT ON COLUMN works.settlement_amount IS '정산 금액 (계산된 값 저장)';
                """
            ]
            
            for i, migration in enumerate(migrations, 1):
                try:
                    print(f"마이그레이션 {i}/{len(migrations)} 실행 중...")
                    db.session.execute(text(migration))
                    db.session.commit()
                    print(f"마이그레이션 {i} 완료")
                except Exception as e:
                    print(f"마이그레이션 {i} 실패: {str(e)}")
                    db.session.rollback()
                    if "already exists" not in str(e) and "duplicate column" not in str(e):
                        raise
            
            # 2. 기존 완료된 작업들의 정산 상태 초기화
            print("기존 데이터 정산 상태 초기화 중...")
            
            # 완료된 작업들은 정산 대기 상태로 설정
            update_existing = text("""
                UPDATE works 
                SET settlement_status = 'pending' 
                WHERE status = 'completed' AND settlement_status IS NULL;
            """)
            
            result = db.session.execute(update_existing)
            db.session.commit()
            
            print(f"기존 완료된 작업 {result.rowcount}개의 정산 상태를 'pending'으로 설정했습니다.")
            
            # 3. 인덱스 추가 (성능 최적화)
            indexes = [
                """
                CREATE INDEX IF NOT EXISTS idx_works_settlement_status 
                ON works(settlement_status);
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_works_settlement_date 
                ON works(settlement_date);
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_works_user_settlement 
                ON works(user_id, settlement_status, work_date);
                """
            ]
            
            for i, index_sql in enumerate(indexes, 1):
                try:
                    print(f"인덱스 {i}/{len(indexes)} 생성 중...")
                    db.session.execute(text(index_sql))
                    db.session.commit()
                    print(f"인덱스 {i} 생성 완료")
                except Exception as e:
                    print(f"인덱스 {i} 생성 실패: {str(e)}")
                    db.session.rollback()
                    if "already exists" not in str(e):
                        raise
            
            print("✅ 정산 기능 마이그레이션이 성공적으로 완료되었습니다!")
            
            # 마이그레이션 결과 요약
            print("\n📊 마이그레이션 결과:")
            print("- works.settlement_status 컬럼 추가 (기본값: 'pending')")
            print("- works.settlement_date 컬럼 추가")
            print("- works.settlement_amount 컬럼 추가")
            print("- 성능 최적화를 위한 인덱스 3개 추가")
            print("- 기존 완료된 작업들을 정산 대기 상태로 설정")
            
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {str(e)}")
        db.session.rollback()
        sys.exit(1)

def rollback_migration():
    """마이그레이션 롤백 (개발용)"""
    try:
        with app.app_context():
            print("정산 기능 마이그레이션 롤백 시작...")
            
            # 인덱스 삭제
            rollback_sql = [
                "DROP INDEX IF EXISTS idx_works_settlement_status;",
                "DROP INDEX IF EXISTS idx_works_settlement_date;", 
                "DROP INDEX IF EXISTS idx_works_user_settlement;",
                "ALTER TABLE works DROP COLUMN IF EXISTS settlement_status;",
                "ALTER TABLE works DROP COLUMN IF EXISTS settlement_date;",
                "ALTER TABLE works DROP COLUMN IF EXISTS settlement_amount;"
            ]
            
            for sql in rollback_sql:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                except Exception as e:
                    print(f"롤백 중 오류 (무시): {str(e)}")
                    db.session.rollback()
            
            print("✅ 마이그레이션 롤백이 완료되었습니다!")
            
    except Exception as e:
        print(f"❌ 롤백 실패: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback_migration()
    else:
        run_migration()
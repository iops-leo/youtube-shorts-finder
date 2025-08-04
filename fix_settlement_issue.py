#!/usr/bin/env python3
"""
편집자별 정산 데이터 문제 해결을 위한 스크립트
- settlement 관련 컬럼 추가
- 기존 완료된 작업들을 정산 대기 상태로 설정
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

def check_and_fix_settlement_columns():
    """정산 컬럼 확인 및 추가"""
    try:
        with app.app_context():
            print("🔍 정산 컬럼 확인 중...")
            
            # 1. 현재 테이블 구조 확인
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('works')]
            
            print("📋 현재 works 테이블 컬럼:")
            for col in columns:
                print(f"  - {col}")
            
            # 2. settlement 컬럼들이 있는지 확인
            settlement_columns = ['settlement_status', 'settlement_date', 'settlement_amount']
            missing_columns = [col for col in settlement_columns if col not in columns]
            
            if not missing_columns:
                print("✅ 모든 정산 컬럼이 이미 존재합니다.")
                
                # 데이터 상태 확인
                result = db.session.execute(text("""
                    SELECT 
                        COUNT(*) as total_works,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_works,
                        COUNT(CASE WHEN settlement_status = 'pending' THEN 1 END) as pending_settlements,
                        COUNT(CASE WHEN settlement_status = 'settled' THEN 1 END) as settled_works
                    FROM works
                """)).fetchone()
                
                print(f"📊 데이터 현황:")
                print(f"  - 전체 작업: {result.total_works}개")
                print(f"  - 완료된 작업: {result.completed_works}개") 
                print(f"  - 정산 대기: {result.pending_settlements}개")
                print(f"  - 정산 완료: {result.settled_works}개")
                
                # 정산 상태가 NULL인 완료된 작업들 확인
                null_settlement = db.session.execute(text("""
                    SELECT COUNT(*) as null_count
                    FROM works 
                    WHERE status = 'completed' AND settlement_status IS NULL
                """)).fetchone()
                
                if null_settlement.null_count > 0:
                    print(f"⚠️  정산 상태가 NULL인 완료된 작업: {null_settlement.null_count}개")
                    print("🔧 NULL 정산 상태를 'pending'으로 업데이트 중...")
                    
                    result = db.session.execute(text("""
                        UPDATE works 
                        SET settlement_status = 'pending' 
                        WHERE status = 'completed' AND settlement_status IS NULL
                    """))
                    db.session.commit()
                    
                    print(f"✅ {result.rowcount}개 작업의 정산 상태를 업데이트했습니다.")
                
                return True
            
            print(f"❌ 누락된 컬럼: {missing_columns}")
            print("🔧 정산 컬럼 추가 중...")
            
            # 3. 누락된 컬럼들 추가
            migrations = []
            
            if 'settlement_status' in missing_columns:
                migrations.append("""
                    ALTER TABLE works 
                    ADD COLUMN settlement_status VARCHAR(20) DEFAULT 'pending'
                """)
            
            if 'settlement_date' in missing_columns:
                migrations.append("""
                    ALTER TABLE works 
                    ADD COLUMN settlement_date DATE
                """)
            
            if 'settlement_amount' in missing_columns:
                migrations.append("""
                    ALTER TABLE works 
                    ADD COLUMN settlement_amount INTEGER
                """)
            
            # 4. 마이그레이션 실행
            for i, migration in enumerate(migrations, 1):
                print(f"📝 마이그레이션 {i}/{len(migrations)} 실행 중...")
                db.session.execute(text(migration))
                db.session.commit()
                print(f"✅ 마이그레이션 {i} 완료")
            
            # 5. 기존 완료된 작업들의 정산 상태 초기화
            print("🔄 기존 완료된 작업들의 정산 상태 초기화 중...")
            result = db.session.execute(text("""
                UPDATE works 
                SET settlement_status = 'pending' 
                WHERE status = 'completed' AND settlement_status IS NULL
            """))
            db.session.commit()
            
            print(f"✅ {result.rowcount}개 작업의 정산 상태를 'pending'으로 설정했습니다.")
            
            # 6. 인덱스 추가
            print("📊 인덱스 추가 중...")
            indices = [
                "CREATE INDEX IF NOT EXISTS idx_works_settlement_status ON works(settlement_status)",
                "CREATE INDEX IF NOT EXISTS idx_works_settlement_date ON works(settlement_date)",
                "CREATE INDEX IF NOT EXISTS idx_works_user_settlement ON works(user_id, settlement_status, work_date)"
            ]
            
            for index_sql in indices:
                db.session.execute(text(index_sql))
                db.session.commit()
            
            print("✅ 인덱스 추가 완료")
            
            # 7. 최종 상태 확인
            result = db.session.execute(text("""
                SELECT 
                    COUNT(*) as total_works,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_works,
                    COUNT(CASE WHEN settlement_status = 'pending' THEN 1 END) as pending_settlements,
                    COUNT(CASE WHEN settlement_status = 'settled' THEN 1 END) as settled_works
                FROM works
            """)).fetchone()
            
            print(f"\n🎉 정산 기능 설정 완료!")
            print(f"📊 최종 데이터 현황:")
            print(f"  - 전체 작업: {result.total_works}개")
            print(f"  - 완료된 작업: {result.completed_works}개") 
            print(f"  - 정산 대기: {result.pending_settlements}개")
            print(f"  - 정산 완료: {result.settled_works}개")
            
            return True
            
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    success = check_and_fix_settlement_columns()
    if success:
        print("\n✅ 편집자별 정산 데이터 문제가 해결되었습니다!")
        print("💡 이제 웹사이트에서 편집자별 정산 데이터를 확인할 수 있습니다.")
    else:
        print("\n❌ 문제 해결에 실패했습니다.")
        sys.exit(1)
#!/usr/bin/env python3
"""
정산 관리 기능 추가로 누락된 컬럼들을 데이터베이스에 추가하는 스크립트
"""
import os
import psycopg2
from dotenv import load_dotenv

# .env 파일이 있으면 로드
if os.path.exists('.env'):
    load_dotenv()

# 데이터베이스 URL 가져오기
db_url = os.environ.get('DATABASE_URL', '')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://')

if not db_url:
    print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
    exit(1)

print(f"📊 데이터베이스 연결 중...")

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    print("✅ 데이터베이스 연결 성공")
    
    # 각 테이블별로 누락된 컬럼 확인 및 추가
    migrations = []
    
    # 1. editors 테이블 확인
    print("\n🔍 editors 테이블 확인 중...")
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'editors'")
        existing_columns = [row[0] for row in cur.fetchall()]
        print(f"기존 컬럼: {existing_columns}")
        
        required_columns = {
            'id': 'SERIAL PRIMARY KEY',
            'user_id': 'VARCHAR(128) REFERENCES "user"(id)',
            'name': 'VARCHAR(100) NOT NULL',
            'contact': 'VARCHAR(50)',
            'email': 'VARCHAR(100)',
            'contract_date': 'DATE DEFAULT CURRENT_DATE',
            'basic_rate': 'INTEGER DEFAULT 15000',
            'japanese_rate': 'INTEGER DEFAULT 20000',
            'status': 'VARCHAR(20) DEFAULT \'active\'',
            'notes': 'TEXT',
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        if 'editors' not in [table[0] for table in cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'") or []]:
            # 테이블이 없으면 생성
            create_editors_sql = """
            CREATE TABLE editors (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(128) REFERENCES "user"(id),
                name VARCHAR(100) NOT NULL,
                contact VARCHAR(50),
                email VARCHAR(100),
                contract_date DATE DEFAULT CURRENT_DATE,
                basic_rate INTEGER DEFAULT 15000,
                japanese_rate INTEGER DEFAULT 20000,
                status VARCHAR(20) DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            migrations.append(("CREATE TABLE editors", create_editors_sql))
        else:
            # 누락된 컬럼 추가
            for col, definition in required_columns.items():
                if col not in existing_columns and col != 'id':  # id는 PRIMARY KEY라 별도 처리
                    alter_sql = f"ALTER TABLE editors ADD COLUMN IF NOT EXISTS {col} {definition};"
                    migrations.append((f"ADD editors.{col}", alter_sql))
    
    except Exception as e:
        print(f"editors 테이블 확인 중 에러: {e}")
    
    # 2. works 테이블 확인
    print("\n🔍 works 테이블 확인 중...")
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'works'")
        existing_columns = [row[0] for row in cur.fetchall()]
        print(f"기존 컬럼: {existing_columns}")
        
        if not existing_columns:  # 테이블이 없으면 생성
            create_works_sql = """
            CREATE TABLE works (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(128) REFERENCES "user"(id),
                editor_id INTEGER REFERENCES editors(id),
                title VARCHAR(200) NOT NULL,
                work_type VARCHAR(20) NOT NULL,
                work_date DATE NOT NULL,
                deadline DATE,
                rate INTEGER NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            migrations.append(("CREATE TABLE works", create_works_sql))
        else:
            # 누락된 컬럼들 확인
            required_work_columns = {
                'user_id': 'VARCHAR(128) REFERENCES "user"(id)',
                'editor_id': 'INTEGER REFERENCES editors(id)',
                'title': 'VARCHAR(200) NOT NULL',
                'work_type': 'VARCHAR(20) NOT NULL',
                'work_date': 'DATE NOT NULL',
                'deadline': 'DATE',
                'rate': 'INTEGER NOT NULL',
                'status': 'VARCHAR(20) DEFAULT \'pending\'',
                'notes': 'TEXT',
                'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
                'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            }
            
            for col, definition in required_work_columns.items():
                if col not in existing_columns:
                    alter_sql = f"ALTER TABLE works ADD COLUMN IF NOT EXISTS {col} {definition};"
                    migrations.append((f"ADD works.{col}", alter_sql))
    
    except Exception as e:
        print(f"works 테이블 확인 중 에러: {e}")
    
    # 3. revenues 테이블 확인 및 새 컬럼 추가
    print("\n🔍 revenues 테이블 확인 중...")
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'revenues'")
        existing_columns = [row[0] for row in cur.fetchall()]
        print(f"기존 컬럼: {existing_columns}")
        
        if not existing_columns:  # 테이블이 없으면 생성
            create_revenues_sql = """
            CREATE TABLE revenues (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(128) REFERENCES "user"(id),
                year_month VARCHAR(7) NOT NULL,
                youtube_revenue INTEGER DEFAULT 0,
                music_revenue INTEGER DEFAULT 0,
                other_revenue INTEGER DEFAULT 0,
                main_channel INTEGER DEFAULT 0,
                sub_channel1 INTEGER DEFAULT 0,
                sub_channel2 INTEGER DEFAULT 0,
                total_revenue INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            migrations.append(("CREATE TABLE revenues", create_revenues_sql))
        else:
            # 새로운 컬럼들 추가 (nullable=True로 기존 데이터 호환성 유지)
            new_revenue_columns = {
                'youtube_revenue': 'INTEGER DEFAULT 0',
                'music_revenue': 'INTEGER DEFAULT 0', 
                'other_revenue': 'INTEGER DEFAULT 0'
            }
            
            for col, definition in new_revenue_columns.items():
                if col not in existing_columns:
                    alter_sql = f"ALTER TABLE revenues ADD COLUMN IF NOT EXISTS {col} {definition};"
                    migrations.append((f"ADD revenues.{col}", alter_sql))
    
    except Exception as e:
        print(f"revenues 테이블 확인 중 에러: {e}")
    
    # 4. editor_rate_history 테이블 확인
    print("\n🔍 editor_rate_history 테이블 확인 중...")
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'editor_rate_history'")
        existing_columns = [row[0] for row in cur.fetchall()]
        
        if not existing_columns:  # 테이블이 없으면 생성
            create_rate_history_sql = """
            CREATE TABLE editor_rate_history (
                id SERIAL PRIMARY KEY,
                editor_id INTEGER REFERENCES editors(id),
                user_id VARCHAR(128) REFERENCES "user"(id),
                old_basic_rate INTEGER,
                new_basic_rate INTEGER,
                old_japanese_rate INTEGER,
                new_japanese_rate INTEGER,
                change_reason VARCHAR(200),
                effective_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            migrations.append(("CREATE TABLE editor_rate_history", create_rate_history_sql))
    
    except Exception as e:
        print(f"editor_rate_history 테이블 확인 중 에러: {e}")
    
    # 마이그레이션 실행
    if migrations:
        print(f"\n🚀 {len(migrations)}개의 마이그레이션을 실행합니다...")
        
        for description, sql in migrations:
            try:
                print(f"  ▶ {description}")
                cur.execute(sql)
                conn.commit()
                print(f"    ✅ 완료")
            except Exception as e:
                print(f"    ❌ 실패: {e}")
                conn.rollback()
    else:
        print("\n✅ 모든 테이블과 컬럼이 이미 존재합니다.")
    
    print("\n🎉 마이그레이션 완료!")
    
except Exception as e:
    print(f"❌ 데이터베이스 연결 실패: {e}")
    print("환경변수 DATABASE_URL을 확인해주세요.")
finally:
    if 'conn' in locals():
        conn.close()
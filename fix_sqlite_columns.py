#!/usr/bin/env python3
"""
SQLite 데이터베이스에서 정산 관리 기능 누락된 컬럼들을 추가하는 스크립트
"""
import sqlite3
import os

# SQLite 데이터베이스 파일 경로들
db_files = [
    'instance/test.db',
    'test_migration.db'
]

def check_and_fix_database(db_path):
    if not os.path.exists(db_path):
        print(f"❌ {db_path} 파일이 존재하지 않습니다.")
        return
    
    print(f"\n📊 {db_path} 데이터베이스 확인 중...")
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # 기존 테이블 목록 확인
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cur.fetchall()]
        print(f"기존 테이블: {existing_tables}")
        
        migrations = []
        
        # 1. editors 테이블 확인/생성
        if 'editors' not in existing_tables:
            create_editors_sql = """
            CREATE TABLE editors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                name TEXT NOT NULL,
                contact TEXT,
                email TEXT,
                contract_date DATE DEFAULT CURRENT_DATE,
                basic_rate INTEGER DEFAULT 15000,
                japanese_rate INTEGER DEFAULT 20000,
                status TEXT DEFAULT 'active',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user(id)
            );
            """
            migrations.append(("CREATE TABLE editors", create_editors_sql))
        else:
            # editors 테이블 컬럼 확인
            cur.execute("PRAGMA table_info(editors)")
            existing_columns = [row[1] for row in cur.fetchall()]
            print(f"editors 테이블 기존 컬럼: {existing_columns}")
            
            required_columns = [
                ('contract_date', 'DATE DEFAULT CURRENT_DATE'),
                ('basic_rate', 'INTEGER DEFAULT 15000'),
                ('japanese_rate', 'INTEGER DEFAULT 20000'),
                ('status', 'TEXT DEFAULT \'active\''),
                ('notes', 'TEXT'),
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for col_name, col_def in required_columns:
                if col_name not in existing_columns:
                    alter_sql = f"ALTER TABLE editors ADD COLUMN {col_name} {col_def};"
                    migrations.append((f"ADD editors.{col_name}", alter_sql))
        
        # 2. works 테이블 확인/생성
        if 'works' not in existing_tables:
            create_works_sql = """
            CREATE TABLE works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                editor_id INTEGER,
                title TEXT NOT NULL,
                work_type TEXT NOT NULL,
                work_date DATE NOT NULL,
                deadline DATE,
                rate INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user(id),
                FOREIGN KEY (editor_id) REFERENCES editors(id)
            );
            """
            migrations.append(("CREATE TABLE works", create_works_sql))
        else:
            # works 테이블 컬럼 확인
            cur.execute("PRAGMA table_info(works)")
            existing_columns = [row[1] for row in cur.fetchall()]
            print(f"works 테이블 기존 컬럼: {existing_columns}")
            
            required_columns = [
                ('user_id', 'TEXT'),
                ('editor_id', 'INTEGER'),
                ('title', 'TEXT NOT NULL'),
                ('work_type', 'TEXT NOT NULL'),
                ('work_date', 'DATE NOT NULL'),
                ('deadline', 'DATE'),
                ('rate', 'INTEGER NOT NULL'),
                ('status', 'TEXT DEFAULT \'pending\''),
                ('notes', 'TEXT'),
                ('created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for col_name, col_def in required_columns:
                if col_name not in existing_columns:
                    alter_sql = f"ALTER TABLE works ADD COLUMN {col_name} {col_def};"
                    migrations.append((f"ADD works.{col_name}", alter_sql))
        
        # 3. revenues 테이블 확인 (새 컬럼 추가)
        if 'revenues' in existing_tables:
            cur.execute("PRAGMA table_info(revenues)")
            existing_columns = [row[1] for row in cur.fetchall()]
            print(f"revenues 테이블 기존 컬럼: {existing_columns}")
            
            # 새로운 컬럼들 추가
            new_columns = [
                ('youtube_revenue', 'INTEGER DEFAULT 0'),
                ('music_revenue', 'INTEGER DEFAULT 0'),
                ('other_revenue', 'INTEGER DEFAULT 0')
            ]
            
            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    alter_sql = f"ALTER TABLE revenues ADD COLUMN {col_name} {col_def};"
                    migrations.append((f"ADD revenues.{col_name}", alter_sql))
        
        # 4. editor_rate_history 테이블 확인/생성
        if 'editor_rate_history' not in existing_tables:
            create_rate_history_sql = """
            CREATE TABLE editor_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                editor_id INTEGER,
                user_id TEXT,
                old_basic_rate INTEGER,
                new_basic_rate INTEGER,
                old_japanese_rate INTEGER,
                new_japanese_rate INTEGER,
                change_reason TEXT,
                effective_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (editor_id) REFERENCES editors(id),
                FOREIGN KEY (user_id) REFERENCES user(id)
            );
            """
            migrations.append(("CREATE TABLE editor_rate_history", create_rate_history_sql))
        
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
        
    except Exception as e:
        print(f"❌ 데이터베이스 처리 중 에러: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# 모든 데이터베이스 파일 처리
for db_file in db_files:
    check_and_fix_database(db_file)

print("\n🎉 마이그레이션 완료!")
print("\n📝 다음 단계:")
print("1. 애플리케이션을 재시작하세요")
print("2. 웹 브라우저에서 YouTube 관리 페이지를 새로고침하세요")
print("3. 여전히 문제가 있다면 브라우저 개발자 도구에서 구체적인 에러 메시지를 확인하세요")
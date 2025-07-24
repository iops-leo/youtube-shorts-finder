#!/usr/bin/env python3
"""
간단한 데이터베이스 마이그레이션 스크립트
SQLite를 사용해서 테이블 생성을 테스트합니다.
"""

import sqlite3
from datetime import datetime

def create_editor_rate_history_table():
    """SQLite에서 EditorRateHistory 테이블 생성"""
    
    # SQLite 연결
    conn = sqlite3.connect('test_migration.db')
    cursor = conn.cursor()
    
    try:
        print("EditorRateHistory 테이블 생성 중...")
        
        # 테이블 생성 SQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS editor_rate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            editor_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
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
        
        cursor.execute(create_table_sql)
        conn.commit()
        
        print("✅ editor_rate_history 테이블이 성공적으로 생성되었습니다.")
        
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(editor_rate_history);")
        columns = cursor.fetchall()
        
        print("\n📋 editor_rate_history 테이블 구조:")
        for col in columns:
            print(f"  - {col[1]}: {col[2]} {'(PRIMARY KEY)' if col[5] else ''}")
        
        # 인덱스 생성
        print("\n인덱스 생성 중...")
        
        index_sql = [
            "CREATE INDEX IF NOT EXISTS idx_editor_rate_history_editor_id ON editor_rate_history(editor_id);",
            "CREATE INDEX IF NOT EXISTS idx_editor_rate_history_user_id ON editor_rate_history(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_editor_rate_history_effective_date ON editor_rate_history(effective_date);"
        ]
        
        for sql in index_sql:
            cursor.execute(sql)
        
        conn.commit()
        print("✅ 인덱스가 성공적으로 생성되었습니다.")
        
        # 샘플 데이터 삽입 테스트
        print("\n샘플 데이터 삽입 테스트...")
        
        sample_data = """
        INSERT INTO editor_rate_history 
        (editor_id, user_id, old_basic_rate, new_basic_rate, old_japanese_rate, new_japanese_rate, 
         change_reason, effective_date, created_at)
        VALUES 
        (1, 'test_user_123', 15000, 17000, 20000, 22000, '성과 향상으로 인한 단가 인상', '2024-01-15', datetime('now'));
        """
        
        cursor.execute(sample_data)
        conn.commit()
        
        # 데이터 조회 테스트
        cursor.execute("SELECT * FROM editor_rate_history;")
        rows = cursor.fetchall()
        
        print(f"✅ 샘플 데이터 삽입 완료 (총 {len(rows)}개 레코드)")
        
        for row in rows:
            print(f"  📝 ID: {row[0]}, Editor: {row[1]}, 기본단가: {row[2]}→{row[3]}, 일본어단가: {row[4]}→{row[5]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {str(e)}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("YouTube 편집자 관리 시스템 - 단가 변경 이력 테이블 생성 테스트")
    print("=" * 70)
    
    success = create_editor_rate_history_table()
    
    if success:
        print("\n🎉 테이블 생성 및 테스트가 완료되었습니다!")
        print("\n새로 추가된 기능:")
        print("• 편집자 단가 변경 이력 추적")
        print("• 변경 사유 및 적용일 기록")
        print("• 변경한 사용자 추적")
        print("• 효율적인 조회를 위한 인덱스")
        
        print("\n실제 PostgreSQL 적용 시 다음 SQL을 실행하세요:")
        print("""
CREATE TABLE editor_rate_history (
    id SERIAL PRIMARY KEY,
    editor_id INTEGER NOT NULL REFERENCES editors(id),
    user_id VARCHAR(128) NOT NULL REFERENCES "user"(id),
    old_basic_rate INTEGER,
    new_basic_rate INTEGER,
    old_japanese_rate INTEGER,
    new_japanese_rate INTEGER,
    change_reason VARCHAR(200),
    effective_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_editor_rate_history_editor_id ON editor_rate_history(editor_id);
CREATE INDEX idx_editor_rate_history_user_id ON editor_rate_history(user_id);
CREATE INDEX idx_editor_rate_history_effective_date ON editor_rate_history(effective_date);
        """)
    else:
        print("\n❌ 테이블 생성이 실패했습니다.")
        exit(1)
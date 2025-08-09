#!/usr/bin/env python3
"""
SavedVideo 테이블 생성 마이그레이션 스크립트

사용법:
python migrate_saved_videos.py

이 스크립트는 saved_videos 테이블을 생성합니다.
- 사용자가 저장한 YouTube Shorts 영상 정보 저장
- 중복 저장 방지 (user_id + video_id unique constraint)
- 인덱스 최적화 (조회 성능 향상)
"""

import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from models import db, SavedVideo

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """데이터베이스 URL 가져오기"""
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://')
    
    if not db_url:
        logger.error("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        return None
    
    return db_url

def check_table_exists(engine, table_name):
    """테이블 존재 여부 확인"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                );
            """))
            return result.fetchone()[0]
    except Exception as e:
        logger.error(f"테이블 존재 확인 중 오류: {e}")
        return False

def create_saved_videos_table(engine):
    """saved_videos 테이블 생성"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS saved_videos (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(128) NOT NULL,
                    video_id VARCHAR(50) NOT NULL,
                    video_title VARCHAR(500) NOT NULL,
                    channel_title VARCHAR(255) NOT NULL,
                    channel_id VARCHAR(128),
                    thumbnail_url VARCHAR(500),
                    video_url VARCHAR(500) NOT NULL,
                    view_count INTEGER DEFAULT 0,
                    duration VARCHAR(20),
                    published_at TIMESTAMP,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    notes TEXT,
                    
                    -- 외래 키 제약조건
                    CONSTRAINT fk_saved_videos_user_id 
                        FOREIGN KEY (user_id) REFERENCES "user"(id),
                    
                    -- 중복 저장 방지
                    CONSTRAINT unique_user_video UNIQUE (user_id, video_id)
                );
            """))
            
            # 인덱스 생성
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_video_saved 
                ON saved_videos (user_id, video_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_saved_at 
                ON saved_videos (user_id, saved_at DESC);
            """))
            
            conn.commit()
            logger.info("saved_videos 테이블과 인덱스가 성공적으로 생성되었습니다.")
            return True
            
    except Exception as e:
        logger.error(f"테이블 생성 중 오류: {e}")
        return False

def verify_table_structure(engine):
    """테이블 구조 확인"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'saved_videos' 
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            logger.info("saved_videos 테이블 구조:")
            for col in columns:
                logger.info(f"  - {col[0]}: {col[1]} ({'NULL' if col[2] == 'YES' else 'NOT NULL'})")
            
            # 인덱스 확인
            result = conn.execute(text("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'saved_videos';
            """))
            
            indexes = result.fetchall()
            logger.info("인덱스:")
            for idx in indexes:
                logger.info(f"  - {idx[0]}")
            
            return True
            
    except Exception as e:
        logger.error(f"테이블 구조 확인 중 오류: {e}")
        return False

def main():
    """메인 실행 함수"""
    logger.info("SavedVideo 테이블 마이그레이션을 시작합니다...")
    
    # 데이터베이스 URL 확인
    db_url = get_database_url()
    if not db_url:
        return False
    
    # 데이터베이스 엔진 생성
    try:
        engine = create_engine(db_url)
        logger.info("데이터베이스 연결 성공")
    except Exception as e:
        logger.error(f"데이터베이스 연결 실패: {e}")
        return False
    
    # 테이블 존재 확인
    if check_table_exists(engine, 'saved_videos'):
        logger.warning("saved_videos 테이블이 이미 존재합니다.")
        choice = input("테이블 구조를 확인하시겠습니까? (y/N): ").lower()
        if choice == 'y':
            verify_table_structure(engine)
        return True
    
    # 테이블 생성
    success = create_saved_videos_table(engine)
    if not success:
        logger.error("테이블 생성에 실패했습니다.")
        return False
    
    # 테이블 구조 확인
    verify_table_structure(engine)
    
    logger.info("마이그레이션이 완료되었습니다!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
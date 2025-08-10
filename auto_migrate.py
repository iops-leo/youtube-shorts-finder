#!/usr/bin/env python3
"""
자동 데이터베이스 마이그레이션 스크립트
앱 시작시 자동으로 새로운 컬럼을 추가합니다.
"""

import os
import sys
from sqlalchemy import text, inspect

def check_and_add_columns(app, db):
    """필요한 컬럼들이 없으면 자동으로 추가"""
    try:
        with app.app_context():
            inspector = inspect(db.engine)
            
            # Revenue 테이블 컬럼 확인 및 추가
            revenue_columns = [col['name'] for col in inspector.get_columns('revenues')]
            
            new_columns = ['youtube_revenue', 'music_revenue', 'other_revenue']
            missing_columns = [col for col in new_columns if col not in revenue_columns]
            
            if missing_columns:
                print(f"Revenue 테이블에 누락된 컬럼 발견: {missing_columns}")
                
                for column in missing_columns:
                    try:
                        sql = f"ALTER TABLE revenues ADD COLUMN {column} INTEGER DEFAULT 0"
                        db.session.execute(text(sql))
                        print(f"✅ {column} 컬럼 추가 완료")
                    except Exception as e:
                        print(f"❌ {column} 컬럼 추가 실패: {str(e)}")
                        continue
                
                # 데이터 마이그레이션 (기존 컬럼에서 새 컬럼으로)
                try:
                    migrate_sql = """
                    UPDATE revenues SET 
                        youtube_revenue = COALESCE(main_channel, 0),
                        music_revenue = COALESCE(sub_channel1, 0), 
                        other_revenue = COALESCE(sub_channel2, 0)
                    WHERE (youtube_revenue IS NULL OR youtube_revenue = 0) 
                    AND (main_channel IS NOT NULL OR sub_channel1 IS NOT NULL OR sub_channel2 IS NOT NULL)
                    """
                    db.session.execute(text(migrate_sql))
                    print("✅ 기존 데이터 마이그레이션 완료")
                except Exception as e:
                    print(f"⚠️ 데이터 마이그레이션 건너뜀: {str(e)}")
                
                db.session.commit()
                print("✅ Revenue 테이블 컬럼 추가 완료")
            else:
                print("✅ Revenue 테이블 컬럼이 모두 존재합니다")
            
            # YouTube Dashboard 테이블 확인 및 생성
            tables = inspector.get_table_names()
            if 'youtube_dashboard' not in tables:
                try:
                    create_dashboard_sql = """
                    CREATE TABLE youtube_dashboard (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(128) NOT NULL REFERENCES "user"(id),
                        stats_date DATE NOT NULL,
                        total_editors INTEGER DEFAULT 0,
                        week_works INTEGER DEFAULT 0,
                        week_payment INTEGER DEFAULT 0,
                        month_revenue INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                    db.session.execute(text(create_dashboard_sql))
                    db.session.commit()
                    print("✅ YouTube Dashboard 테이블 생성 완료")
                except Exception as e:
                    print(f"⚠️ YouTube Dashboard 테이블 생성 실패: {str(e)}")

            # EmailNotification 테이블 weekly_settlement_active 컬럼 추가
            try:
                email_notif_columns = [col['name'] for col in inspector.get_columns('email_notification')]
                if 'weekly_settlement_active' not in email_notif_columns:
                    db.session.execute(text("ALTER TABLE email_notification ADD COLUMN weekly_settlement_active BOOLEAN DEFAULT FALSE"))
                    db.session.commit()
                    print("✅ email_notification.weekly_settlement_active 컬럼 추가 완료")
                else:
                    print("✅ email_notification.weekly_settlement_active 컬럼이 이미 존재합니다")
            except Exception as e:
                print(f"⚠️ email_notification 컬럼 확인/추가 중 오류: {str(e)}")

            # Editor Rate History 테이블 확인 및 생성
            if 'editor_rate_history' not in tables:
                try:
                    create_history_sql = """
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
                    )
                    """
                    db.session.execute(text(create_history_sql))
                    
                    # 인덱스 생성
                    index_sqls = [
                        "CREATE INDEX idx_editor_rate_history_editor_id ON editor_rate_history(editor_id)",
                        "CREATE INDEX idx_editor_rate_history_user_id ON editor_rate_history(user_id)",
                        "CREATE INDEX idx_editor_rate_history_effective_date ON editor_rate_history(effective_date)"
                    ]
                    
                    for idx_sql in index_sqls:
                        db.session.execute(text(idx_sql))
                    
                    db.session.commit()
                    print("✅ Editor Rate History 테이블 및 인덱스 생성 완료")
                except Exception as e:
                    print(f"⚠️ Editor Rate History 테이블 생성 실패: {str(e)}")
            
            return True
            
    except Exception as e:
        print(f"❌ 자동 마이그레이션 실패: {str(e)}")
        db.session.rollback()
        return False

def safe_migrate(app, db):
    """안전한 마이그레이션 실행"""
    print("🔄 자동 데이터베이스 마이그레이션 시작...")
    
    try:
        # 데이터베이스 연결 확인
        with app.app_context():
            db.session.execute(text("SELECT 1"))
            print("✅ 데이터베이스 연결 확인")
        
        # 컬럼 추가 및 테이블 생성
        success = check_and_add_columns(app, db)
        
        if success:
            print("🎉 자동 마이그레이션 완료!")
        else:
            print("⚠️ 일부 마이그레이션이 실패했지만 앱은 계속 실행됩니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 마이그레이션 중 오류 발생: {str(e)}")
        print("⚠️ 마이그레이션은 실패했지만 앱은 계속 실행됩니다.")
        return False
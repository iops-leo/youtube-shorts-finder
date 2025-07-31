#!/usr/bin/env python3
"""
Revenue 테이블 컬럼 마이그레이션 스크립트
main_channel, sub_channel1, sub_channel2 -> youtube_revenue, music_revenue, other_revenue
"""

import os
import sys
from sqlalchemy import text

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_revenue_columns():
    """Revenue 테이블 컬럼 마이그레이션"""
    try:
        from app import app, db
        
        with app.app_context():
            print("Revenue 테이블 컬럼 마이그레이션 시작...")
            
            # 현재 테이블 구조 확인
            try:
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'revenues' 
                    ORDER BY ordinal_position
                """))
                current_columns = [row[0] for row in result]
                print(f"현재 컬럼: {current_columns}")
                
                # 이전 컬럼들이 있는지 확인
                old_columns = ['main_channel', 'sub_channel1', 'sub_channel2']
                new_columns = ['youtube_revenue', 'music_revenue', 'other_revenue']
                
                has_old_columns = all(col in current_columns for col in old_columns)
                has_new_columns = all(col in current_columns for col in new_columns)
                
                if has_new_columns and not has_old_columns:
                    print("✅ 이미 새로운 컬럼 구조로 되어 있습니다.")
                    return True
                    
                if not has_old_columns:
                    print("❌ 예상된 이전 컬럼들을 찾을 수 없습니다.")
                    return False
                
                # 새 컬럼 추가 (아직 없는 경우)
                if not has_new_columns:
                    print("새 컬럼들을 추가하는 중...")
                    db.session.execute(text("""
                        ALTER TABLE revenues 
                        ADD COLUMN youtube_revenue INTEGER DEFAULT 0,
                        ADD COLUMN music_revenue INTEGER DEFAULT 0,
                        ADD COLUMN other_revenue INTEGER DEFAULT 0
                    """))
                    
                # 데이터 마이그레이션
                print("데이터를 마이그레이션하는 중...")
                db.session.execute(text("""
                    UPDATE revenues SET 
                        youtube_revenue = COALESCE(main_channel, 0),
                        music_revenue = COALESCE(sub_channel1, 0), 
                        other_revenue = COALESCE(sub_channel2, 0)
                    WHERE youtube_revenue IS NULL OR youtube_revenue = 0
                """))
                
                # 이전 컬럼 제거
                print("이전 컬럼들을 제거하는 중...")
                db.session.execute(text("""
                    ALTER TABLE revenues 
                    DROP COLUMN IF EXISTS main_channel,
                    DROP COLUMN IF EXISTS sub_channel1,
                    DROP COLUMN IF EXISTS sub_channel2
                """))
                
                db.session.commit()
                print("✅ 컬럼 마이그레이션이 완료되었습니다.")
                
                # 최종 확인
                result = db.session.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'revenues' 
                    ORDER BY ordinal_position
                """))
                final_columns = [row[0] for row in result]
                print(f"최종 컬럼: {final_columns}")
                
                return True
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ 마이그레이션 중 오류 발생: {str(e)}")
                return False
                
    except ImportError as e:
        print(f"❌ 모듈 import 오류: {str(e)}")
        print("가상환경이 활성화되어 있고 필요한 환경변수가 설정되어 있는지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("YouTube Shorts Finder - Revenue 테이블 컬럼 마이그레이션")
    print("=" * 60)
    
    success = migrate_revenue_columns()
    
    if success:
        print("\n🎉 마이그레이션이 성공적으로 완료되었습니다!")
        print("\n변경사항:")
        print("• main_channel → youtube_revenue")
        print("• sub_channel1 → music_revenue") 
        print("• sub_channel2 → other_revenue")
    else:
        print("\n❌ 마이그레이션이 실패했습니다.")
        print("환경변수를 확인하고 다시 시도해주세요.")
        sys.exit(1)
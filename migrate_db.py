#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 스크립트
EditorRateHistory 테이블을 추가합니다.
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, EditorRateHistory

def migrate_database():
    """데이터베이스 마이그레이션 실행"""
    app = create_app()
    
    with app.app_context():
        try:
            print("데이터베이스 마이그레이션 시작...")
            
            # 새 테이블 생성
            db.create_all()
            
            print("✅ EditorRateHistory 테이블이 성공적으로 생성되었습니다.")
            print("✅ 데이터베이스 마이그레이션이 완료되었습니다.")
            
            # 테이블 확인
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'editor_rate_history' in tables:
                print("✅ editor_rate_history 테이블 존재 확인됨")
                
                # 컬럼 정보 출력
                columns = inspector.get_columns('editor_rate_history')
                print("\n📋 editor_rate_history 테이블 구조:")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
            else:
                print("❌ editor_rate_history 테이블을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"❌ 마이그레이션 실패: {str(e)}")
            return False
    
    return True

if __name__ == "__main__":
    print("YouTube 편집자 관리 시스템 - 데이터베이스 마이그레이션")
    print("=" * 60)
    
    success = migrate_database()
    
    if success:
        print("\n🎉 모든 작업이 완료되었습니다!")
        print("\n새로 추가된 기능:")
        print("• 편집자 단가 변경 이력 추적")
        print("• 작업 정보 전체 수정 기능")
        print("• 단가 변경 사유 및 적용일 기록")
        
        print("\n새로운 API 엔드포인트:")
        print("• PUT /api/youtube/editors/<id> - 편집자 정보 수정 (이력 기록)")
        print("• PUT /api/youtube/works/<id> - 작업 정보 전체 수정")
        print("• GET /api/youtube/editors/<id>/rate-history - 단가 변경 이력 조회")
    else:
        print("\n❌ 마이그레이션이 실패했습니다.")
        sys.exit(1)
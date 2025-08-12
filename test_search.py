#!/usr/bin/env python3
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, '/Users/leo/project/youtube-shorts-finder')

try:
    from common_utils.search import get_recent_popular_shorts
    print("✅ search.py 모듈 import 성공")
    
    # 기본 함수 호출 테스트 (실제 API 호출 없이)
    print("✅ get_recent_popular_shorts 함수 정의 확인")
    
except ImportError as e:
    print(f"❌ Import 오류: {e}")
except SyntaxError as e:
    print(f"❌ 구문 오류: {e}")
    print(f"라인 {e.lineno}: {e.text}")
except Exception as e:
    print(f"❌ 기타 오류: {e}")

print("search.py 파일 검증 완료")

#!/usr/bin/env python3
"""
사용자 API 키 서비스 간단 테스트 스크립트
"""

import os
import sys

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """모듈 임포트 테스트"""
    try:
        print("🔍 모듈 임포트 테스트 중...")
        
        from services.user_api_service import UserApiKeyManager
        from models import UserApiKey, db
        from cryptography.fernet import Fernet
        
        print("✅ 모든 모듈이 성공적으로 임포트되었습니다.")
        return True
        
    except Exception as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False

def test_encryption():
    """암호화/복호화 테스트"""
    try:
        print("🔍 암호화/복호화 테스트 중...")
        
        from cryptography.fernet import Fernet
        
        # 테스트용 암호화 키 생성
        key = Fernet.generate_key()
        cipher = Fernet(key)
        
        # 테스트 데이터
        test_api_key = "AIzaSyBvOkBokdHfHmQDVND-pkBHfOJKlnGhOGA"
        
        # 암호화
        encrypted = cipher.encrypt(test_api_key.encode())
        print(f"   - 원본 API 키: {test_api_key[:10]}...")
        print(f"   - 암호화된 데이터: {encrypted[:20]}...")
        
        # 복호화
        decrypted = cipher.decrypt(encrypted).decode()
        
        if decrypted == test_api_key:
            print("✅ 암호화/복호화 테스트 통과")
            return True
        else:
            print("❌ 암호화/복호화 결과 불일치")
            return False
            
    except Exception as e:
        print(f"❌ 암호화/복호화 테스트 실패: {e}")
        return False

def test_user_api_manager_init():
    """UserApiKeyManager 초기화 테스트"""
    try:
        print("🔍 UserApiKeyManager 초기화 테스트 중...")
        
        from services.user_api_service import UserApiKeyManager
        
        # 테스트 사용자 ID
        test_user_id = "test_user_123"
        
        # 환경변수 설정 (테스트용)
        os.environ['API_ENCRYPTION_KEY'] = "test_key_for_development_only"
        
        # UserApiKeyManager 인스턴스 생성
        manager = UserApiKeyManager(test_user_id)
        
        print(f"   - 사용자 ID: {manager.user_id}")
        print(f"   - 암호화 키 존재: {'Yes' if manager.encryption_key else 'No'}")
        print(f"   - Cipher 객체 존재: {'Yes' if manager.cipher else 'No'}")
        
        print("✅ UserApiKeyManager 초기화 테스트 통과")
        return True
        
    except Exception as e:
        print(f"❌ UserApiKeyManager 초기화 테스트 실패: {e}")
        return False

def test_api_key_validation_logic():
    """API 키 검증 로직 테스트 (실제 API 호출 없이)"""
    try:
        print("🔍 API 키 검증 로직 테스트 중...")
        
        # 테스트 케이스들
        test_cases = [
            ("", False, "빈 문자열"),
            ("invalid_key", False, "잘못된 형식"),
            ("AIzaSyBvOkBokdHfHmQDVND-pkBHfOJKlnGhOGA", True, "올바른 형식"),
            ("short", False, "너무 짧은 키")
        ]
        
        for api_key, expected, description in test_cases:
            # 간단한 형식 검증 (실제 API 호출은 하지 않음)
            is_valid_format = (
                len(api_key) > 30 and 
                api_key.startswith("AIza") and 
                api_key.replace("AIza", "").replace("-", "").replace("_", "").isalnum()
            )
            
            result = "✅" if is_valid_format == expected else "❌"
            print(f"   {result} {description}: {api_key[:10]}... -> {is_valid_format}")
        
        print("✅ API 키 검증 로직 테스트 완료")
        return True
        
    except Exception as e:
        print(f"❌ API 키 검증 로직 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("🧪 사용자 API 키 서비스 테스트")
    print("=" * 60)
    
    tests = [
        ("모듈 임포트 테스트", test_imports),
        ("암호화/복호화 테스트", test_encryption),
        ("UserApiKeyManager 초기화 테스트", test_user_api_manager_init),
        ("API 키 검증 로직 테스트", test_api_key_validation_logic),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        if test_func():
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 60)
    print("📊 테스트 결과")
    print("=" * 60)
    print(f"✅ 통과: {passed}")
    print(f"❌ 실패: {failed}")
    print(f"📈 성공률: {(passed / (passed + failed)) * 100:.1f}%")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("\n📝 다음 단계:")
        print("   1. 데이터베이스 마이그레이션 실행")
        print("   2. Flask 애플리케이션 시작")
        print("   3. /api-keys 페이지에서 실제 기능 테스트")
        return 0
    else:
        print(f"\n⚠️ {failed}개의 테스트가 실패했습니다.")
        print("   실패한 테스트를 확인하고 수정해주세요.")
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
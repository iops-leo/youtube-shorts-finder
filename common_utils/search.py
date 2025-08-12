# core/search.py
import hashlib
import json
import time
import os
import googleapiclient.discovery
import isodate
import pytz
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from .quota_manager import initialize_quota_manager, get_quota_manager, QuotaErrorType

# 캐시 설정 (API 호출 결과를 메모리에 저장)
CACHE_TIMEOUT = 28800  # 캐시 유효시간 (초)
cache = {}

# 번역 캐시 설정
translation_cache = {}

# 할당량 관리자 초기화
api_key_str = os.environ.get('YOUTUBE_API_KEY', '')
quota_manager = initialize_quota_manager(api_key_str, daily_limit=10000)

# 호환성을 위한 기존 변수들
api_keys = quota_manager.api_keys if quota_manager else []
current_key_index = 0

# 보안: API 키 정보 로깅 방지
if quota_manager:
    print(f"✅ 할당량 관리자 초기화 완료: {len(api_keys)}개 키 로드")
else:
    print("⚠️ 경고: YOUTUBE_API_KEY 환경변수 미설정 또는 할당량 관리자 초기화 실패")

def _key_preview(key: str) -> str:
    """보안: API 키 미리보기 (전체 키 노출 방지)"""
    if not key:
        return "(없음)"
    # 8자리를 4자리로 축소하여 보안 강화
    return f"••••{key[-4:]}" if len(key) >= 4 else "••••"

def _is_quota_or_key_error(error_str: str) -> bool:
    # 영문/국문 키워드 모두 인식
    return (
        ('quota' in error_str) or ('exceeded' in error_str) or
        ('invalid' in error_str) or ('forbidden' in error_str) or
        ('api key not valid' in error_str) or ('daily' in error_str) or
        ('할당량' in error_str) or ('api 키' in error_str) or ('모든 api 키' in error_str)
    )

def get_current_api_key():
    """현재 사용할 API 키 반환"""
    if quota_manager:
        return quota_manager.get_current_api_key()
    return api_keys[current_key_index] if api_keys else None

def get_api_key_info():
    """API 키 정보 반환"""
    if quota_manager:
        status = quota_manager.get_quota_status()
        return {
            'total_keys': status['total_keys'],
            'current_key_index': status['current_key_index'],
            'current_key_preview': f"키{status['current_key_index'] + 1}" if status['current_key_index'] is not None else None,
            'quota_status': status
        }
    return {
        'total_keys': len(api_keys),
        'current_key_index': current_key_index if api_keys else None,
        'current_key_preview': _key_preview(api_keys[current_key_index]) if api_keys else None
    }

def switch_to_next_api_key():
    """다음 API 키로 전환"""
    if quota_manager:
        new_key = quota_manager.switch_to_next_key()
        if new_key:
            print(f"할당량 관리자: 다음 API 키로 전환 완료")
        return new_key
    
    # 기존 로직 (호환성 유지)
    global current_key_index
    if not api_keys:
        return None
        
    current_key_index = (current_key_index + 1) % len(api_keys)
    new_key = get_current_api_key()
    print(f"ℹ️ API 키 전환: 인덱스 {current_key_index}로 변경됨")
    return new_key

def translate_text(text, target_lang='ko'):
    """텍스트를 대상 언어로 번역"""
    """텍스트 번역 기능 비활성화 (리소스 절약)"""
    return None  # 번역하지 않고 None 반환
    if not text or text.strip() == "":
        return ""
        
    # 텍스트 길이 제한 (API 제한 고려)
    if len(text) > 5000:
        text = text[:5000]
    
    # 캐시 키 생성 (텍스트 + 대상 언어)
    cache_key = f"{text}_{target_lang}"
    
    # 캐시에서 번역 확인
    if cache_key in translation_cache:
        # 보안: 캐시 히트 로깅에서 내용 축소
        print(f"💾 번역 캐시 히트 (길이: {len(text)}자)")
        return translation_cache[cache_key]
    
    try:
        # 번역 실행
        translator = GoogleTranslator(source='auto', target=target_lang)
        translated = translator.translate(text)
        
        # 번역 결과가 None이거나 빈 문자열이면 원본 반환
        if not translated:
            return text
            
        # 번역 결과 캐싱
        translation_cache[cache_key] = translated
        
        # 보안: 번역 로깅에서 내용 축소 
        print(f"✅ 번역 완료 (입력: {len(text)}자, 출력: {len(translated)}자)")
        return translated
    except Exception as e:
        print(f"❌ 번역 오류: {type(e).__name__}")
        return text  # 오류 시 원본 반환
        
    # 번역 캐시 크기 제한
    if len(translation_cache) > 1000:
        # 가장 오래된 항목 50개 제거
        oldest_keys = list(translation_cache.keys())[:50]
        for key in oldest_keys:
            if key in translation_cache:
                del translation_cache[key]

def get_cache_key(params):
    """파라미터로부터 캐시 키 생성"""
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()

def get_from_cache(cache_key):
    """캐시에서 데이터 가져오기"""
    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if time.time() - timestamp < CACHE_TIMEOUT:
            return data
        else:
            del cache[cache_key]
    return None

def save_to_cache(cache_key, data):
    """캐시에 데이터 저장"""
    cache[cache_key] = (data, time.time())
    
    # 캐시 크기 제한 개선 (200개로 증가, 성능 향상)
    if len(cache) > 200:
        # 가장 오래된 20개 항목 제거 (배치 처리로 성능 향상)
        sorted_keys = sorted(cache.keys(), key=lambda k: cache[k][1])
        for key in sorted_keys[:20]:
            del cache[key]
        print(f"🗺️ 캐시 정리: {len(sorted_keys[:20])}개 항목 제거, 현재: {len(cache)}개")

def get_cache_stats():
    """캐시 통계 반환"""
    now = time.time()
    valid_entries = sum(1 for _, timestamp in cache.values() if now - timestamp < CACHE_TIMEOUT)
    
    return {
        'total_entries': len(cache),
        'valid_entries': valid_entries,
        'expired_entries': len(cache) - valid_entries,
        'translation_cache_size': len(translation_cache),
        'cache_timeout_hours': CACHE_TIMEOUT / 3600
    }

def get_youtube_api_service():
    """YouTube API 서비스 인스턴스 생성 (키 오류 시 다음 키로 전환)"""
    api_key = get_current_api_key()
    if not api_key:
        if quota_manager:
            error_type, user_message = quota_manager.handle_quota_error(
                "모든 API 키의 할당량이 초과되었습니다", "get_service"
            )
            # 명시적으로 할당량 관련 에러로 인식되도록 한국어 메시지 그대로 전달
            raise Exception("모든 YouTube API 키의 할당량이 초과되었습니다.")
        raise Exception("사용 가능한 YouTube API 키가 없습니다.")
        
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        return youtube
    except Exception as e:
        error_str = str(e).lower()
        if quota_manager and _is_quota_or_key_error(error_str):
            # 할당량 관리자를 통한 오류 처리
            error_type, user_message = quota_manager.handle_quota_error(str(e), "get_service")
            next_api_key = quota_manager.switch_to_next_key()
            if next_api_key:
                print(f"⚠️ 할당량/키 오류로 다음 API 키({_key_preview(next_api_key)})로 전환")
                return googleapiclient.discovery.build("youtube", "v3", developerKey=next_api_key)
            else:
                raise Exception(user_message)
        elif _is_quota_or_key_error(error_str):
            # 기존 로직 (호환성)
            next_api_key = switch_to_next_api_key()
            if next_api_key:
                print(f"할당량 초과로 다음 API 키로 전환합니다.")
                return googleapiclient.discovery.build("youtube", "v3", developerKey=next_api_key)
        # 다른 오류는 그대로 전파
        raise

def execute_youtube_api_call(api_call_func, endpoint_name, max_retries=3):
    """
    YouTube API 호출을 실행하고 할당량을 추적하는 헬퍼 함수
    
    Args:
        api_call_func: 실행할 API 호출 함수
        endpoint_name: API 엔드포인트 이름 (예: 'search.list')
        max_retries: 최대 재시도 횟수
    
    Returns:
        API 응답 결과
    
    Raises:
        Exception: API 호출 실패 시
    """
    for attempt in range(max_retries):
        try:
            # API 호출 실행
            result = api_call_func()
            
            # 성공한 경우 할당량 기록
            if quota_manager:
                quota_manager.record_api_call(endpoint_name, success=True)
            
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            # 할당량/키 관련 오류인지 확인
            if _is_quota_or_key_error(error_str):
                if quota_manager:
                    # 할당량 관리자를 통한 오류 처리
                    error_type, user_message = quota_manager.handle_quota_error(str(e), endpoint_name)
                    
                    # 다른 키로 전환 시도
                    next_key = quota_manager.switch_to_next_key()
                    if next_key and attempt < max_retries - 1:
                    print(f"🔄 [{endpoint_name}] API 키 전환({_key_preview(next_key)}) 후 재시도 ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        # 더 이상 시도할 수 없는 경우
                        raise Exception(user_message)
                else:
                    # 기존 로직 (호환성)
                    next_key = switch_to_next_api_key()
                    if next_key and attempt < max_retries - 1:
                    print(f"🔄 [{endpoint_name}] API 키 전환 후 재시도 ({attempt + 1}/{max_retries})")
                        continue
                    else:
                        raise Exception("모든 YouTube API 키의 할당량이 초과되었습니다.")
            else:
                # 할당량 외 다른 오류
                if quota_manager:
                    quota_manager.record_api_call(endpoint_name, success=False, error_message=str(e))
                
                # 재시도 가능한 오류인지 확인 (네트워크 오류 등)
                if any(keyword in error_str for keyword in ['timeout', 'connection', 'network']):
                    if attempt < max_retries - 1:
                        print(f"🌐 [{endpoint_name}] 네트워크 오류로 재시도 ({attempt + 1}/{max_retries})")
                        time.sleep(1)  # 1초 대기 후 재시도
                        continue
                
                # 재시도 불가능한 오류
                raise
    
    # 모든 재시도 실패
    raise Exception(f"API 호출 실패: {endpoint_name} (최대 {max_retries}회 재시도 후 실패)")

# 이하의 고수준 검색 함수들에서는 quota_manager가 있는 경우 그 로직을 우선 사용하고,
# 호환성 블록은 그대로 유지합니다.

def search_by_keyword_based_shorts(min_views=100000, days_ago=5, max_results=20,
                                   category_id=None, region_code="KR", language=None, keyword=None):
    """
    키워드 기반 영상 검색 - API 키 순환 로직 강화
    제한사항 적용: 최소 조회수 10만, 최대 기간 5일, 최대 20개 결과
    """
    filtered_videos = []
    all_api_keys_exhausted = False  # 모든 API 키 소진 여부 플래그
    
    try:
        published_after = (datetime.utcnow() - timedelta(days=days_ago)).isoformat("T") + "Z"

        search_params = {
            'part': 'snippet',
            'maxResults': 50,
            'order': 'viewCount',
            'type': 'video',
            'videoDuration': 'short',
            'publishedAfter': published_after,
            'regionCode': region_code
        }

        if keyword:
            search_params['q'] = keyword
        if category_id and category_id != 'any':
            search_params['videoCategoryId'] = category_id
        if language and language != 'any':
            search_params['relevanceLanguage'] = language

        # 보안: 검색 파라미터에서 API 키 제거 및 제한 반영
        safe_params = {k: v for k, v in search_params.items() if k != 'key' and 'api' not in k.lower()}
        print(f"🔍 [키워드 검색] 조건: {safe_params}")
        print(f"⚙️ [제한사항] 최소조회수: {min_views:,}, 기간: {days_ago}일, 최대결과: {max_results}개")
        all_video_ids = []
        next_page_token = None

        # 페이지네이션으로 영상 ID 수집
        while len(all_video_ids) < max_results and not all_api_keys_exhausted:
            if next_page_token:
                search_params['pageToken'] = next_page_token
            
            # API 키 순환을 위한 최대 시도 횟수
            max_api_key_attempts = len(api_keys) if api_keys else 1
            current_attempt = 0
            page_processed = False
            
            while current_attempt < max_api_key_attempts and not page_processed:
                try:
                    youtube = get_youtube_api_service()
                    search_response = execute_youtube_api_call(
                        lambda: youtube.search().list(**search_params).execute(),
                        'search.list'
                    )
                    items = search_response.get('items', [])
                    video_ids = [item['id']['videoId'] for item in items]
                    all_video_ids.extend(video_ids)
                    
                    print(f"📊 페이지 결과: {len(items)}개 항목 발견 (총 {len(all_video_ids)}개)")
                    next_page_token = search_response.get('nextPageToken')
                    page_processed = True
                    
                    if not next_page_token or len(items) == 0:
                        break  # 더 이상 페이지가 없거나 결과가 없으면 종료
                        
                except Exception as e:
                    error_str = str(e).lower()
                    if _is_quota_or_key_error(error_str):
                        next_key = quota_manager.switch_to_next_key() if quota_manager else switch_to_next_api_key()
                        if next_key:
                            print(f"⚠️ [검색 중 할당량/키 오류] 다음 API 키({_key_preview(next_key)})로 전환")
                            current_attempt += 1
                        else:
                            print("🚫 [모든 API 키 소진] 더 이상 사용 가능한 API 키가 없음")
                            all_api_keys_exhausted = True
                            break
                    else:
                        # 할당량 외 다른 오류
                        print(f"❌ [검색 오류] {type(e).__name__}: {str(e)[:100]}")
                        page_processed = True
                        break
            
            # 이 페이지 처리가 실패했고 모든 API 키가 소진되었으면 루프 종료
            if not page_processed and all_api_keys_exhausted:
                break

        # 최대 결과 수 제한
        if len(all_video_ids) > max_results:
            all_video_ids = all_video_ids[:max_results]

        # 영상 상세 정보 가져오기 (50개씩 배치 처리)
        for i in range(0, len(all_video_ids), 50):
            if all_api_keys_exhausted:
                break
                
            batch_ids = all_video_ids[i:i+50]
            batch_processed = False
            current_attempt = 0
            
            while current_attempt < max_api_key_attempts and not batch_processed:
                try:
                    youtube = get_youtube_api_service()
                    video_response = execute_youtube_api_call(
                        lambda: youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=','.join(batch_ids)
                        ).execute(),
                        'videos.list'
                    )

                    for item in video_response.get('items', []):
                        try:
                            view_count = int(item['statistics'].get('viewCount', 0))
                            duration = item['contentDetails']['duration']
                            duration_seconds = isodate.parse_duration(duration).total_seconds()

                            if view_count < min_views or duration_seconds > 60:
                                continue

                            title = item['snippet']['title']
                            translated_title = None
                            if not any('\uAC00' <= c <= '\uD7A3' for c in title):
                                translated_title = translate_text(title, 'ko')

                            thumbnail_url = item['snippet']['thumbnails'].get('high', {}).get('url', '')

                            filtered_videos.append({
                                'id': item['id'],
                                'title': title,
                                'translated_title': translated_title,
                                'channelTitle': item['snippet']['channelTitle'],
                                'channelId': item['snippet']['channelId'],
                                'publishedAt': item['snippet']['publishedAt'],
                                'description': item['snippet'].get('description', ''),
                                'viewCount': view_count,
                                'likeCount': int(item['statistics'].get('likeCount', 0)),
                                'commentCount': int(item['statistics'].get('commentCount', 0)),
                                'duration': round(duration_seconds),
                                'url': f"https://www.youtube.com/shorts/{item['id']}",
                                'thumbnail': thumbnail_url,
                                'regionCode': region_code,
                                'isVertical': True
                            })

                        except Exception as ve:
                            print(f"❌ [상세 처리 오류] {type(ve).__name__}")
                            continue
                            
                    batch_processed = True

                except Exception as e:
                    error_str = str(e).lower()
                    if _is_quota_or_key_error(error_str):
                        next_key = quota_manager.switch_to_next_key() if quota_manager else switch_to_next_api_key()
                        if next_key:
                            print(f"⚠️ [상세 조회 중 할당량/키 오류] 다음 API 키({_key_preview(next_key)})로 전환")
                            current_attempt += 1
                        else:
                            print("🚫 [모든 API 키 소진] 더 이상 사용 가능한 API 키가 없음")
                            all_api_keys_exhausted = True
                            break
                    else:
                        # 할당량 외 다른 오류
                        print(f"❌ [상세 조회 오류] {type(e).__name__}: {str(e)[:100]}")
                        batch_processed = True
                        break

        # 최신순 정렬 및 제한
        filtered_videos.sort(key=lambda x: datetime.strptime(x['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
        # 모든 키 소진 상태에서 결과가 없다면 예외로 상위에 알림
        if all_api_keys_exhausted and len(filtered_videos) == 0:
            raise Exception("모든 YouTube API 키의 할당량이 초과되었습니다.")
        return filtered_videos[:max_results]

    except Exception as e:
        print(f"❌ [키워드 기반 검색 오류] {type(e).__name__}: {str(e)[:100]}")
        # 상위에서 구분 처리할 수 있도록 예외 그대로 전파
        raise

def get_recent_popular_shorts(min_views=100000, days_ago=5, max_results=20,
                             category_id=None, region_code="KR", language=None,
                             channel_ids=None, keyword=None):
    """
    채널 ID 기반 최신 쇼츠 수집 방식 - API 키 순환 로직 강화
    제한사항 적용: 최소 조회수 10만, 최대 기간 5일, 채널당 최대 20개
    """
    all_filtered_videos = []
    all_api_keys_exhausted = False  # 모든 API 키 소진 여부 플래그

    if isinstance(channel_ids, str):
        channel_id_list = [ch.strip() for ch in channel_ids.split(',') if ch.strip()]
    else:
        channel_id_list = channel_ids or []

    if channel_id_list:
        # 채널 개수 제한 (20개)
        if len(channel_id_list) > 20:
            print(f"⚠️ [채널 개수 제한] {len(channel_id_list)}개 입력 → 20개로 제한")
            channel_id_list = channel_id_list[:20]
            
        print(f"📺 총 {len(channel_id_list)}개 채널에서 직접 영상 수집 중...")
        print(f"⚙️ [제한사항] 최소조회수: {min_views:,}, 기간: {days_ago}일, 채널당 최대: {max_results}개")
        
        # 날짜 필터 설정
        published_after = None
        if days_ago > 0:
            published_after = (datetime.utcnow() - timedelta(days=days_ago)).isoformat("T") + "Z"
            print(f"📅 날짜 필터: {days_ago}일 전 ({published_after}) 이후 영상만 검색")

        for channel_id in channel_id_list:
            # 모든 API 키가 소진되었으면 더 이상 처리하지 않음
            if all_api_keys_exhausted:
                break
                
            max_api_key_attempts = len(api_keys) if api_keys else 1
            current_attempt = 0
            channel_processed = False  # 현재 채널 처리 완료 여부
            
            while current_attempt < max_api_key_attempts and not channel_processed:
                try:
                    youtube = get_youtube_api_service()

                    # 각 채널당 최신 영상 검색 (날짜 필터 포함)
                    search_params = {
                        'part': 'snippet',
                        'channelId': channel_id,
                        'order': 'date',
                        'type': 'video',
                        'maxResults': min(50, max(1, max_results))  # 더 많은 결과로 늘려서 필터링 후에도 충분한 결과 확보
                    }
                    
                    # 날짜 필터 적용
                    if published_after:
                        search_params['publishedAfter'] = published_after
                    
                    search_response = execute_youtube_api_call(
                        lambda: youtube.search().list(**search_params).execute(),
                        'search.list'
                    )

                    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

                    if not video_ids:
                        channel_processed = True  # 영상이 없으면 처리 완료로 표시
                        continue

                    # 비디오 상세 정보 조회
                    try:
                        video_response = execute_youtube_api_call(
                            lambda: youtube.videos().list(
                                part='snippet,statistics,contentDetails',
                                id=','.join(video_ids)
                            ).execute(),
                            'videos.list'
                        )
                        
                        for item in video_response.get('items', []):
                            try:
                                view_count = int(item['statistics'].get('viewCount', 0))
                                duration = item['contentDetails']['duration']
                                duration_seconds = isodate.parse_duration(duration).total_seconds()
                                
                                # 추가 날짜 필터링 (클라이언트 사이드에서 한 번 더 확인)
                                if days_ago > 0:
                                    published_at = datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                                    cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
                                    if published_at < cutoff_date:
                                        print(f"날짜 필터링: {item['snippet']['title']} - 게시일 {published_at.strftime('%Y-%m-%d')}가 기준일 {cutoff_date.strftime('%Y-%m-%d')}보다 이전")
                                        continue

                                if view_count < min_views or duration_seconds > 60:
                                    continue

                                title = item['snippet']['title']
                                translated_title = None
                                if not any('\uAC00' <= char <= '\uD7A3' for char in title):
                                    translated_title = translate_text(title, 'ko')

                                thumbnail_url = item['snippet']['thumbnails'].get('high', {}).get('url', '')

                                all_filtered_videos.append({
                                    'id': item['id'],
                                    'title': title,
                                    'translated_title': translated_title,
                                    'channelTitle': item['snippet']['channelTitle'],
                                    'channelId': item['snippet']['channelId'],
                                    'publishedAt': item['snippet']['publishedAt'],
                                    'description': item['snippet'].get('description', ''),
                                    'viewCount': view_count,
                                    'likeCount': int(item['statistics'].get('likeCount', 0)),
                                    'commentCount': int(item['statistics'].get('commentCount', 0)),
                                    'duration': round(duration_seconds),
                                    'url': f"https://www.youtube.com/shorts/{item['id']}",
                                    'thumbnail': thumbnail_url,
                                    'regionCode': region_code,
                                    'isVertical': True
                                })

                            except Exception as ve:
                                print(f"[비디오 개별 처리 오류] {str(ve)}")
                                continue
                        
                        channel_processed = True  # 채널 처리 완료
                        
                    except Exception as e:
                        # 비디오 목록 조회 중 오류
                        error_str = str(e).lower()
                        if _is_quota_or_key_error(error_str):
                            next_key = quota_manager.switch_to_next_key() if quota_manager else switch_to_next_api_key()
                            if next_key:
                                print(f"[비디오 조회 중 할당량/키 오류] 채널 {channel_id} - 다음 API 키({_key_preview(next_key)})로 전환")
                                current_attempt += 1
                                continue
                            else:
                                print("[모든 API 키 소진] 더 이상 사용 가능한 API 키가 없습니다.")
                                all_api_keys_exhausted = True
                                break
                        else:
                            # 할당량 외 다른 오류는 이 채널 건너뛰기
                            print(f"[비디오 조회 오류] 채널 {channel_id} - {str(e)}")
                            channel_processed = True
                            break

                except Exception as e:
                    # 채널 검색 중 오류
                    error_str = str(e).lower()
                    if _is_quota_or_key_error(error_str):
                        # 상태 반영
                        if quota_manager:
                            quota_manager.handle_quota_error(str(e), 'search.list')
                        next_key = quota_manager.switch_to_next_key() if quota_manager else switch_to_next_api_key()
                        if next_key:
                            print(f"[채널 검색 중 할당량/키 오류] 채널 {channel_id} - 다음 API 키({_key_preview(next_key)})로 전환")
                            current_attempt += 1
                            continue
                        else:
                            print("[모든 API 키 소진] 더 이상 사용 가능한 API 키가 없습니다.")
                            all_api_keys_exhausted = True
                            break
                    else:
                        # 할당량 외 다른 오류는 그대로 전파
                        print(f"[채널 검색 오류] {channel_id} → {str(e)}")
                        channel_processed = True
                        break

        # 최신순 기준 정렬 후 전체에서 max_results개 자르기
        all_filtered_videos.sort(
            key=lambda x: datetime.strptime(x['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"),
            reverse=True
        )
        # 모든 키 소진 상태에서 결과가 없다면 예외로 상위에 알림
        if all_api_keys_exhausted and len(all_filtered_videos) == 0:
            raise Exception("모든 YouTube API 키의 할당량이 초과되었습니다.")
        return all_filtered_videos

    else:
        # 키워드 기반 검색으로 fallback (여기도 API 키 소진 관리 필요)
        # 모든 API 키가 이미 소진된 경우 빈 결과 반환
        if all_api_keys_exhausted:
            print("모든 API 키가 소진되어 키워드 검색을 건너뜁니다.")
            raise Exception("모든 YouTube API 키의 할당량이 초과되었습니다.")
            
        return search_by_keyword_based_shorts(
            min_views=min_views, 
            days_ago=days_ago, 
            max_results=max_results,
            category_id=category_id, 
            region_code=region_code, 
            language=language,
            keyword=keyword
        )
    
# perform_search는 기존 그대로 유지합니다(내부에서 전환 로직이 포함되어 있음).
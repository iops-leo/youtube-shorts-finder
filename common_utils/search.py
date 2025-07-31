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

# 콤마로 구분된 API 키들을 리스트로 변환
api_keys = []
api_key_str = os.environ.get('YOUTUBE_API_KEY', '')

# 캐시 설정 (API 호출 결과를 메모리에 저장)
CACHE_TIMEOUT = 28800  # 캐시 유효시간 (초)
cache = {}

# 번역 캐시 설정
translation_cache = {}

if api_key_str:
    api_keys = [key.strip() for key in api_key_str.split(',') if key.strip()]
    print(f"{len(api_keys)}개의 API 키가 로드되었습니다.")
else:
    print("경고: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")

# 현재 사용 중인 API 키 인덱스
current_key_index = 0

def get_current_api_key():
    """현재 사용할 API 키 반환"""
    if not api_keys:
        return None
    return api_keys[current_key_index]

def switch_to_next_api_key():
    """다음 API 키로 전환"""
    global current_key_index
    if not api_keys:
        return None
        
    # 다음 키 인덱스로 전환 (순환)
    current_key_index = (current_key_index + 1) % len(api_keys)
    new_key = get_current_api_key()
    print(f"API 키 전환: 인덱스 {current_key_index}의 키로 변경됨")
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
        print(f"번역 캐시 히트: {text[:30]}...")
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
        
        print(f"번역 완료: {text[:30]}... -> {translated[:30]}...")
        return translated
    except Exception as e:
        print(f"번역 오류: {str(e)}")
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
    # 캐시 크기 제한 (선택적)
    if len(cache) > 100:
        oldest_key = min(cache.keys(), key=lambda k: cache[k][1])
        del cache[oldest_key]

def get_youtube_api_service():
    """YouTube API 서비스 인스턴스 생성 (키 오류 시 다음 키로 전환)"""
    api_key = get_current_api_key()
    if not api_key:
        raise Exception("사용 가능한 YouTube API 키가 없습니다.")
        
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
        return youtube
    except Exception as e:
        error_str = str(e).lower()
        if 'quota' in error_str or 'exceeded' in error_str:
            # 할당량 초과 시 다음 키로 전환
            next_api_key = switch_to_next_api_key()
            if next_api_key:
                print(f"할당량 초과로 다음 API 키로 전환합니다.")
                return googleapiclient.discovery.build("youtube", "v3", developerKey=next_api_key)
        # 다른 오류는 그대로 전파
        raise

def search_by_keyword_based_shorts(min_views, days_ago, max_results,
                                   category_id, region_code, language, keyword):
    """
    키워드 기반 영상 검색 - API 키 순환 로직 강화
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

        print(f"[키워드 검색] 조건: {search_params}")
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
                    search_response = youtube.search().list(**search_params).execute()
                    items = search_response.get('items', [])
                    video_ids = [item['id']['videoId'] for item in items]
                    all_video_ids.extend(video_ids)
                    
                    print(f"페이지 결과: {len(items)}개 항목 발견 (총 {len(all_video_ids)}개)")
                    next_page_token = search_response.get('nextPageToken')
                    page_processed = True
                    
                    if not next_page_token or len(items) == 0:
                        break  # 더 이상 페이지가 없거나 결과가 없으면 종료
                        
                except Exception as e:
                    error_str = str(e).lower()
                    if 'quota' in error_str or 'exceeded' in error_str:
                        next_key = switch_to_next_api_key()
                        if next_key:
                            print(f"[검색 중 할당량 초과] 다음 API 키({next_key[:8]}...)로 전환")
                            current_attempt += 1
                        else:
                            print("[모든 API 키 소진] 더 이상 사용 가능한 API 키가 없습니다.")
                            all_api_keys_exhausted = True
                            break
                    else:
                        # 할당량 외 다른 오류
                        print(f"[검색 오류] {str(e)}")
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
                    video_response = youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(batch_ids)
                    ).execute()

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
                            print(f"[상세 처리 오류] {str(ve)}")
                            continue
                            
                    batch_processed = True

                except Exception as e:
                    error_str = str(e).lower()
                    if 'quota' in error_str or 'exceeded' in error_str:
                        next_key = switch_to_next_api_key()
                        if next_key:
                            print(f"[상세 조회 중 할당량 초과] 다음 API 키({next_key[:8]}...)로 전환")
                            current_attempt += 1
                        else:
                            print("[모든 API 키 소진] 더 이상 사용 가능한 API 키가 없습니다.")
                            all_api_keys_exhausted = True
                            break
                    else:
                        # 할당량 외 다른 오류
                        print(f"[상세 조회 오류] {str(e)}")
                        batch_processed = True
                        break

        # 정렬 및 제한
        filtered_videos.sort(key=lambda x: x['viewCount'], reverse=True)
        return filtered_videos[:max_results]

    except Exception as e:
        print(f"[키워드 기반 검색 오류] {str(e)}")
        return []

def get_recent_popular_shorts(min_views=100000, days_ago=5, max_results=300,
                             category_id=None, region_code="KR", language=None,
                             channel_ids=None, keyword=None):
    """
    채널 ID 기반 최신 쇼츠 수집 방식 - API 키 순환 로직 강화
    """
    all_filtered_videos = []
    all_api_keys_exhausted = False  # 모든 API 키 소진 여부 플래그

    if isinstance(channel_ids, str):
        channel_id_list = [ch.strip() for ch in channel_ids.split(',') if ch.strip()]
    else:
        channel_id_list = channel_ids or []

    if channel_id_list:
        print(f"총 {len(channel_id_list)}개 채널에서 직접 영상 수집 중...")

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

                    # 각 채널당 최신 영상 검색
                    search_response = youtube.search().list(
                        part='snippet',
                        channelId=channel_id,
                        order='date',
                        type='video',
                        maxResults=min(10, max(1, max_results))  # 유튜브 API 제한: 최대 10
                    ).execute()

                    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

                    if not video_ids:
                        channel_processed = True  # 영상이 없으면 처리 완료로 표시
                        continue

                    # 비디오 상세 정보 조회
                    try:
                        video_response = youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=','.join(video_ids)
                        ).execute()
                        
                        for item in video_response.get('items', []):
                            try:
                                view_count = int(item['statistics'].get('viewCount', 0))
                                duration = item['contentDetails']['duration']
                                duration_seconds = isodate.parse_duration(duration).total_seconds()

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
                        if 'quota' in error_str or 'exceeded' in error_str:
                            next_key = switch_to_next_api_key()
                            if next_key:
                                print(f"[비디오 조회 중 할당량 초과] 채널 {channel_id} - 다음 API 키({next_key[:8]}...)로 전환")
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
                    if 'quota' in error_str or 'exceeded' in error_str:
                        next_key = switch_to_next_api_key()
                        if next_key:
                            print(f"[채널 검색 중 할당량 초과] 채널 {channel_id} - 다음 API 키({next_key[:8]}...)로 전환")
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

        # 조회수 순 기준 정렬 후 전체에서 max_results개 자르기 (알림용)
        all_filtered_videos.sort(key=lambda x: x.get('viewCount', 0), reverse=True)
        return all_filtered_videos

    else:
        # 키워드 기반 검색으로 fallback (여기도 API 키 소진 관리 필요)
        # 모든 API 키가 이미 소진된 경우 빈 결과 반환
        if all_api_keys_exhausted:
            print("모든 API 키가 소진되어 키워드 검색을 건너뜁니다.")
            return []
            
        return search_by_keyword_based_shorts(min_views, days_ago, max_results,
                                             category_id, region_code, language,
                                             keyword)
    
def perform_search(youtube, min_views, days_ago, max_results, 
                  category_id, region_code, language, 
                  keyword, channel_id):
    """단일 검색 수행 함수 - API 키 순환 지원 추가"""
    # 현재 시간 기준으로 n일 전 날짜 계산
    now = datetime.now(pytz.UTC)
    published_after = (now - timedelta(days=days_ago)).isoformat()

    # 검색 파라미터 설정
    search_params = {
        'part': 'snippet',
        'type': 'video',
        'maxResults': 50,  # API 한계로 한 번에 50개씩 요청 (페이지네이션으로 보완)
        'publishedAfter': published_after,
        'videoDuration': 'short',
        'regionCode': region_code,
        'order': 'viewCount'
    }

    # 키워드 처리
    if keyword and keyword.strip():
        print(f"키워드 검색 사용: '{keyword}'")
        search_params['q'] = keyword
        if language and language != "any":
            search_params['relevanceLanguage'] = language
    else:
        print("키워드 없음 - 일반 검색 수행")
    
    # 카테고리 ID가 있는 경우 추가
    if category_id and category_id != "any":
        search_params['videoCategoryId'] = category_id
    
    # 채널 ID가 있는 경우 추가
    if channel_id:
        search_params['channelId'] = channel_id

    # 디버깅을 위한 검색 조건 로그 추가
    print(f"실제 검색 조건: keyword={keyword}, min_views={min_views}, "
          f"days_ago={days_ago}, region_code={region_code}, max_results={max_results}")

    # 페이지네이션으로 모든 결과 수집
    all_video_ids = []
    next_page_token = None

    try:
        print("YouTube 검색 API 호출 시작 (페이지네이션 사용)...")
        while len(all_video_ids) < max_results:
            if next_page_token:
                search_params['pageToken'] = next_page_token
            
            # API 호출 시 할당량 초과 예외 처리 및 키 전환
            try:
                search_response = youtube.search().list(**search_params).execute()
            except Exception as e:
                error_str = str(e).lower()
                if 'quota' in error_str or 'exceeded' in error_str:
                    # 다음 키로 전환 시도
                    next_key = switch_to_next_api_key()
                    if next_key:
                        # 새 키로 YouTube API 서비스 재생성
                        youtube = get_youtube_api_service()
                        # 재시도
                        search_response = youtube.search().list(**search_params).execute()
                    else:
                        # 더 이상 사용 가능한 키가 없을 때
                        raise Exception("모든 API 키의 할당량이 초과되었습니다.")
                else:
                    # 할당량 외 다른 오류는 그대로 전파
                    raise
            
            items = search_response.get('items', [])
            print(f"페이지 결과: {len(items)}개 항목 발견 (총 {len(all_video_ids) + len(items)}개)")
            
            all_video_ids.extend([item['id']['videoId'] for item in items])
            
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token or len(items) == 0:
                break  # 더 이상 페이지가 없거나 결과가 없으면 종료

        # max_results 초과 시 자르기
        if len(all_video_ids) > max_results:
            all_video_ids = all_video_ids[:max_results]
            
    except Exception as e:
        print(f"YouTube API 검색 오류: {str(e)}")
        # 특별한 처리 없이 상위로 예외 전파 (get_recent_popular_shorts에서 처리)
        raise

    if not all_video_ids:
        print("검색 결과 없음 - 빈 리스트 반환")
        return []

    # 비디오 상세 정보 가져오기 (50개씩 배치 처리)
    filtered_videos = []
    for i in range(0, len(all_video_ids), 50):
        batch_ids = all_video_ids[i:i + 50]
        try:
            print(f"비디오 상세 정보 요청: {len(batch_ids)}개 ID (총 {len(all_video_ids)}개 중)")
            
            # API 호출 시 할당량 초과 예외 처리 및 키 전환
            try:
                video_response = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(batch_ids),
                    regionCode=region_code
                ).execute()
            except Exception as e:
                error_str = str(e).lower()
                if 'quota' in error_str or 'exceeded' in error_str:
                    # 다음 키로 전환 시도
                    next_key = switch_to_next_api_key()
                    if next_key:
                        # 새 키로 YouTube API 서비스 재생성
                        youtube = get_youtube_api_service()
                        # 재시도
                        video_response = youtube.videos().list(
                            part='snippet,statistics,contentDetails',
                            id=','.join(batch_ids),
                            regionCode=region_code
                        ).execute()
                    else:
                        # 더 이상 사용 가능한 키가 없을 때
                        raise Exception("모든 API 키의 할당량이 초과되었습니다.")
                else:
                    # 할당량 외 다른 오류는 그대로 전파
                    raise
            
            print(f"비디오 상세 정보 결과: {len(video_response.get('items', []))}개 항목")

            for item in video_response.get('items', []):
                try:
                    view_count = int(item['statistics'].get('viewCount', 0))
                    duration = item['contentDetails']['duration']
                    duration_seconds = isodate.parse_duration(duration).total_seconds()
                    thumbnail_url = ''
                    if 'high' in item['snippet']['thumbnails']:
                        thumbnail_url = item['snippet']['thumbnails']['high']['url']
                    elif 'medium' in item['snippet']['thumbnails']:
                        thumbnail_url = item['snippet']['thumbnails']['medium']['url']
                    elif 'default' in item['snippet']['thumbnails']:
                        thumbnail_url = item['snippet']['thumbnails']['default']['url']

                    # 최소 조회수 체크
                    if view_count >= min_views and duration_seconds <= 60:
                        print(f"비디오 발견: {item['snippet']['title']} - 조회수: {view_count}, 지역: {region_code}")
                        
                        # 원본 제목 저장
                        original_title = item['snippet']['title']
                        
                        # 제목 번역 (한국어가 아닌 경우에만)
                        translated_title = None
                        try:
                            # 언어 감지 및 번역 (한국어가 아닌 경우)
                            if not any('\uAC00' <= char <= '\uD7A3' for char in original_title):  # 한글 문자 범위 확인
                                translated_title = translate_text(original_title, 'ko')
                                # 번역 결과가 원본과 동일하거나 빈 문자열이면 무시
                                if translated_title == original_title or not translated_title:
                                    translated_title = None
                        except Exception as e:
                            print(f"제목 번역 중 오류: {str(e)}")
                        
                        filtered_videos.append({
                            'id': item['id'],
                            'title': original_title,
                            'translated_title': translated_title,  # 번역된 제목 추가
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
                except Exception as e:
                    print(f"비디오 처리 중 오류: {str(e)}")
                    continue

        except Exception as e:
            print(f"YouTube API 비디오 상세 정보 오류: {str(e)}")
            # 특별한 처리 없이 상위로 예외 전파 (get_recent_popular_shorts에서 처리)
            raise
    
    print(f"필터링 후 최종 결과: {len(filtered_videos)}개 항목")
    return filtered_videos
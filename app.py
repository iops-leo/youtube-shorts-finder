from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime, timedelta
import googleapiclient.discovery
import pytz
import isodate
import os
import json
from functools import lru_cache
import time
import hashlib
import re
import math

app = Flask(__name__)

# 정적 파일 경로 설정
app.static_folder = 'static'

# 콤마로 구분된 API 키들을 리스트로 변환
api_keys = []
api_key_str = os.environ.get('YOUTUBE_API_KEY', '')

# 캐시 설정 (API 호출 결과를 메모리에 저장)
CACHE_TIMEOUT = 600  # 캐시 유효시간 (초)
cache = {}

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

def get_recent_popular_shorts(min_views=100000, days_ago=5, max_results=300,
                             category_id=None, region_code="KR", language=None,
                             channel_ids=None, keyword=None):
    """
    인기 YouTube Shorts 검색 함수 - API 키 순환 지원 추가
    """
    # 캐시 키 생성
    cache_params = {
        'min_views': min_views,
        'days_ago': days_ago,
        'max_results': max_results,
        'category_id': category_id,
        'region_code': region_code,
        'language': language,
        'keyword': keyword,
        'channel_ids': channel_ids
    }
    cache_key = get_cache_key(cache_params)
    
    # 캐시에서 결과 확인
    cached_results = get_from_cache(cache_key)
    if cached_results:
        print(f"캐시에서 결과 가져옴: {len(cached_results)}개 항목")
        return cached_results
    
    print(f"API 검색 시작: 조회수 {min_views}+, {days_ago}일 이내, "
          f"카테고리: {category_id if category_id else '없음(any)'}, 키워드: {keyword if keyword else '없음'}, "
          f"지역: {region_code}, 언어: {language if language and language != 'any' else '모두'}, "
          f"채널IDs: {channel_ids if channel_ids else '모든 채널'}")

    # 최대 API 키 시도 횟수 (API 키의 수만큼)
    max_api_key_attempts = len(api_keys) if api_keys else 1
    attempt_count = 0
    
    # API 키 순환하며 검색 시도
    while attempt_count < max_api_key_attempts:
        try:
            # API 빌드 (할당량 초과 시 자동으로 다음 키로 전환)
            youtube = get_youtube_api_service()
            
            # 여러 채널 ID가 있는 경우 각 채널별로 검색하고 결과 합치기
            all_results = []
            
            # 키워드 처리
            enhanced_keyword = keyword.strip() if keyword and keyword.strip() else None
                
            # 키워드에 콤마가 있으면 공백으로 변환 (OR 검색)
            if enhanced_keyword and ',' in enhanced_keyword:
                enhanced_keyword = enhanced_keyword.replace(',', ' ')
            
            # 요청 결과 수 계산: 일반 검색 또는 채널별 검색
            if not channel_ids:
                # 일반 검색 - 최대 설정된 max_results 사용
                enhanced_max_results = max_results
                
                print(f"일반 검색: {enhanced_max_results}개 결과 요청")
                
                search_results = perform_search(youtube, min_views, days_ago, enhanced_max_results, 
                                               category_id, region_code, language, 
                                               enhanced_keyword, None)
                all_results.extend(search_results)
            else:
                # 채널 ID 처리
                if isinstance(channel_ids, str):
                    if ',' in channel_ids:
                        channel_id_list = [ch_id.strip() for ch_id in channel_ids.split(',')]
                    else:
                        channel_id_list = [channel_ids]
                else:
                    channel_id_list = channel_ids
                    
                # 채널 수에 따라 채널별 요청 결과 수 계산
                channel_count = len(channel_id_list)
                # 채널별 최대 100개까지 요청 (너무 많은 채널이 있으면 채널당 결과 수 줄임)
                results_per_channel = min(100, max(20, math.ceil(max_results / channel_count)))  
                
                print(f"채널별 검색: {channel_count}개 채널, 채널당 {results_per_channel}개 요청")
                    
                # 각 채널별로 검색 실행
                for channel_id in channel_id_list:
                    channel_results = perform_search(youtube, min_views, days_ago, results_per_channel, 
                                                   category_id, region_code, language,
                                                   enhanced_keyword, channel_id)
                    all_results.extend(channel_results)
            
            # 중복 제거 (비디오 ID 기준)
            seen_video_ids = set()
            unique_results = []
            for video in all_results:
                if video['id'] not in seen_video_ids:
                    seen_video_ids.add(video['id'])
                    unique_results.append(video)
           
            # 조회수 기준 내림차순 정렬
            unique_results.sort(key=lambda x: x['viewCount'], reverse=True)
            
            # 최대 결과 수 제한
            if len(unique_results) > max_results:
                unique_results = unique_results[:max_results]
            
            # 결과 캐싱
            save_to_cache(cache_key, unique_results)
            
            # 결과 통계 출력
            if unique_results:
                print(f"검색 결과: {len(unique_results)}개 비디오 찾음, 국가: {region_code}")
            else:
                print(f"검색 결과 없음! 국가: {region_code}, 키워드: {keyword}")
            
            return unique_results
            
        except Exception as e:
            error_str = str(e).lower()
            if 'quota' in error_str or 'exceeded' in error_str:
                print(f"API 할당량 초과 (시도 {attempt_count + 1}/{max_api_key_attempts})")
                
                # 다음 API 키로 전환
                next_key = switch_to_next_api_key()
                if next_key:
                    print(f"다음 API 키로 전환합니다.")
                    attempt_count += 1
                    continue
                else:
                    raise Exception("모든 API 키의 할당량이 초과되었습니다.")
            else:
                # 할당량 외 다른 오류는 바로 전파
                raise
    
    # 모든 시도 실패 시
    raise Exception("모든 API 키 시도 후에도 검색에 실패했습니다.")


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
                        filtered_videos.append({
                            'id': item['id'],
                            'title': item['snippet']['title'],
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

@app.route('/')
def index():
    # 카테고리, 국가, 언어 리스트
    categories = [
        {"id": "any", "name": "모든 카테고리"},
        {"id": "1", "name": "영화 & 애니메이션"},
        {"id": "2", "name": "자동차 & 차량"},
        {"id": "10", "name": "음악"},
        {"id": "15", "name": "애완동물 & 동물"},
        {"id": "17", "name": "스포츠"},
        {"id": "20", "name": "게임"},
        {"id": "22", "name": "인물 & 블로그"},
        {"id": "23", "name": "코미디"},
        {"id": "24", "name": "엔터테인먼트"},
        {"id": "25", "name": "뉴스 & 정치"},
        {"id": "26", "name": "노하우 & 스타일"},
        {"id": "27", "name": "교육"},
        {"id": "28", "name": "과학 & 기술"}
    ]
    regions = [
        {"code": "KR", "name": "대한민국"},
        {"code": "US", "name": "미국"},
        {"code": "JP", "name": "일본"},
        {"code": "GB", "name": "영국"},
        {"code": "FR", "name": "프랑스"},
        {"code": "DE", "name": "독일"},
        {"code": "CA", "name": "캐나다"},
        {"code": "AU", "name": "호주"},
        {"code": "CN", "name": "중국"}
    ]
    languages = [
        {"code": "any", "name": "모든 언어"},
        {"code": "ko", "name": "한국어"},
        {"code": "en", "name": "영어"},
        {"code": "ja", "name": "일본어"},
        {"code": "zh", "name": "중국어"},
        {"code": "es", "name": "스페인어"},
        {"code": "fr", "name": "프랑스어"},
        {"code": "de", "name": "독일어"}
    ]

    # 기본값 설정
    selected_region = request.args.get('region', 'KR')
    selected_language = request.args.get('language', 'ko')

    return render_template('index.html', categories=categories, regions=regions, languages=languages,
                           selected_region=selected_region, selected_language=selected_language)


@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.form
        print("검색 요청 파라미터:", data)

        # 필수 파라미터 설정
        min_views = int(data.get('min_views', '100000'))
        days_ago = int(data.get('days_ago', 5))
        max_results = int(data.get('max_results', 300))
        
        # 최대 500개 제한
        if max_results > 500:
            max_results = 500
        
        category_id = data.get('category_id', 'any')
        region_code = data.get('region_code', 'KR')
        language = data.get('language', 'any')
        keyword = data.get('keyword', '')
        
        # 채널 ID 처리
        channel_ids = data.get('channel_ids', '')

        # API 키 확인
        if not api_keys:
            print("경고: API 키가 설정되지 않았습니다.")
            return jsonify({"status": "error", "message": "YouTube API 키가 설정되지 않았습니다."})

        try:
            results = get_recent_popular_shorts(
                min_views=min_views,
                days_ago=days_ago,
                max_results=max_results,
                category_id=category_id if category_id != 'any' else None,
                region_code=region_code,
                language=language if language != 'any' else None,
                channel_ids=channel_ids if channel_ids else None,
                keyword=keyword
            )

            print(f"API 검색 결과: {len(results)}개 항목 찾음")
            return jsonify({
                "status": "success", 
                "results": results,
                "count": len(results),
                "displayCount": len(results)
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"검색 중 오류 발생: {error_msg}")
            
            # 쿼터 초과 오류 확인
            if 'quota' in error_msg.lower() or 'exceeded' in error_msg.lower():
                return jsonify({
                    "status": "quota_exceeded", 
                    "message": "모든 YouTube API 키의 일일 할당량이 초과되었습니다. 내일 다시 시도해주세요.",
                    "details": error_msg
                })
            else:
                return jsonify({"status": "error", "message": error_msg})

    except Exception as e:
        print(f"검색 중 오류 발생: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})
    

@app.route('/channel-search', methods=['GET'])
def channel_search():
    """채널 검색 API 엔드포인트 - 다중 API 키 지원"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "검색어가 필요합니다."})
            
        if not api_keys:
            return jsonify({"status": "error", "message": "YouTube API 키가 설정되지 않았습니다."})
        
        # 최대 API 키 시도 횟수
        max_api_key_attempts = len(api_keys) if api_keys else 1
        attempt_count = 0
        
        while attempt_count < max_api_key_attempts:
            try:
                # YouTube API 서비스 가져오기 (자동 키 순환)
                youtube = get_youtube_api_service()
                
                # URL이나 핸들(@) 형식인지 확인
                if '@' in query or 'youtube.com/' in query:
                    # URL에서 채널 ID 또는 핸들 추출
                    if 'youtube.com/' in query:
                        parts = query.split('/')
                        for part in parts:
                            if part.startswith('@'):
                                query = part
                                break
                    
                    # @ 기호가 있으면 그대로 사용하고, 없으면 추가
                    if not query.startswith('@') and '@' not in query:
                        query = '@' + query
                    
                    # 핸들 검색 (채널 이름으로 검색 + 필터링)
                    response = youtube.search().list(
                        part="snippet",
                        type="channel",
                        q=query.replace('@', ''),  # @ 기호 제거하고 검색
                        maxResults=10  # 더 많은 결과를 가져와서 필터링
                    ).execute()
                    
                    # 결과에서 정확히 일치하거나 유사한 핸들을 가진 채널 필터링
                    filtered_channels = []
                    channel_handle = query.lower().replace('@', '')
                    
                    for item in response.get('items', []):
                        channel_title = item['snippet']['title'].lower()
                        channel_desc = item['snippet']['description'].lower()
                        
                        if (channel_handle in channel_title.replace(' ', '') or 
                            channel_handle in channel_desc):
                            filtered_channels.append({
                                'id': item['id']['channelId'],
                                'title': item['snippet']['title'],
                                'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                                'description': item['snippet']['description']
                            })
                    
                    if filtered_channels:
                        return jsonify({"status": "success", "channels": filtered_channels})
                
                # 일반 검색으로 진행
                response = youtube.search().list(
                    part="snippet",
                    type="channel",
                    q=query,
                    maxResults=5
                ).execute()
                
                channels = [{
                    'id': item['id']['channelId'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['default']['url'] if 'default' in item['snippet']['thumbnails'] else '',
                    'description': item['snippet']['description']
                } for item in response.get('items', [])]
                
                return jsonify({"status": "success", "channels": channels})
                
            except Exception as e:
                error_str = str(e).lower()
                if 'quota' in error_str or 'exceeded' in error_str:
                    # 다음 API 키로 전환
                    next_key = switch_to_next_api_key()
                    if next_key:
                        print(f"채널 검색: 할당량 초과로 다음 API 키로 전환합니다.")
                        attempt_count += 1
                        continue
                    else:
                        return jsonify({
                            "status": "quota_exceeded", 
                            "message": "모든 YouTube API 키의 할당량이 초과되었습니다."
                        })
                else:
                    return jsonify({"status": "error", "message": str(e)})
        
        # 모든 시도 실패 시
        return jsonify({"status": "error", "message": "모든 API 키 시도 후에도 검색에 실패했습니다."})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# 정적 파일 제공 라우트
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    if not api_keys:
        print("경고: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("다음 명령으로 설정하세요: export YOUTUBE_API_KEY='YOUR_API_KEY_1,YOUR_API_KEY_2,YOUR_API_KEY_3'")
    else:
        print(f"{len(api_keys)}개의 YouTube API 키가 로드되었습니다.")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

@app.route('/favicon.ico')
def favicon():
    """Favicon 반환 라우트"""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
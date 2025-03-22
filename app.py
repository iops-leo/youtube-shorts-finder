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

app = Flask(__name__)

# 정적 파일 경로 설정
app.static_folder = 'static'

# 환경 변수에서 API 키 가져오기
API_KEY = os.environ.get('YOUTUBE_API_KEY')

# 캐시 설정 (API 호출 결과를 메모리에 저장)
CACHE_TIMEOUT = 600  # 캐시 유효시간 (초)
cache = {}

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


def get_recent_popular_shorts(api_key, min_views=10000, max_views=None, days_ago=5, max_results=50,
                             category_id=None, region_code="KR", language=None,
                             duration_max=60, keyword=None, title_contains=None, channel_ids=None):
    """
    인기 YouTube Shorts 검색 함수
    channel_ids 파라미터 수정: 여러 채널의 쇼츠 검색 가능
    """
    # 캐시 키 생성
    cache_params = {
        'min_views': min_views,
        'max_views': max_views,
        'days_ago': days_ago,
        'max_results': max_results,
        'category_id': category_id,
        'region_code': region_code,
        'language': language,
        'duration_max': duration_max,
        'keyword': keyword,
        'title_contains': title_contains,
        'channel_ids': channel_ids
    }
    cache_key = get_cache_key(cache_params)
    
    # 캐시에서 결과 확인
    cached_results = get_from_cache(cache_key)
    if cached_results:
        print(f"캐시에서 결과 가져옴: {len(cached_results)}개 항목")
        return cached_results
    
    print(f"API 검색 시작: 조회수 {min_views}~{max_views if max_views else '무제한'}, {days_ago}일 이내, "
          f"카테고리: {category_id if category_id else '없음(any)'}, 키워드: {keyword if keyword else '없음'}, "
          f"지역: {region_code}, 언어: {language if language and language != 'any' else '모두'}, "
          f"채널IDs: {channel_ids if channel_ids else '모든 채널'}")

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    # 여러 채널 ID가 있는 경우 각 채널별로 검색하고 결과 합치기
    all_results = []
    
    # 채널 ID가 없거나 단일 채널인 경우를 처리
    if not channel_ids:
        search_results = perform_search(youtube, min_views, max_views, days_ago, max_results, 
                                       category_id, region_code, language, duration_max, 
                                       keyword, title_contains, None)
        all_results.extend(search_results)
    else:
        # 문자열로 전달된 경우 리스트로 변환
        if isinstance(channel_ids, str):
            if ',' in channel_ids:
                channel_id_list = [ch_id.strip() for ch_id in channel_ids.split(',')]
            else:
                channel_id_list = [channel_ids]
        else:
            channel_id_list = channel_ids
            
        # 각 채널별로 검색 실행
        for channel_id in channel_id_list:
            channel_results = perform_search(youtube, min_views, max_views, days_ago, 
                                            max_results // len(channel_id_list) + 1, 
                                            category_id, region_code, language, duration_max, 
                                            keyword, title_contains, channel_id)
            all_results.extend(channel_results)
    
    # 중복 제거 (비디오 ID 기준)
    seen_video_ids = set()
    unique_results = []
    for video in all_results:
        if video['id'] not in seen_video_ids:
            seen_video_ids.add(video['id'])
            unique_results.append(video)
    
    # 언어 필터 추가 강화
    if language and language != "any":
        filtered_results = []
        for video in unique_results:
            if check_video_language(video, language):
                filtered_results.append(video)
        unique_results = filtered_results
    
    # 조회수 기준 내림차순 정렬
    unique_results.sort(key=lambda x: x['viewCount'], reverse=True)
    
    # 최대 결과 수 제한
    if len(unique_results) > max_results:
        unique_results = unique_results[:max_results]
    
    # 결과 캐싱
    save_to_cache(cache_key, unique_results)
    
    return unique_results

def perform_search(youtube, min_views, max_views, days_ago, max_results, 
                 category_id, region_code, language, duration_max, 
                 keyword, title_contains, channel_id):
    """단일 검색 수행 함수"""
    # 현재 시간 기준으로 n일 전 날짜 계산
    now = datetime.now(pytz.UTC)
    published_after = (now - timedelta(days=days_ago)).isoformat()

    # 검색 파라미터 설정
    search_params = {
        'part': 'snippet',
        'type': 'video',
        'maxResults': max_results,
        'publishedAfter': published_after,
        'videoDuration': 'short',
        'regionCode': region_code,
        'order': 'viewCount'
    }

    # 키워드 처리 - 콤마로 구분된 키워드 지원
    all_results = []
    
    if keyword:
        # 콤마로 구분된 키워드를 분리
        keywords = [k.strip() for k in keyword.split(',') if k.strip()]
        
        # 각 키워드별로 검색 수행
        for single_keyword in keywords:
            keyword_params = search_params.copy()
            keyword_params['q'] = single_keyword
            
            if language and language != "any":
                keyword_params['relevanceLanguage'] = language
            
            # 카테고리 ID가 있는 경우 추가
            if category_id and category_id != "any":
                keyword_params['videoCategoryId'] = category_id
            
            # 채널 ID가 있는 경우 추가
            if channel_id:
                keyword_params['channelId'] = channel_id
                
            # 검색 실행
            try:
                search_response = youtube.search().list(**keyword_params).execute()
                
                video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                if video_ids:
                    # 비디오 상세 정보 가져오기
                    video_response = youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(video_ids)
                    ).execute()
                    
                    # 결과 필터링 및 처리
                    keyword_results = process_video_results(video_response, min_views, max_views, duration_max, title_contains)
                    all_results.extend(keyword_results)
            except Exception as e:
                print(f"YouTube API 키워드 검색 오류 ({single_keyword}): {str(e)}")
    else:
        # 키워드 없는 기본 검색
        # 카테고리 ID가 있는 경우 추가
        if category_id and category_id != "any":
            search_params['videoCategoryId'] = category_id
        
        # 채널 ID가 있는 경우 추가
        if channel_id:
            search_params['channelId'] = channel_id
            
        # 검색 실행
        try:
            search_response = youtube.search().list(**search_params).execute()
            
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            if video_ids:
                # 비디오 상세 정보 가져오기
                video_response = youtube.videos().list(
                    part='snippet,statistics,contentDetails',
                    id=','.join(video_ids)
                ).execute()
                
                # 결과 필터링 및 처리
                all_results = process_video_results(video_response, min_views, max_views, duration_max, title_contains)
        except Exception as e:
            print(f"YouTube API 기본 검색 오류: {str(e)}")
    
    return all_results

def process_video_results(video_response, min_views, max_views, duration_max, title_contains):
    """비디오 응답 데이터 처리 함수"""
    filtered_videos = []
    
    for item in video_response.get('items', []):
        # 조회수 추출
        view_count = int(item['statistics'].get('viewCount', 0))
        
        # 동영상 길이 추출
        duration = item['contentDetails']['duration']
        duration_seconds = isodate.parse_duration(duration).total_seconds()

        # 썸네일 확인 (세로형 확인용)
        # if 'high' in item['snippet']['thumbnails']:
        #     thumbnail = item['snippet']['thumbnails']['high']
        #     is_vertical = thumbnail['height'] > thumbnail['width']
        # elif 'medium' in item['snippet']['thumbnails']:
        #     thumbnail = item['snippet']['thumbnails']['medium']
        #     is_vertical = thumbnail['height'] > thumbnail['width']
        # else:
        is_vertical = True

        # 비디오가 조건을 충족하는지 확인
        if (view_count >= min_views and
            (max_views is None or view_count <= max_views) and
            duration_seconds <= duration_max):

            # 제목 필터 적용
            if title_contains:
                if title_contains.lower() not in item['snippet']['title'].lower():
                    continue

            filtered_videos.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'channelTitle': item['snippet']['channelTitle'],
                'channelId': item['snippet']['channelId'],
                'publishedAt': item['snippet']['publishedAt'],
                'viewCount': view_count,
                'likeCount': int(item['statistics'].get('likeCount', 0)),
                'commentCount': int(item['statistics'].get('commentCount', 0)),
                'duration': round(duration_seconds),
                'url': f"https://www.youtube.com/shorts/{item['id']}",
                'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else '',
                'isVertical': is_vertical
            })
            
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
    selected_region = request.args.get('region', 'US')
    selected_language = request.args.get('language', 'en')

    return render_template('index.html', categories=categories, regions=regions, languages=languages,
                           selected_region=selected_region, selected_language=selected_language)

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.form
        print("검색 요청 파라미터:", data)

        min_views = int(data.get('min_views', 10000))
        max_views = data.get('max_views', '')
        max_views = int(max_views) if max_views.strip() else None
        
        days_ago = int(data.get('days_ago', 5))
        max_results = int(data.get('max_results', 50))
        category_id = data.get('category_id', 'any')
        region_code = data.get('region_code', 'KR')
        language = data.get('language', 'any')
        duration_max = int(data.get('duration_max', 60))
        keyword = data.get('keyword', '')
        title_contains = data.get('title_contains', '')
        
        # 여러 채널 ID 처리
        channel_ids = data.get('channel_ids', '')

        if not API_KEY:
            print("경고: API 키가 설정되지 않았습니다.")
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})

        results = get_recent_popular_shorts(
            api_key=API_KEY,
            min_views=min_views,
            max_views=max_views,
            days_ago=days_ago,
            max_results=max_results,
            category_id=category_id if category_id != 'any' else None,
            region_code=region_code,
            language=language if language != 'any' else None,
            duration_max=duration_max,
            keyword=keyword,
            title_contains=title_contains,
            channel_ids=channel_ids if channel_ids else None
        )

        print(f"검색 결과: {len(results)}개 항목 찾음")
        return jsonify({"status": "success", "results": results, "count": len(results)})

    except Exception as e:
        print(f"검색 중 오류 발생: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/channel-search', methods=['GET'])
def channel_search():
    """채널 검색 API 엔드포인트"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({"status": "error", "message": "검색어가 필요합니다."})
            
        if not API_KEY:
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})
        
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
            youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
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
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
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
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api-test', methods=['GET'])
def api_test():
    try:
        if not API_KEY:
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})

        # 간단한 API 호출로 키 테스트
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
        response = youtube.channels().list(part="snippet", forUsername="YouTube", maxResults=1).execute()

        return jsonify({"status": "success", "message": "API 키가 정상적으로 작동합니다.", "response": "API 연결 성공"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"API 키 오류: {str(e)}"})

# 정적 파일 제공 라우트
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    if not API_KEY:
        print("경고: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("다음 명령으로 설정하세요: export YOUTUBE_API_KEY='YOUR_API_KEY'")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


def check_video_language(video_data, target_language):
    """
    비디오가 특정 언어인지 확인하는 함수
    video_data: API에서 반환된 비디오 정보
    target_language: 확인할 언어 코드 ('ko', 'en', 'ja', 등)
    """
    # 임시로 모든 비디오가 통과하도록 설정
    return True

    # 언어별 문자 패턴 정의
    language_patterns = {
        'ko': r'[가-힣]',          # 한국어
        'en': r'[a-zA-Z]',         # 영어
        'ja': r'[\u3040-\u309F\u30A0-\u30FF]',  # 일본어 (히라가나, 가타카나)
        'zh': r'[\u4e00-\u9FFF]',  # 중국어
    }
    
    # 제목과 채널명 가져오기
    title = video_data.get('title', '')
    channel_title = video_data.get('channelTitle', '')
    
    # 대상 언어의 패턴이 정의되어 있는지 확인
    if target_language not in language_patterns:
        return True  # 패턴이 없으면 기본적으로 통과
    
    pattern = language_patterns[target_language]
    
    # 제목에서 해당 언어 문자 비율 계산
    if title:
        title_matches = len(re.findall(pattern, title))
        title_ratio = title_matches / len(title) if len(title) > 0 else 0
        
        # 영어의 경우 더 관대한 기준 적용 (영어는 많은 언어에서 차용됨)
        if target_language == 'en':
            if title_ratio > 0.4:  # 40% 이상이 영어 문자면 영어로 간주
                return True
        else:
            # 비영어 언어는 더 엄격한 기준 적용
            if title_ratio > 0.15:  # 15% 이상이 해당 언어 문자면 해당 언어로 간주
                return True
    
    # 채널명에서 해당 언어 문자 비율 계산
    if channel_title:
        channel_matches = len(re.findall(pattern, channel_title))
        channel_ratio = channel_matches / len(channel_title) if len(channel_title) > 0 else 0
        
        if target_language == 'en':
            if channel_ratio > 0.5:  # 50% 이상이 영어 문자면 영어로 간주
                return True
        else:
            if channel_ratio > 0.3:  # 30% 이상이 해당 언어 문자면 해당 언어로 간주
                return True
    
    # 기본적으로 통과시키지 않음
    return False
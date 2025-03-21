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
                             duration_max=60, keyword=None, title_contains=None, channel_id=None):
    """
    인기 YouTube Shorts 검색 함수
    channel_id 파라미터 추가: 특정 채널의 쇼츠만 검색
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
        'channel_id': channel_id
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
          f"채널ID: {channel_id if channel_id else '모든 채널'}")

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

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

    # 키워드가 있는 경우 추가
    if keyword:
        search_params['q'] = keyword
        if language and language != "any":
            search_params['relevanceLanguage'] = language
    
    # 카테고리 ID가 있는 경우 추가
    if category_id and category_id != "any":
        search_params['videoCategoryId'] = category_id
    
    # 채널 ID가 있는 경우 추가
    if channel_id:
        search_params['channelId'] = channel_id

    # 검색 실행
    try:
        search_response = youtube.search().list(**search_params).execute()
        print(f"YouTube 검색 응답: {len(search_response.get('items', []))}개 비디오 ID 찾음")
    except Exception as e:
        print(f"YouTube API 검색 오류: {str(e)}")
        return []

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    if not video_ids:
        return []

    # 비디오 상세 정보 가져오기
    video_response = youtube.videos().list(
        part='snippet,statistics,contentDetails',
        id=','.join(video_ids)
    ).execute()

    filtered_videos = []
    for item in video_response.get('items', []):
        # 조회수 추출
        view_count = int(item['statistics'].get('viewCount', 0))
        
        # 동영상 길이 추출
        duration = item['contentDetails']['duration']
        duration_seconds = isodate.parse_duration(duration).total_seconds()

        # 썸네일 확인 (세로형 확인용)
        if 'high' in item['snippet']['thumbnails']:
            thumbnail = item['snippet']['thumbnails']['high']
            is_vertical = thumbnail['height'] > thumbnail['width']
        elif 'medium' in item['snippet']['thumbnails']:
            thumbnail = item['snippet']['thumbnails']['medium']
            is_vertical = thumbnail['height'] > thumbnail['width']
        else:
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
                'channelId': item['snippet']['channelId'],  # 채널 ID 추가
                'publishedAt': item['snippet']['publishedAt'],
                'viewCount': view_count,
                'likeCount': int(item['statistics'].get('likeCount', 0)),
                'commentCount': int(item['statistics'].get('commentCount', 0)),
                'duration': round(duration_seconds),
                'url': f"https://www.youtube.com/shorts/{item['id']}",
                'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else '',
                'isVertical': is_vertical
            })

    # 조회수 기준 내림차순 정렬
    filtered_videos.sort(key=lambda x: x['viewCount'], reverse=True)
    
    # 결과 캐싱
    save_to_cache(cache_key, filtered_videos)
    
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
        channel_id = data.get('channel_id', '')  # 채널 ID 파라미터 추가

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
            channel_id=channel_id if channel_id else None
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
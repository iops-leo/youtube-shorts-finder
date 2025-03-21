from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import googleapiclient.discovery
import pytz
import isodate
import os
import logging

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 환경 변수에서 API 키 가져오기
API_KEY = os.environ.get('YOUTUBE_API_KEY')

# 카테고리, 국가, 언어 (이제 Python에서만 정의)
CATEGORIES = [
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
REGIONS = [
    {"code": "US", "name": "미국"},
    {"code": "KR", "name": "대한민국"},
    {"code": "JP", "name": "일본"},
    {"code": "GB", "name": "영국"},
    {"code": "FR", "name": "프랑스"},
    {"code": "DE", "name": "독일"},
    {"code": "CA", "name": "캐나다"},
    {"code": "AU", "name": "호주"},
    {"code": "CN", "name": "중국"}
]
LANGUAGES = [
    {"code": "any", "name": "모든 언어"},
    {"code": "en", "name": "영어"},
    {"code": "ko", "name": "한국어"},
    {"code": "ja", "name": "일본어"},
    {"code": "zh", "name": "중국어"},
    {"code": "es", "name": "스페인어"},
    {"code": "fr", "name": "프랑스어"},
    {"code": "de", "name": "독일어"}
]



def get_recent_popular_shorts(api_key, min_views=1000000, days_ago=3, max_results=50,
                             category_id=None, region_code="US", language=None,
                             duration_max=60, keyword=None, title_contains=None, channel_ids=None):
    """
    최근 인기 YouTube Shorts를 검색합니다.

    Args:
        api_key: YouTube Data API v3 키.
        min_views: 최소 조회수.
        days_ago: 최근 몇 일 이내의 비디오를 검색할지.
        max_results: 최대 결과 수.
        category_id: 비디오 카테고리 ID.
        region_code: 지역 코드.
        language: 언어 코드.
        duration_max: 최대 비디오 길이 (초).
        keyword: 검색 키워드.
        title_contains: 제목에 포함되어야 하는 문자열.
        channel_ids: 채널 ID 목록 (쉼표로 구분).

    Returns:
        조건에 맞는 비디오 목록 (딕셔너리 리스트).  오류 발생 시 빈 목록 반환.
    """

    logging.info(f"API 검색 시작: 조회수 {min_views} 이상, {days_ago}일 이내, 카테고리: {category_id if category_id else '없음(any)'}, 키워드: {keyword if keyword else '없음'}, 지역: {region_code}, 언어: {language if language and language != 'any' else '모두'}, 채널 ID: {channel_ids}")

    if not api_key:
        logging.error("API 키가 설정되지 않았습니다.")
        return []

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    now = datetime.now(pytz.UTC)
    published_after = (now - timedelta(days=days_ago)).isoformat()

    search_params = {
        'part': 'id,snippet',  # id와 snippet만 가져오도록 변경
        'type': 'video',
        'maxResults': max_results,
        'publishedAfter': published_after,
        'videoDuration': 'short',
        'regionCode': region_code,
        'order': 'viewCount'
    }

    if keyword:
        search_params['q'] = keyword
        if language and language != "any":
            search_params['relevanceLanguage'] = language
    elif channel_ids:
        # 키워드가 없을 때만 channelId를 사용.  q와 함께 사용하면 예상과 다르게 동작할 수 있음.
        search_params['channelId'] = channel_ids

    if category_id and category_id != "any":
        search_params['videoCategoryId'] = category_id

    try:
        search_response = youtube.search().list(**search_params).execute()
        logging.info(f"YouTube 검색 응답: {len(search_response.get('items', []))}개 비디오 ID 찾음")
    except Exception as e:
        logging.error(f"YouTube API 검색 오류: {str(e)}")
        return []

    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    if not video_ids:
        return []

    # 필요한 경우에만 videos().list() 호출.  채널 ID 필터링은 이미 search().list()에서 했으므로
    # 여기서는 조회수, 길이, 제목 필터링만 처리하면 됨.
    filtered_videos = []
    # 나눠서 API 호출하도록 변경
    chunk_size = 50  # YouTube API의 최대 허용 개수
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i:i + chunk_size]
        try:
            video_response = youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(chunk)
            ).execute()
        except Exception as e:
            logging.error(f"YouTube API 비디오 정보 가져오기 오류: {str(e)}")
            continue  # 다음 청크로 넘어감

        for item in video_response.get('items', []):
            # 조회수 및 길이 필터링
            view_count = int(item['statistics'].get('viewCount', 0))
            duration_seconds = isodate.parse_duration(item['contentDetails']['duration']).total_seconds()

            if view_count < min_views or duration_seconds > duration_max:
                continue

            # 제목 필터링 (필요한 경우)
            if title_contains and title_contains.lower() not in item['snippet']['title'].lower():
                continue

            # 채널 ID가 이미 search 단계에서 필터링 되었으므로 여기서는 확인할 필요 없음.

            filtered_videos.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'channelTitle': item['snippet']['channelTitle'],
                'channelId': item['snippet']['channelId'], # 채널 ID 추가
                'publishedAt': item['snippet']['publishedAt'],
                'viewCount': view_count,
                'likeCount': int(item['statistics'].get('likeCount', 0)),
                'commentCount': int(item['statistics'].get('commentCount', 0)),
                'duration': round(duration_seconds),
                'url': f"https://www.youtube.com/shorts/{item['id']}",
                'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else ''
            })

    filtered_videos.sort(key=lambda x: x['viewCount'], reverse=True)
    return filtered_videos


@app.route('/')
def index():
    selected_region = 'US'
    selected_language = 'any'
    return render_template('index.html', categories=CATEGORIES, regions=REGIONS, languages=LANGUAGES,
                           selected_region=selected_region, selected_language=selected_language)


@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.form
        logging.info("검색 요청 파라미터: %s", data)

        # 입력 값 유효성 검사 (간단한 예시)
        try:
            min_views = int(data.get('min_views', 1000000))
            days_ago = int(data.get('days_ago', 3))
            max_results = int(data.get('max_results', 50))
            duration_max = int(data.get('duration_max', 60))
            if not (1000 <= min_views <= 1000000000 and 1 <= days_ago <= 30 and 10 <= max_results <= 50 and 15<= duration_max <= 180):
                raise ValueError("잘못된 입력 값 범위")
        except ValueError as e:
            return jsonify({"status": "error", "message": f"입력 값 오류: {str(e)}"})
        
        category_id = data.get('category_id', 'any')
        region_code = data.get('region_code', 'US')
        language = data.get('language', 'any')
        keyword = data.get('keyword', '')
        title_contains = data.get('title_contains', '')
        channel_filter = data.get('channel_filter', '')

        # 채널 ID 목록으로 변환
        channel_ids = None
        if channel_filter:
            channel_ids = ','.join([c.strip() for c in channel_filter.split(',')])


        if not API_KEY:
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})

        results = get_recent_popular_shorts(
            api_key=API_KEY,
            min_views=min_views,
            days_ago=days_ago,
            max_results=max_results,
            category_id=category_id,
            region_code=region_code,
            language=language,
            duration_max=duration_max,
            keyword=keyword,
            title_contains=title_contains,
            channel_ids=channel_ids  # 채널 ID 목록 전달
        )
        logging.info(f"검색 결과: {len(results)}개 항목 찾음")
        return jsonify({"status": "success", "results": results, "count": len(results)})

    except Exception as e:
        logging.exception(f"검색 중 오류 발생: {str(e)}")  # 더 자세한 로깅
        return jsonify({"status": "error", "message": f"서버 오류: {str(e)}"})


@app.route('/api-test', methods=['GET'])
def api_test():
    try:
        if not API_KEY:
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})

        # 간단한 API 호출로 키 테스트
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)
        response = youtube.channels().list(part="snippet", mine=False, maxResults=1).execute()

        return jsonify({"status": "success", "message": "API 키가 정상적으로 작동합니다.", "response": "API 연결 성공"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"API 키 오류: {str(e)}"})
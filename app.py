from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import googleapiclient.discovery
import pytz
import isodate
import os

app = Flask(__name__)

# 환경 변수에서 API 키 가져오기 (보안을 위해)
API_KEY = os.environ.get('YOUTUBE_API_KEY')

def get_recent_popular_shorts(api_key, min_views=10000, days_ago=5, max_results=50,
                             category_id=None, region_code="KR", language=None,
                             duration_max=60, keyword=None):
    print(f"API 검색 시작: 조회수 {min_views}+, {days_ago}일 이내, 카테고리: {category_id if category_id else '없음(any)'}, 키워드: {keyword if keyword else '없음'}, 언어: {language if language and language != 'any' else '모두'}")

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

    # 현재 시간 기준으로 n일 전 날짜 계산
    now = datetime.now(pytz.UTC)
    published_after = (now - timedelta(days=days_ago)).isoformat()

    # 검색 파라미터 설정. keyword가 있으면 q 파라미터 사용, 없으면 생략
    search_params = {
        'part': 'snippet',
        'type': 'video',
        'maxResults': max_results,
        'publishedAfter': published_after,
        'videoDuration': 'short',
        'regionCode': region_code,
        'order': 'viewCount'
    }
    if keyword:
        search_params['q'] = keyword
        # Keyword가 있을 때만 relevanceLanguage 설정
        if language and language != "any":
            search_params['relevanceLanguage'] = language
    else:  # Keyword가 없을 때는 relevanceLanguage 설정 안 함
        if language and language != "any":
             print("경고: 키워드 없이 언어 필터가 적용되었습니다. 결과가 제한될 수 있습니다.")
    # 선택적 파라미터 추가
    if category_id and category_id != "any":
        search_params['videoCategoryId'] = category_id

    # 검색 실행
    try:
        search_response = youtube.search().list(**search_params).execute()
        print(f"YouTube 검색 응답: {len(search_response.get('items', []))}개 비디오 ID 찾음")
    except Exception as e:
        print(f"YouTube API 검색 오류: {str(e)}")
        return []

    # 검색된 비디오 ID 목록 추출 (검색 결과가 없는 경우 빈 리스트 반환)
    video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
    if not video_ids:
        return []


    # 비디오 상세 정보 가져오기
    video_response = youtube.videos().list(
        part='snippet,statistics,contentDetails',
        id=','.join(video_ids)
    ).execute()

    # 조건에 맞는 비디오 필터링
    filtered_videos = []
    for item in video_response.get('items', []):
        # 조회수 확인
        view_count = int(item['statistics'].get('viewCount', 0))

        # 비디오 길이 확인
        duration = item['contentDetails']['duration']
        duration_seconds = isodate.parse_duration(duration).total_seconds()

        # 수직 비율 확인 (Shorts는 일반적으로 9:16 비율)
        # high 썸네일이 있으면 그걸 사용, 없으면 medium 썸네일 확인. 둘 다 없으면 수직으로 간주.
        if 'high' in item['snippet']['thumbnails']:
            thumbnail = item['snippet']['thumbnails']['high']
            is_vertical = thumbnail['height'] > thumbnail['width']
        elif 'medium' in item['snippet']['thumbnails']:
            thumbnail = item['snippet']['thumbnails']['medium']
            is_vertical = thumbnail['height'] > thumbnail['width']
        else:
            is_vertical = True  # 썸네일 정보가 없으면 기본적으로 수직으로 가정


        # 비디오가 조건을 충족하는지 확인
        if (view_count >= min_views and
            duration_seconds <= duration_max and
            is_vertical):

            filtered_videos.append({
                'id': item['id'],
                'title': item['snippet']['title'],
                'channelTitle': item['snippet']['channelTitle'],
                'publishedAt': item['snippet']['publishedAt'],
                'viewCount': view_count,
                'likeCount': int(item['statistics'].get('likeCount', 0)),
                'commentCount': int(item['statistics'].get('commentCount', 0)),
                'duration': round(duration_seconds),
                'url': f"https://www.youtube.com/shorts/{item['id']}",
                'thumbnail': item['snippet']['thumbnails']['high']['url'] if 'high' in item['snippet']['thumbnails'] else ''
            })

    # 조회수 기준으로 정렬
    filtered_videos.sort(key=lambda x: x['viewCount'], reverse=True)

    return filtered_videos

@app.route('/')
def index():
    # 카테고리 리스트
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

    # 국가 코드 리스트
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

    # 언어 코드 리스트
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

    return render_template('index.html', categories=categories, regions=regions, languages=languages)

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.form

        print("검색 요청 파라미터:", data)

        min_views = int(data.get('min_views', 10000))
        days_ago = int(data.get('days_ago', 5))
        max_results = int(data.get('max_results', 50))
        category_id = data.get('category_id', 'any')
        region_code = data.get('region_code', 'KR')
        language = data.get('language', 'any')
        duration_max = int(data.get('duration_max', 60))
        keyword = data.get('keyword', '')

        if not API_KEY:
            print("경고: API 키가 설정되지 않았습니다.")
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})


        results = get_recent_popular_shorts(
            api_key=API_KEY,
            min_views=min_views,
            days_ago=days_ago,
            max_results=max_results,
            category_id=category_id if category_id != 'any' else None,
            region_code=region_code,
            language=language if language != 'any' else None,
            duration_max=duration_max,
            keyword=keyword
        )

        print(f"검색 결과: {len(results)}개 항목 찾음")


        return jsonify({"status": "success", "results": results, "count": len(results)})

    except Exception as e:
        print(f"검색 중 오류 발생: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # 환경 변수에 API_KEY가 없으면 경고
    if not API_KEY:
        print("경고: YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("다음 명령으로 설정하세요: export YOUTUBE_API_KEY='YOUR_API_KEY'")

    # Render, Heroku 등의 호스팅 환경에서 자동으로 포트 설정
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


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
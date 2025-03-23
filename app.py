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


# app.py의 get_recent_popular_shorts 함수 수정

def get_recent_popular_shorts(api_key, min_views=10000, max_views=None, days_ago=5, max_results=50,
                             category_id=None, region_code="KR", language=None,
                             duration_max=60, keyword=None, title_contains=None, 
                             description_contains=None, channel_ids=None):
    """
    인기 YouTube Shorts 검색 함수 - 대량의 결과를 처리하도록 개선
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
        'description_contains': description_contains,
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
          f"제목 포함: {title_contains if title_contains else '없음'}, "
          f"설명 포함: {description_contains if description_contains else '없음'}, "
          f"지역: {region_code}, 언어: {language if language and language != 'any' else '모두'}, "
          f"채널IDs: {channel_ids if channel_ids else '모든 채널'}")

    # API 빌드
    try:
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    except Exception as e:
        print(f"YouTube API 빌드 오류: {str(e)}")
        # 쿼터 제한 오류인 경우 상위로 전파
        if 'quota' in str(e).lower() or 'exceeded' in str(e).lower():
            raise Exception(f"YouTube API 할당량 초과: {str(e)}")
        raise

    # 여러 채널 ID가 있는 경우 각 채널별로 검색하고 결과 합치기
    all_results = []
    
    try:
        # 키워드 처리
        original_keyword = keyword
        enhanced_keyword = None
        
        # 키워드가 있는 경우에만 처리
        if keyword and keyword.strip():
            enhanced_keyword = keyword.strip()
            
            # 키워드에 콤마가 있으면 공백으로 변환 (OR 검색)
            if enhanced_keyword and ',' in enhanced_keyword:
                enhanced_keyword = enhanced_keyword.replace(',', ' ')
                
            print(f"키워드 처리: 원본 '{original_keyword}' -> 처리 후 '{enhanced_keyword}'")
        else:
            print("키워드 없음")
        
        # 요청 결과 수 계산: 일반 검색 또는 채널별 검색
        if not channel_ids:
            # 일반 검색 - 요청 결과 수는 max_results
            # 기본 검색은 최대 300개 결과로 증가
            enhanced_max_results = min(300, max_results * 3)  # 기본적으로 요청된 결과의 3배까지 검색 (최대 300개)
            
            print(f"일반 검색: {enhanced_max_results}개 결과 요청 (원래 요청: {max_results}개)")
            
            search_results = perform_search(youtube, min_views, max_views, days_ago, enhanced_max_results, 
                                           category_id, region_code, language, duration_max, 
                                           enhanced_keyword, title_contains, description_contains, None)
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
            results_per_channel = min(100, max(20, math.ceil(300 / channel_count)))  
            
            print(f"채널별 검색: {channel_count}개 채널, 채널당 {results_per_channel}개 요청")
                
            # 각 채널별로 검색 실행
            for channel_id in channel_id_list:
                channel_results = perform_search(youtube, min_views, max_views, days_ago, 
                                               results_per_channel, 
                                               category_id, region_code, language, duration_max, 
                                               enhanced_keyword, title_contains, description_contains, channel_id)
                all_results.extend(channel_results)
    except Exception as e:
        print(f"검색 실행 중 오류: {str(e)}")
        # 쿼터 제한 오류인 경우 상위로 전파
        if 'quota' in str(e).lower() or 'exceeded' in str(e).lower():
            raise Exception(f"YouTube API 할당량 초과: {str(e)}")
        # 다른 오류는 빈 결과 반환
        all_results = []
    
    # 중복 제거 (비디오 ID 기준)
    seen_video_ids = set()
    unique_results = []
    for video in all_results:
        if video['id'] not in seen_video_ids:
            seen_video_ids.add(video['id'])
            unique_results.append(video)
   
    # 조회수 기준 내림차순 정렬
    unique_results.sort(key=lambda x: x['viewCount'], reverse=True)
    
    # 최대 결과 수 제한 - 이제 사용자 요청보다 많은 결과 반환
    # 클라이언트에서 필터링을 위해 더 많은 데이터 필요
    final_result_limit = min(300, max(max_results, len(unique_results)))
    if len(unique_results) > final_result_limit:
        unique_results = unique_results[:final_result_limit]
    
    # 결과 캐싱
    save_to_cache(cache_key, unique_results)
    
    # 결과 통계 출력
    if unique_results:
        print(f"검색 결과: {len(unique_results)}개 비디오 찾음, 국가: {region_code}")
    else:
        print(f"검색 결과 없음! 국가: {region_code}, 키워드: {keyword}")
    
    return unique_results


def perform_search(youtube, min_views, max_views, days_ago, max_results, 
                  category_id, region_code, language, duration_max, 
                  keyword, title_contains, description_contains, channel_id):
    """단일 검색 수행 함수 - 페이지네이션 추가 및 설명란 필터링 기능 유지"""
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
    print(f"실제 검색 조건: keyword={keyword}, min_views={min_views}, max_views={max_views}, "
          f"days_ago={days_ago}, region_code={region_code}, max_results={max_results}")

    # 페이지네이션으로 모든 결과 수집
    all_video_ids = []
    next_page_token = None

    try:
        print("YouTube 검색 API 호출 시작 (페이지네이션 사용)...")
        while len(all_video_ids) < max_results:
            if next_page_token:
                search_params['pageToken'] = next_page_token
            
            search_response = youtube.search().list(**search_params).execute()
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
        if 'quota' in str(e).lower() or 'exceeded' in str(e).lower():
            raise Exception(f"YouTube API 할당량 초과: {str(e)}")
        return []

    if not all_video_ids:
        print("검색 결과 없음 - 빈 리스트 반환")
        return []

    # 비디오 상세 정보 가져오기 (50개씩 배치 처리)
    filtered_videos = []
    for i in range(0, len(all_video_ids), 50):
        batch_ids = all_video_ids[i:i + 50]
        try:
            print(f"비디오 상세 정보 요청: {len(batch_ids)}개 ID (총 {len(all_video_ids)}개 중)")
            video_response = youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(batch_ids),
                regionCode=region_code
            ).execute()
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

                    if (view_count >= min_views and
                        (max_views is None or view_count <= max_views) and
                        duration_seconds <= duration_max):

                        if title_contains and title_contains.lower() not in item['snippet']['title'].lower():
                            continue
                        if description_contains:
                            description = item['snippet'].get('description', '')
                            if description_contains.lower() not in description.lower():
                                continue

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
            if 'quota' in str(e).lower() or 'exceeded' in str(e).lower():
                raise Exception(f"YouTube API 할당량 초과: {str(e)}")
            continue
    
    print(f"필터링 후 최종 결과: {len(filtered_videos)}개 항목")
    return filtered_videos

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

        # 콤마가 포함된 문자열을 처리하여 정수로 변환
        try:
            min_views_str = data.get('min_views', '10000')
            min_views = int(min_views_str.replace(',', '')) if min_views_str else 10000
            
            max_views_str = data.get('max_views', '')
            max_views = int(max_views_str.replace(',', '')) if max_views_str.strip() else None
        except ValueError as e:
            print(f"조회수 값 변환 중 오류: {str(e)}")
            return jsonify({"status": "error", "message": f"조회수 값이 유효하지 않습니다: {str(e)}"})
        
        days_ago = int(data.get('days_ago', 5))
        
        # 사용자 입력 max_results는 UI 표시 용도로만 사용
        user_max_results = int(data.get('max_results', 50))
        # 실제 API 요청에는 증가된 값(300) 사용
        api_max_results = 300
        
        category_id = data.get('category_id', 'any')
        region_code = data.get('region_code', 'KR')
        language = data.get('language', 'any')
        duration_max = int(data.get('duration_max', 60))
        keyword = data.get('keyword', '')
        title_contains = data.get('title_contains', '')
        description_contains = data.get('description_contains', '')  # 설명 필터 추가
        
        # 여러 채널 ID 처리
        channel_ids = data.get('channel_ids', '')

        if not API_KEY:
            print("경고: API 키가 설정되지 않았습니다.")
            return jsonify({"status": "error", "message": "API 키가 설정되지 않았습니다."})

        try:
            results = get_recent_popular_shorts(
                api_key=API_KEY,
                min_views=min_views,
                max_views=max_views,
                days_ago=days_ago,
                max_results=api_max_results,  # 여기서 증가된 값 사용
                category_id=category_id if category_id != 'any' else None,
                region_code=region_code,
                language=language if language != 'any' else None,
                duration_max=duration_max,
                keyword=keyword,
                title_contains=title_contains,
                description_contains=description_contains,
                channel_ids=channel_ids if channel_ids else None
            )

            # 결과를 사용자가 요청한 max_results로 제한
            if len(results) > user_max_results:
                displayed_results = results[:user_max_results]
            else:
                displayed_results = results

            print(f"API 검색 결과: {len(results)}개 항목 찾음, 표시: {len(displayed_results)}개")
            return jsonify({
                "status": "success", 
                "results": results,  # 전체 결과 반환 (클라이언트에서 필터링에 사용)
                "count": len(results),
                "displayCount": len(displayed_results)
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"검색 중 오류 발생: {error_msg}")
            
            # 쿼터 초과 오류 확인
            if 'quota' in error_msg.lower() or 'exceeded' in error_msg.lower():
                return jsonify({
                    "status": "quota_exceeded", 
                    "message": "YouTube API 일일 할당량이 초과되었습니다. 내일 다시 시도해주세요.",
                    "details": error_msg
                })
            else:
                return jsonify({"status": "error", "message": error_msg})

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

@app.route('/favicon.ico')
def favicon():
    """Favicon 반환 라우트"""
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
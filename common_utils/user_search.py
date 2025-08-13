# common_utils/user_search.py
import time
import isodate
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
from services.user_api_service import UserApiKeyManager
import googleapiclient.discovery
from flask import current_app

class UserSearchService:
    """사용자별 API 키를 사용하는 검색 서비스"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.api_manager = UserApiKeyManager(user_id)
        
    def search_recent_popular_shorts(self, min_views=100000, days_ago=5, max_results=20,
                                   category_id=None, region_code="KR", language=None,
                                   channel_ids=None, keyword=None):
        """
        사용자의 개인 API 키를 사용한 최신 인기 쇼츠 검색
        """
        all_filtered_videos = []
        
        if isinstance(channel_ids, str):
            channel_id_list = [ch.strip() for ch in channel_ids.split(',') if ch.strip()]
        else:
            channel_id_list = channel_ids or []

        if channel_id_list:
            # 채널 기반 검색
            return self._search_by_channels(
                channel_id_list, min_views, days_ago, max_results, region_code
            )
        elif keyword:
            # 키워드 기반 검색
            return self._search_by_keyword(
                keyword, min_views, days_ago, max_results, 
                category_id, region_code, language
            )
        
        return []
    
    def _search_by_channels(self, channel_ids, min_views, days_ago, max_results, region_code):
        """채널 ID 기반 검색"""
        all_filtered_videos = []
        
        # 채널 개수 제한
        if len(channel_ids) > 20:
            current_app.logger.info(f"채널 개수 제한: {len(channel_ids)}개 → 20개")
            channel_ids = channel_ids[:20]
        
        # 날짜 필터 설정
        published_after = None
        if days_ago > 0:
            published_after = (datetime.utcnow() - timedelta(days=days_ago)).isoformat("T") + "Z"
        
        current_app.logger.info(f"채널 기반 검색 시작: {len(channel_ids)}개 채널, 최소조회수: {min_views:,}")
        
        for channel_id in channel_ids:
            try:
                # 채널별 영상 검색
                search_params = {
                    'part': 'snippet',
                    'channelId': channel_id,
                    'order': 'date',
                    'type': 'video',
                    'maxResults': min(50, max_results)
                }
                
                if published_after:
                    search_params['publishedAfter'] = published_after
                
                # API 호출
                def search_call():
                    youtube = self.api_manager.get_youtube_service()
                    return youtube.search().list(**search_params).execute()
                
                search_response = self.api_manager.execute_api_call(
                    search_call, 'search.list', quota_cost=100
                )
                
                video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
                
                if not video_ids:
                    continue
                
                # 비디오 상세 정보 조회
                def videos_call():
                    youtube = self.api_manager.get_youtube_service()
                    return youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(video_ids)
                    ).execute()
                
                video_response = self.api_manager.execute_api_call(
                    videos_call, 'videos.list', quota_cost=1
                )
                
                # 영상 필터링 및 처리
                for item in video_response.get('items', []):
                    try:
                        view_count = int(item['statistics'].get('viewCount', 0))
                        duration = item['contentDetails']['duration']
                        duration_seconds = isodate.parse_duration(duration).total_seconds()
                        
                        # 추가 날짜 필터링
                        if days_ago > 0:
                            published_at = datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
                            if published_at < cutoff_date:
                                continue
                        
                        # 조회수 및 길이 필터
                        if view_count < min_views or duration_seconds > 60:
                            continue
                        
                        title = item['snippet']['title']
                        translated_title = self._translate_if_needed(title)
                        
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
                        current_app.logger.error(f"영상 개별 처리 오류: {str(ve)}")
                        continue
                        
            except Exception as e:
                error_str = str(e).lower()
                if 'api 키' in error_str or '할당량' in error_str:
                    # 사용자에게 친숙한 메시지로 변환
                    raise Exception("등록된 API 키의 할당량이 부족합니다. API 키 관리 페이지에서 키를 추가하거나 확인해주세요.")
                else:
                    current_app.logger.error(f"채널 검색 오류 ({channel_id}): {str(e)}")
                    continue
        
        # 최신순 정렬 및 제한
        all_filtered_videos.sort(
            key=lambda x: datetime.strptime(x['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"), 
            reverse=True
        )
        
        return all_filtered_videos[:max_results]
    
    def _search_by_keyword(self, keyword, min_views, days_ago, max_results, 
                          category_id, region_code, language):
        """키워드 기반 검색"""
        filtered_videos = []
        
        published_after = (datetime.utcnow() - timedelta(days=days_ago)).isoformat("T") + "Z"
        
        search_params = {
            'part': 'snippet',
            'maxResults': 50,
            'order': 'viewCount',
            'type': 'video',
            'videoDuration': 'short',
            'publishedAfter': published_after,
            'regionCode': region_code,
            'q': keyword
        }
        
        if category_id and category_id != 'any':
            search_params['videoCategoryId'] = category_id
        if language and language != 'any':
            search_params['relevanceLanguage'] = language
        
        current_app.logger.info(f"키워드 검색 시작: '{keyword}', 최소조회수: {min_views:,}")
        
        try:
            all_video_ids = []
            next_page_token = None
            
            # 페이지네이션으로 영상 ID 수집
            while len(all_video_ids) < max_results:
                if next_page_token:
                    search_params['pageToken'] = next_page_token
                
                def search_call():
                    youtube = self.api_manager.get_youtube_service()
                    return youtube.search().list(**search_params).execute()
                
                search_response = self.api_manager.execute_api_call(
                    search_call, 'search.list', quota_cost=100
                )
                
                items = search_response.get('items', [])
                video_ids = [item['id']['videoId'] for item in items]
                all_video_ids.extend(video_ids)
                
                next_page_token = search_response.get('nextPageToken')
                if not next_page_token or len(items) == 0:
                    break
            
            # 최대 결과 수 제한
            if len(all_video_ids) > max_results:
                all_video_ids = all_video_ids[:max_results]
            
            # 영상 상세 정보 가져오기 (50개씩 배치 처리)
            for i in range(0, len(all_video_ids), 50):
                batch_ids = all_video_ids[i:i+50]
                
                def videos_call():
                    youtube = self.api_manager.get_youtube_service()
                    return youtube.videos().list(
                        part='snippet,statistics,contentDetails',
                        id=','.join(batch_ids)
                    ).execute()
                
                video_response = self.api_manager.execute_api_call(
                    videos_call, 'videos.list', quota_cost=1
                )
                
                for item in video_response.get('items', []):
                    try:
                        view_count = int(item['statistics'].get('viewCount', 0))
                        duration = item['contentDetails']['duration']
                        duration_seconds = isodate.parse_duration(duration).total_seconds()
                        
                        if view_count < min_views or duration_seconds > 60:
                            continue
                        
                        title = item['snippet']['title']
                        translated_title = self._translate_if_needed(title)
                        
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
                        current_app.logger.error(f"영상 개별 처리 오류: {str(ve)}")
                        continue
            
            # 최신순 정렬 및 제한
            filtered_videos.sort(
                key=lambda x: datetime.strptime(x['publishedAt'], "%Y-%m-%dT%H:%M:%SZ"), 
                reverse=True
            )
            
            return filtered_videos[:max_results]
            
        except Exception as e:
            error_str = str(e).lower()
            if 'api 키' in error_str or '할당량' in error_str:
                raise Exception("등록된 API 키의 할당량이 부족합니다. API 키 관리 페이지에서 키를 추가하거나 확인해주세요.")
            else:
                current_app.logger.error(f"키워드 검색 오류: {str(e)}")
                raise
    
    def _translate_if_needed(self, title):
        """필요시 제목 번역 (한글이 없는 경우만)"""
        try:
            # 한글이 포함되어 있지 않은 경우만 번역
            if not any('\uAC00' <= c <= '\uD7A3' for c in title):
                # 간단한 번역 (번역 기능은 선택적으로 비활성화 가능)
                return None  # 현재는 번역 비활성화
            return None
        except:
            return None
    
    def search_channels(self, query):
        """채널 검색 (사용자 API 키 사용)"""
        try:
            if '@' in query or 'youtube.com/' in query:
                # 핸들 또는 URL 검색
                return self._search_channel_by_handle(query)
            else:
                # 일반 채널 검색
                return self._search_channels_by_name(query)
                
        except Exception as e:
            error_str = str(e).lower()
            if 'api 키' in error_str or '할당량' in error_str:
                raise Exception("등록된 API 키의 할당량이 부족합니다. API 키 관리 페이지에서 키를 추가하거나 확인해주세요.")
            else:
                raise
    
    def _search_channel_by_handle(self, query):
        """핸들로 채널 검색"""
        # URL에서 핸들 추출
        if 'youtube.com/' in query:
            parts = query.split('/')
            for part in parts:
                if part.startswith('@'):
                    query = part
                    break
        
        # @ 기호 처리
        if not query.startswith('@') and '@' not in query:
            query = '@' + query
        
        handle = query.replace('@', '')
        
        try:
            # forHandle 파라미터로 정확한 핸들 매칭 시도
            def handle_search_call():
                youtube = self.api_manager.get_youtube_service()
                return youtube.channels().list(
                    part="snippet",
                    forHandle=handle,
                    maxResults=1
                ).execute()
            
            response = self.api_manager.execute_api_call(
                handle_search_call, 'channels.list', quota_cost=1
            )
            
            if response.get('items'):
                item = response['items'][0]
                return [{
                    'id': item['id'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', ''),
                    'description': item['snippet']['description']
                }]
                
        except Exception:
            pass  # forHandle 실패시 일반 검색으로 넘어감
        
        # 대체 방법: 일반 검색으로 핸들 매칭
        def fallback_search_call():
            youtube = self.api_manager.get_youtube_service()
            return youtube.search().list(
                part="snippet",
                type="channel",
                q=handle,
                maxResults=10
            ).execute()
        
        response = self.api_manager.execute_api_call(
            fallback_search_call, 'search.list', quota_cost=100
        )
        
        # 정확한 매칭 우선
        exact_matches = []
        for item in response.get('items', []):
            channel_title = item['snippet']['title'].lower()
            if channel_title == handle.lower():
                exact_matches.append({
                    'id': item['id']['channelId'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', ''),
                    'description': item['snippet']['description']
                })
        
        return exact_matches[:3] if exact_matches else []
    
    def _search_channels_by_name(self, query):
        """이름으로 채널 검색"""
        def search_call():
            youtube = self.api_manager.get_youtube_service()
            return youtube.search().list(
                part="snippet",
                type="channel",
                q=query,
                maxResults=5
            ).execute()
        
        response = self.api_manager.execute_api_call(
            search_call, 'search.list', quota_cost=100
        )
        
        channels = []
        for item in response.get('items', []):
            channels.append({
                'id': item['id']['channelId'],
                'title': item['snippet']['title'],
                'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', ''),
                'description': item['snippet']['description']
            })
        
        return channels

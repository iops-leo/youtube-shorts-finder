// 전역 변수 설정
let allResults = []; // 전체 결과 저장
let currentPage = 1; // 현재 페이지
let itemsPerPage = 12; // 페이지당 아이템 수
let selectedChannels = []; // 선택된 채널 목록 저장

const MAX_HISTORY_ITEMS = 10; // 최대 저장 기록 수
const HISTORY_STORAGE_KEY = 'youtubeShortSearchHistory';
const CURRENT_PREFS_KEY = 'youtubeShortSearchPrefs';


// DOM 요소 참조
const loadMoreButton = document.getElementById('loadMoreButton');
const loadMoreContainer = document.getElementById('loadMoreContainer');
const channelSearchInput = document.getElementById('channel_search');
const channelSearchResults = document.getElementById('channelSearchResults');
const selectedChannelsContainer = document.getElementById('selectedChannels');
const channelIdsInput = document.getElementById('channel_ids');
const clearAllChannelsBtn = document.getElementById('clearAllChannels');
const channelCounter = document.getElementById('channelCounter');
const resetSettingsBtn = document.getElementById('resetSettings');
const searchForm = document.getElementById('searchForm');

// 페이지 로드 시 이벤트 설정
document.addEventListener('DOMContentLoaded', function() {
    // 저장된 폼 값 복원
    loadFormValuesFromLocalStorage();
    
    // 선택된 채널 UI 업데이트
    updateSelectedChannelsUI();
    
    // 이벤트 리스너 설정
    setupEventListeners();


    // 새로운 개선 기능 초기화
    enhanceKeywordField();
    enhanceVideoCards();
    addSortingFeature();
    
    // 숫자 포맷팅 설정 추가
    setupNumberFormatting();
});

// 이벤트 리스너 설정 함수
function setupEventListeners() {
    // 채널 검색 입력 이벤트
    channelSearchInput.addEventListener('input', function() {
        searchChannel(this.value);
    });
    
    // 모든 채널 초기화 버튼
    clearAllChannelsBtn.addEventListener('click', function() {
        clearAllChannels();
    });
    
    // 설정 초기화 버튼 클릭 이벤트
    resetSettingsBtn.addEventListener('click', function() {
        if (confirm('저장된 모든 검색 설정을 초기화하시겠습니까?')) {
            localStorage.removeItem('youtubeShortSearchPrefs');
            location.reload();
        }
    });
    
    // 외부 클릭 시 검색 결과 닫기
    document.addEventListener('click', function(e) {
        if (!channelSearchInput.contains(e.target) && !channelSearchResults.contains(e.target)) {
            channelSearchResults.style.display = 'none';
        }
    });
    
    // 더 보기 버튼 클릭 이벤트
    loadMoreButton.addEventListener('click', function() {
        currentPage++;
        renderResults(currentPage);
    });
    
    // 검색 폼 제출 이벤트
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // 초기화
        allResults = [];
        currentPage = 1;
        loadMoreContainer.style.display = 'none';
        
        // 검색 실행 시 설정 저장
        saveFormValuesToLocalStorage();
        
        // 검색 기록 저장
        saveSearchHistory();
        
        // 검색 실행
        performSearch(this);
    });
    
    // 히스토리 모달 이벤트 - 모달이 표시될 때 내용 업데이트
    const historyModal = document.getElementById('historyModal');
    if (historyModal) {
        historyModal.addEventListener('shown.bs.modal', function() {
            showSearchHistoryModal();
        });
    }
    
    // 히스토리 삭제 버튼
    const clearHistoryButton = document.getElementById('clearHistoryButton');
    if (clearHistoryButton) {
        clearHistoryButton.addEventListener('click', function() {
            clearAllSearchHistory();
        });
    }
    
    // 검색 기록 버튼 UI 초기화
    updateHistoryButtonUI();
}

// 채널 관리 함수들
// 채널 추가 함수
function addChannel(channel) {
    // 이미 추가된 채널인지 확인
    const isAlreadyAdded = selectedChannels.some(ch => ch.id === channel.id);
    if (isAlreadyAdded) {
        alert('이미 추가된 채널입니다.');
        return;
    }
    
    // 채널 개수 제한 (최대 50개)
    if (selectedChannels.length >= 50) {
        alert('최대 50개까지만 채널을 추가할 수 있습니다.');
        return;
    }
    
    // 기본 이미지 URL 설정 (썸네일이 없을 경우)
    if (!channel.thumbnail || channel.thumbnail.trim() === '') {
        channel.thumbnail = 'https://via.placeholder.com/40';
    }
    
    // 채널 추가
    selectedChannels.push(channel);
    
    // UI 업데이트
    updateSelectedChannelsUI();
    
    // 검색 입력 초기화 및 결과 숨기기
    channelSearchInput.value = '';
    channelSearchResults.style.display = 'none';
    
    // 로컬 스토리지 업데이트
    saveFormValuesToLocalStorage();
}

// 채널 제거 함수
function removeChannel(channelId) {
    // 해당 채널 삭제
    selectedChannels = selectedChannels.filter(ch => ch.id !== channelId);
    
    // UI 업데이트
    updateSelectedChannelsUI();
    
    // 로컬 스토리지 업데이트
    saveFormValuesToLocalStorage();
}

// 모든 채널 초기화 함수
function clearAllChannels() {
    if (selectedChannels.length === 0) return;
    
    if (confirm('선택한 모든 채널을 삭제하시겠습니까?')) {
        selectedChannels = [];
        updateSelectedChannelsUI();
        saveFormValuesToLocalStorage();
    }
}

// 선택된 채널 UI 업데이트 함수
function updateSelectedChannelsUI() {
    // 선택된 채널 컨테이너 비우기
    selectedChannelsContainer.innerHTML = '';
    
    // 선택된 채널이 없는 경우
    if (selectedChannels.length === 0) {
        selectedChannelsContainer.innerHTML = '<div class="empty-channels-message">선택된 채널이 없습니다. 채널을 검색하여 추가해주세요.</div>';
        channelIdsInput.value = '';
        channelCounter.textContent = '선택된 채널: 0개';
        return;
    }
    
    // 각 채널 항목 생성 및 추가
    selectedChannels.forEach(channel => {
        // 기본 이미지 URL 설정 (썸네일이 없을 경우)
        const thumbnailUrl = channel.thumbnail || 'https://via.placeholder.com/24';
        
        const channelItem = document.createElement('div');
        channelItem.className = 'selected-channel-item';
        channelItem.innerHTML = `
            <img src="${thumbnailUrl}" alt="${channel.title}" onerror="this.src='https://via.placeholder.com/24'">
            <span class="channel-name" title="${channel.title}">${channel.title}</span>
            <button type="button" class="remove-channel" data-channel-id="${channel.id}">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // 채널 삭제 버튼 이벤트
        const removeBtn = channelItem.querySelector('.remove-channel');
        removeBtn.addEventListener('click', function() {
            removeChannel(this.dataset.channelId);
        });
        
        selectedChannelsContainer.appendChild(channelItem);
    });
    
    // hidden input 필드에 채널 ID 목록 설정
    channelIdsInput.value = selectedChannels.map(ch => ch.id).join(',');
    
    // 카운터 업데이트
    channelCounter.textContent = `선택된 채널: ${selectedChannels.length}개`;
}

// 로컬 스토리지 관련 함수
// 폼 값 저장 함수
function saveFormValuesToLocalStorage() {
    const formData = new FormData(searchForm);
    const formValues = {};
    
    // FormData를 객체로 변환
    for (let [key, value] of formData.entries()) {
        formValues[key] = value;
    }
    
    // 선택된 채널 정보 저장
    formValues['selectedChannels'] = selectedChannels;
    
    // 객체를 JSON 문자열로 변환하여 저장
    localStorage.setItem('youtubeShortSearchPrefs', JSON.stringify(formValues));
    console.log('검색 설정이 저장되었습니다.');
}

// 폼 값 복원 함수
function loadFormValuesFromLocalStorage() {
    const savedValues = localStorage.getItem('youtubeShortSearchPrefs');
    if (!savedValues) return;
    
    try {
        const formValues = JSON.parse(savedValues);
        
        // 각 입력 필드에 저장된 값 설정
        for (const key in formValues) {
            const input = searchForm.elements[key];
            if (input && key !== 'selectedChannels') {
                input.value = formValues[key];
            }
        }
        
        // 채널 정보 복원 (있는 경우)
        if (formValues['selectedChannels'] && Array.isArray(formValues['selectedChannels'])) {
            selectedChannels = formValues['selectedChannels'];
        }
        
        console.log('저장된 검색 설정을 불러왔습니다.');
    } catch (error) {
        console.error('저장된 설정을 불러오는 중 오류 발생:', error);
        localStorage.removeItem('youtubeShortSearchPrefs');
    }
}

// 채널 검색 관련 함수
// 디바운스 함수
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 채널 검색 함수
const searchChannel = debounce(function(query) {
    // 입력된 검색어 정리
    query = query.trim();
    
    // 검색창이 비어있으면 결과 숨김
    if (!query) {
        channelSearchResults.style.display = 'none';
        return;
    }
    
    // 최소 2글자 이상 입력 필요
    if (query.length < 2) {
        channelSearchResults.innerHTML = '<div class="p-3 text-center">최소 2글자 이상 입력하세요.</div>';
        channelSearchResults.style.display = 'block';
        return;
    }
    
    // 로딩 표시
    channelSearchResults.innerHTML = '<div class="p-3 text-center"><i class="fas fa-spinner fa-spin me-2"></i>검색 중...</div>';
    channelSearchResults.style.display = 'block';
    
    fetch(`/channel-search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.channels.length > 0) {
                channelSearchResults.innerHTML = '';
                data.channels.forEach(channel => {
                    // 기본 이미지 URL 설정 (채널 썸네일이 없을 경우)
                    const thumbnailUrl = channel.thumbnail || 'https://via.placeholder.com/40';
                    
                    const channelItem = document.createElement('div');
                    channelItem.className = 'channel-item';
                    channelItem.innerHTML = `
                        <img src="${thumbnailUrl}" class="channel-thumbnail" alt="${channel.title}" onerror="this.src='https://via.placeholder.com/40'">
                        <div class="channel-info">
                            <div class="channel-title">${channel.title}</div>
                            <div class="channel-description">${channel.description || '설명 없음'}</div>
                        </div>
                    `;
                    
                    // 이미 추가된 채널인지 확인
                    const isAlreadyAdded = selectedChannels.some(ch => ch.id === channel.id);
                    if (isAlreadyAdded) {
                        channelItem.style.opacity = '0.7';
                        channelItem.title = '이미 추가된 채널입니다';
                    } else {
                        channelItem.addEventListener('click', () => {
                            addChannel(channel);
                        });
                    }
                    
                    channelSearchResults.appendChild(channelItem);
                });
                channelSearchResults.style.display = 'block';
            } else {
                channelSearchResults.innerHTML = '<div class="p-3 text-center">채널을 찾을 수 없습니다.</div>';
                channelSearchResults.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('채널 검색 오류:', error);
            channelSearchResults.innerHTML = '<div class="p-3 text-center">오류가 발생했습니다.</div>';
            channelSearchResults.style.display = 'block';
        });
}, 300);

// 검색 및 결과 처리 함수
// main.js의 performSearch 함수 개선

function performSearch(form) {
    // 로딩 표시
    document.getElementById('loader').style.display = 'block';
    document.getElementById('results').innerHTML = '';
    document.getElementById('resultsHeader').style.display = 'none';

    // 폼 데이터 가져오기
    const formData = new FormData(form);

    // max_views 값이 비어있으면 formData에서 제거
    if (formData.get('max_views') && formData.get('max_views').trim() === '') {
        formData.delete('max_views');
    }
    
    // 채널 ID가 비어있으면 제거
    if (formData.get('channel_ids') === '') {
        formData.delete('channel_ids');
    }
    
    // 키워드가 비어있으면 제거 (새로 추가)
    if (formData.get('keyword') && formData.get('keyword').trim() === '') {
        formData.delete('keyword');
        console.log('빈 키워드 필드 제거됨');
    } else if (formData.get('keyword')) {
        console.log('검색 키워드:', formData.get('keyword'));
    }
    
    // 제목 포함 필드가 비어있으면 제거 (새로 추가)
    if (formData.get('title_contains') && formData.get('title_contains').trim() === '') {
        formData.delete('title_contains');
    }

    // API 요청 전 폼 데이터 로깅 (디버깅용)
    console.log('검색 파라미터:');
    for (let [key, value] of formData.entries()) {
        console.log(`${key}: ${value}`);
    }

    // API 요청
    fetch('/search', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // 로딩 숨기기
        document.getElementById('loader').style.display = 'none';

        if (data.status === 'success') {
            // 전체 결과 저장
            allResults = data.results;
            
            // 결과 헤더 표시
            document.getElementById('resultsHeader').style.display = 'block';
            document.getElementById('resultCount').textContent = data.count;

            if (data.results.length === 0) {
                document.getElementById('results').innerHTML = `
                    <div class="col-12">
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle me-2"></i>검색 조건에 맞는 결과가 없습니다.
                            <p class="mt-2 mb-0">
                                <small>
                                    <i class="fas fa-info-circle me-1"></i>다음을 시도해 보세요:
                                    <ul class="mb-0">
                                        <li>다른 키워드를 사용해보세요</li>
                                        <li>국가 설정을 변경해보세요</li>
                                        <li>더 오랜 기간을 검색해보세요 (최근 기간 값 증가)</li>
                                        <li>낮은 최소 조회수를 설정해보세요</li>
                                    </ul>
                                </small>
                            </p>
                        </div>
                    </div>
                `;
                return;
            }
            
            // 첫 페이지 렌더링
            renderResults();
        } 
        else if (data.status === 'quota_exceeded') {
            // API 쿼터 제한 오류 표시
            document.getElementById('resultsHeader').style.display = 'block';
            document.getElementById('resultCount').textContent = '0';
            document.getElementById('results').innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <h5 class="mb-2"><i class="fas fa-exclamation-circle me-2"></i>YouTube API 할당량 초과</h5>
                        <p class="mb-2">YouTube API 일일 할당량이 초과되었습니다. 내일 다시 시도해주세요.</p>
                        <p class="mb-0 small text-muted">
                            <i class="fas fa-info-circle me-1"></i>YouTube Data API는 프로젝트당 하루 일정량의 사용만 허용합니다. 
                            일일 할당량은 미국 태평양 시간(PST) 자정에 리셋됩니다.
                        </p>
                    </div>
                </div>
            `;
        }
        else {
            // 기타 오류 표시
            document.getElementById('resultsHeader').style.display = 'block';
            document.getElementById('resultCount').textContent = '0';
            document.getElementById('results').innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <h5 class="mb-0"><i class="fas fa-exclamation-circle me-2"></i>오류가 발생했습니다</h5>
                        <p class="mb-0">${data.message}</p>
                    </div>
                </div>
            `;
        }
    })
    .catch(error => {
        // 로딩 숨기기
        document.getElementById('loader').style.display = 'none';

        // 오류 표시
        document.getElementById('resultsHeader').style.display = 'block';
        document.getElementById('resultCount').textContent = '0';
        document.getElementById('results').innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    <h5 class="mb-0"><i class="fas fa-wifi me-2"></i>네트워크 오류가 발생했습니다</h5>
                    <p class="mb-0">${error.message}</p>
                </div>
            </div>
        `;
    });
}

// 결과 렌더링 함수
function renderResults(page = 1) {
    const resultsContainer = document.getElementById('results');
    const start = (page - 1) * itemsPerPage;
    const end = page * itemsPerPage;
    const pageItems = allResults.slice(start, end);
    
    if (page === 1) {
        resultsContainer.innerHTML = '';
    }
    
    pageItems.forEach(video => {
        const videoCard = createVideoCard(video);
        resultsContainer.innerHTML += videoCard; // 직접 HTML 추가
    });
    
    // 더 보기 버튼 표시 여부
    if (allResults.length > end) {
        loadMoreContainer.style.display = 'block';
    } else {
        loadMoreContainer.style.display = 'none';
    }
}

// 비디오 카드 생성 함수
function createVideoCard(video) {
    const publishDate = new Date(video.publishedAt).toLocaleDateString('ko-KR');
    
    // 조회수, 좋아요, 댓글 포맷팅
    const viewCount = formatNumber(video.viewCount);
    const likeCount = formatNumber(video.likeCount);
    const commentCount = formatNumber(video.commentCount);
    
    // 국가 정보 배지 추가 (비디오 객체에 regionCode가 있을 경우)
    const regionBadge = video.regionCode ? 
        `<span class="badge bg-info" title="검색 국가 코드">${video.regionCode}</span>` : '';
    
    return `
        <div class="card h-100">
            <a href="${video.url}" target="_blank">
                <img src="${video.thumbnail}" class="card-img-top" alt="${video.title}">
            </a>
            <div class="card-body">
                <h6 class="card-title">${video.title}</h6>
                <p class="card-text small text-muted">
                    <a href="https://www.youtube.com/channel/${video.channelId}" target="_blank" class="text-decoration-none">
                        <i class="fas fa-user-circle me-1"></i>${video.channelTitle}
                    </a>
                    ${regionBadge}
                </p>
                <div class="stats">
                    <span title="조회수">
                        <i class="fas fa-eye me-1"></i>
                        ${viewCount}
                    </span>
                    <span title="좋아요">
                        <i class="fas fa-thumbs-up me-1"></i>
                        ${likeCount}
                    </span>
                    <span title="댓글">
                        <i class="fas fa-comment me-1"></i>
                        ${commentCount}
                    </span>
                </div>
                <div class="mt-2 small text-muted">
                    <i class="far fa-calendar-alt me-1"></i><span>${publishDate}</span> • 
                    <i class="far fa-clock me-1"></i><span>${video.duration}초</span>
                </div>
            </div>
            <div class="card-footer">
                <a href="${video.url}" target="_blank" class="btn btn-sm btn-primary w-100">
                    <i class="fab fa-youtube me-1"></i>쇼츠 보기
                </a>
            </div>
        </div>
    `;
}

// 유틸리티 함수
function formatNumber(num) {
    // 기본 콤마 형식으로 포맷팅
    const withCommas = num.toLocaleString();
    
    // 천 단위 이상일 경우 약어 추가
    if (num >= 1000000) {
        return `${(num / 1000000).toFixed(1)}M (${withCommas})`;
    }
    if (num >= 1000) {
        return `${(num / 1000).toFixed(1)}K (${withCommas})`;
    }
    return withCommas;
}

// 검색 기록 저장 함수
function saveSearchHistory() {
    try {
        // 현재 검색 설정 가져오기
        const currentPrefs = JSON.parse(localStorage.getItem(CURRENT_PREFS_KEY));
        if (!currentPrefs) return;
        
        // 기존 기록 로드
        let history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY)) || [];
        
        // 현재 시간 추가
        const timestamp = new Date().toISOString();
        const historyItem = {
            ...currentPrefs,
            timestamp,
            dateFormatted: new Date().toLocaleString()
        };
        
        // 중복 검사 (완전히 동일한 설정은 저장하지 않음)
        const isDuplicate = history.some(item => {
            // timestamp와 dateFormatted 제외하고 비교
            const item1 = {...item};
            const item2 = {...historyItem};
            
            delete item1.timestamp;
            delete item1.dateFormatted;
            delete item2.timestamp;
            delete item2.dateFormatted;
            
            return JSON.stringify(item1) === JSON.stringify(item2);
        });
        
        if (!isDuplicate) {
            // 최근 검색을 배열 앞에 추가
            history.unshift(historyItem);
            
            // 최대 저장 수 제한
            if (history.length > MAX_HISTORY_ITEMS) {
                history = history.slice(0, MAX_HISTORY_ITEMS);
            }
            
            // 저장
            localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
            
            // 히스토리 버튼 UI 업데이트
            updateHistoryButtonUI();
        }
    } catch (error) {
        console.error('검색 기록 저장 중 오류:', error);
    }
}

// 검색 기록 UI 업데이트
function updateHistoryButtonUI() {
    const historyBtn = document.getElementById('historyButton');
    const historyCount = getSearchHistoryCount();
    
    if (historyCount > 0) {
        historyBtn.textContent = `검색 기록 (${historyCount})`;
        historyBtn.disabled = false;
    } else {
        historyBtn.textContent = '검색 기록';
        historyBtn.disabled = true;
    }
}

// 검색 기록 개수 가져오기
function getSearchHistoryCount() {
    try {
        const history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY)) || [];
        return history.length;
    } catch (error) {
        console.error('검색 기록 읽기 중 오류:', error);
        return 0;
    }
}

// 검색 기록 모달 표시
function showSearchHistoryModal() {
    const history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY)) || [];
    const modalBody = document.getElementById('historyModalBody');
    
    if (history.length === 0) {
        modalBody.innerHTML = '<div class="text-center p-4 text-muted">저장된 검색 기록이 없습니다.</div>';
        return;
    }
    
    // 기록 목록 생성
    let html = '<div class="list-group">';
    
    history.forEach((item, index) => {
        // 기본 정보 추출
        const dateFormatted = item.dateFormatted || '날짜 정보 없음';
        const keyword = item.keyword || '키워드 없음';
        const minViews = item.min_views || '제한 없음';
        const categoryName = getCategoryNameById(item.category_id);
        const regionName = getRegionNameByCode(item.region_code);
        
        // 채널 정보
        const channelCount = item.selectedChannels ? item.selectedChannels.length : 0;
        const channelInfo = channelCount > 0 
            ? `${channelCount}개 채널 선택됨` 
            : '모든 채널';
        
        html += `
            <a href="#" class="list-group-item list-group-item-action search-history-item" data-index="${index}">
                <div class="d-flex w-100 justify-content-between">
                    <h6 class="mb-1">${keyword}</h6>
                    <small class="text-muted">${dateFormatted}</small>
                </div>
                <p class="mb-1">
                    <small>
                        <span class="badge bg-primary me-1">최소 ${formatNumber(minViews)}회</span>
                        <span class="badge bg-secondary me-1">${categoryName}</span>
                        <span class="badge bg-info me-1">${regionName}</span>
                        <span class="badge bg-dark">${channelInfo}</span>
                    </small>
                </p>
            </a>
        `;
    });
    
    html += '</div>';
    modalBody.innerHTML = html;
    
    // 각 항목에 클릭 이벤트 추가
    const historyItems = document.querySelectorAll('.search-history-item');
    historyItems.forEach(item => {
        item.addEventListener('click', function(e) {
            e.preventDefault();
            const index = parseInt(this.dataset.index);
            loadSearchHistoryItem(index);
            
            // 모달 닫기 (Bootstrap 방식)
            const historyModal = bootstrap.Modal.getInstance(document.getElementById('historyModal'));
            historyModal.hide();
        });
    });
}

// 특정 인덱스의 검색 기록 로드
function loadSearchHistoryItem(index) {
    try {
        const history = JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY)) || [];
        if (index < 0 || index >= history.length) return;
        
        const item = history[index];
        
        // 현재 설정으로 저장
        localStorage.setItem(CURRENT_PREFS_KEY, JSON.stringify(item));
        
        // 폼 값 복원
        loadFormValuesFromLocalStorage();
        
        // 알림 표시
        showToast('검색 기록이 로드되었습니다. 검색 버튼을 눌러 검색을 시작하세요.', 'success');
    } catch (error) {
        console.error('검색 기록 로드 중 오류:', error);
        showToast('검색 기록을 로드하는 중 오류가 발생했습니다.', 'danger');
    }
}

// 검색 기록 모두 지우기
function clearAllSearchHistory() {
    if (confirm('모든 검색 기록을 삭제하시겠습니까?')) {
        localStorage.removeItem(HISTORY_STORAGE_KEY);
        updateHistoryButtonUI();
        showToast('모든 검색 기록이 삭제되었습니다.', 'info');
        
        // 모달이 열려있는 경우 내용 업데이트
        const modalBody = document.getElementById('historyModalBody');
        if (modalBody) {
            modalBody.innerHTML = '<div class="text-center p-4 text-muted">저장된 검색 기록이 없습니다.</div>';
        }
    }
}

// 카테고리 ID로 이름 찾기
function getCategoryNameById(id) {
    const categories = [
        {"id": "any", "name": "모든 카테고리"},
        {"id": "1", "name": "영화 & 애니"},
        {"id": "2", "name": "자동차"},
        {"id": "10", "name": "음악"},
        {"id": "15", "name": "동물"},
        {"id": "17", "name": "스포츠"},
        {"id": "20", "name": "게임"},
        {"id": "22", "name": "인물 & 블로그"},
        {"id": "23", "name": "코미디"},
        {"id": "24", "name": "엔터테인먼트"},
        {"id": "25", "name": "뉴스 & 정치"},
        {"id": "26", "name": "노하우 & 스타일"},
        {"id": "27", "name": "교육"},
        {"id": "28", "name": "과학 & 기술"}
    ];
    
    const category = categories.find(cat => cat.id === id);
    return category ? category.name : '카테고리 정보 없음';
}

// 국가 코드로 이름 찾기
function getRegionNameByCode(code) {
    const regions = [
        {"code": "KR", "name": "대한민국"},
        {"code": "US", "name": "미국"},
        {"code": "JP", "name": "일본"},
        {"code": "GB", "name": "영국"},
        {"code": "FR", "name": "프랑스"},
        {"code": "DE", "name": "독일"},
        {"code": "CA", "name": "캐나다"},
        {"code": "AU", "name": "호주"},
        {"code": "CN", "name": "중국"}
    ];
    
    const region = regions.find(reg => reg.code === code);
    return region ? region.name : '국가 정보 없음';
}

// 토스트 알림 표시
function showToast(message, type = 'primary') {
    // 이미 있는 토스트 제거
    const existingToast = document.getElementById('appToast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toastContainer.style.zIndex = '1060';
    
    const toast = document.createElement('div');
    toast.id = 'appToast';
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 3000
    });
    bsToast.show();
}

// 검색어(keyword) 입력 필드에 도움말 추가
function enhanceKeywordField() {
    const keywordInput = document.getElementById('keyword');
    if (keywordInput) {
        keywordInput.placeholder = "검색할 키워드 (콤마로 구분하여 여러 키워드 입력 가능)";
        
        // 도움말 추가
        const keywordHelpText = document.createElement('div');
        keywordHelpText.className = 'form-text text-muted';
        keywordHelpText.innerHTML = '<small>여러 키워드는 콤마(,)로 구분하세요. 예: 축구,농구,야구</small>';
        
        keywordInput.parentNode.appendChild(keywordHelpText);
    }
}

// 비디오 카드에 마우스 오버 시 추가 정보 표시
function enhanceVideoCards() {
    // CSS 스타일 추가
    const style = document.createElement('style');
    style.textContent = `
        .video-hover-info {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 15px;
            overflow: auto;
            z-index: 10;
            transition: opacity 0.3s;
            border-radius: calc(0.375rem - 1px);
        }
        .card:hover .video-hover-info {
            display: block;
            opacity: 1;
        }
    `;
    document.head.appendChild(style);
    
    // 비디오 카드 생성 함수 수정
    window.createVideoCardWithHover = function(video) {
        const publishDate = new Date(video.publishedAt).toLocaleDateString('ko-KR');
        
        // 조회수, 좋아요, 댓글 포맷팅
        const viewCount = formatNumber(video.viewCount);
        const likeCount = formatNumber(video.likeCount);
        const commentCount = formatNumber(video.commentCount);
        
        // 게시일 포맷팅 (날짜 + 시간)
        const publishDateTime = new Date(video.publishedAt).toLocaleString('ko-KR');
        
        return `
                <div class="card">
                    <a href="${video.url}" target="_blank">
                        <img src="${video.thumbnail}" class="card-img-top" alt="${video.title}">
                    </a>
                    <div class="card-body">
                        <h6 class="card-title">${video.title}</h6>
                        <p class="card-text small text-muted">
                            <a href="https://www.youtube.com/channel/${video.channelId}" target="_blank" class="text-decoration-none">
                                <i class="fas fa-user-circle me-1"></i>${video.channelTitle}
                            </a>
                        </p>
                        <div class="stats">
                            <span title="조회수">
                                <i class="fas fa-eye me-1"></i>
                                ${viewCount}
                            </span>
                            <span title="좋아요">
                                <i class="fas fa-thumbs-up me-1"></i>
                                ${likeCount}
                            </span>
                            <span title="댓글">
                                <i class="fas fa-comment me-1"></i>
                                ${commentCount}
                            </span>
                        </div>
                        <div class="mt-2 small text-muted">
                            <i class="far fa-calendar-alt me-1"></i><span>${publishDate}</span> • 
                            <i class="far fa-clock me-1"></i><span>${video.duration}초</span>
                        </div>
                    </div>
                    <div class="card-footer">
                        <a href="${video.url}" target="_blank" class="btn btn-sm btn-primary w-100">
                            <i class="fab fa-youtube me-1"></i>쇼츠 보기
                        </a>
                    </div>
                    
                    <!-- 호버 시 추가 정보 -->
                    <div class="video-hover-info">
                        <h6>${video.title}</h6>
                        <p><strong>채널:</strong> ${video.channelTitle}</p>
                        <p><strong>조회수:</strong> ${viewCount}</p>
                        <p><strong>좋아요:</strong> ${likeCount}</p>
                        <p><strong>댓글:</strong> ${commentCount}</p>
                        <p><strong>게시일:</strong> ${publishDateTime}</p>
                        <p><strong>영상길이:</strong> ${video.duration}초</p>
                        <div class="mt-3">
                            <a href="${video.url}" target="_blank" class="btn btn-sm btn-light w-100">
                                쇼츠 보기
                            </a>
                        </div>
                        <div class="mt-2">
                            <a href="https://www.youtube.com/channel/${video.channelId}" target="_blank" class="btn btn-sm btn-outline-light w-100">
                                채널 방문
                            </a>
                        </div>
                    </div>
                </div>
        `;
    };
    
    // 원래 함수를 새로운 함수로 대체
    window.originalCreateVideoCard = window.createVideoCard;
    window.createVideoCard = window.createVideoCardWithHover;
}

function setupNumberFormatting() {
    // 대상 요소들
    const minViewsInput = document.getElementById('min_views');
    const maxViewsInput = document.getElementById('max_views');
    
    // 포맷팅할 요소들
    const inputsToFormat = [minViewsInput, maxViewsInput];
    
    inputsToFormat.forEach(input => {
      if (!input) return;
      
      // 초기값에 콤마 적용
      if (input.value) {
        input.value = Number(input.value).toLocaleString();
      }
      
      // 입력란에 포커스가 오면 콤마 제거
      input.addEventListener('focus', function() {
        this.value = this.value.replace(/,/g, '');
      });
      
      // 입력란에서 포커스가 나가면 콤마 추가
      input.addEventListener('blur', function() {
        if (this.value) {
          // 숫자가 아닌 문자 제거하고 숫자만 유지
          const numericValue = this.value.replace(/[^\d]/g, '');
          if (numericValue) {
            this.value = Number(numericValue).toLocaleString();
          }
        }
      });
    });
    
    // 폼 제출 시 콤마 제거
    const searchForm = document.getElementById('searchForm');
    if (searchForm) {
      const originalSubmit = searchForm.onsubmit;
      
      searchForm.onsubmit = function(e) {
        e.preventDefault();
        
        // 제출 전에 콤마 제거
        inputsToFormat.forEach(input => {
          if (input && input.value) {
            input.value = input.value.replace(/,/g, '');
          }
        });
        
        // 검색 수행 (기존 로직 호출)
        performSearch(this);
        
        // 화면 표시를 위해 다시 콤마 추가
        setTimeout(() => {
          inputsToFormat.forEach(input => {
            if (input && input.value) {
              input.value = Number(input.value).toLocaleString();
            }
          });
        }, 100);
      };
    }
  }

// 정렬 및 필터링 기능 추가
function addSortingFeature() {
    // 정렬 컨트롤 추가
    const sortingControlHTML = `
        <div class="row">
            <div class="col-md-6 mb-3">
                <label for="sortOption" class="form-label"><i class="fas fa-sort me-1"></i>정렬 기준:</label>
                <select id="sortOption" class="form-select">
                    <option value="viewCount">조회수 (높은순)</option>
                    <option value="viewCountAsc">조회수 (낮은순)</option>
                    <option value="likeCount">좋아요 (높은순)</option>
                    <option value="commentCount">댓글 (높은순)</option>
                    <option value="publishDate">최신순</option>
                    <option value="publishDateAsc">오래된순</option>
                    <option value="duration">길이 (긴순)</option>
                    <option value="durationAsc">길이 (짧은순)</option>
                </select>
            </div>
            <div class="col-md-6 mb-3">
                <label for="filterRegion" class="form-label"><i class="fas fa-globe me-1"></i>국가별 필터:</label>
                <select id="filterRegion" class="form-select">
                    <option value="all">모든 국가 표시</option>
                    <option value="KR">한국 (KR)</option>
                    <option value="US">미국 (US)</option>
                    <option value="JP">일본 (JP)</option>
                    <option value="GB">영국 (GB)</option>
                    <option value="FR">프랑스 (FR)</option>
                    <option value="DE">독일 (DE)</option>
                    <option value="CA">캐나다 (CA)</option>
                    <option value="AU">호주 (AU)</option>
                    <option value="CN">중국 (CN)</option>
                </select>
            </div>
        </div>
    `;
    
    // 결과 헤더 영역에 정렬 컨트롤 추가
    const resultsHeader = document.getElementById('resultsHeader');
    if (resultsHeader) {
        const sortingControlContainer = document.createElement('div');
        sortingControlContainer.className = 'col-12 mt-2';
        sortingControlContainer.innerHTML = sortingControlHTML;
        sortingControlContainer.style.display = 'none';
        sortingControlContainer.id = 'sortingControl';
        resultsHeader.appendChild(sortingControlContainer);
    }
    
    // 정렬 함수
    window.sortResults = function(sortBy) {
        switch(sortBy) {
            case 'viewCount':
                allResults.sort((a, b) => b.viewCount - a.viewCount);
                break;
            case 'viewCountAsc':
                allResults.sort((a, b) => a.viewCount - b.viewCount);
                break;
            case 'likeCount':
                allResults.sort((a, b) => b.likeCount - a.likeCount);
                break;
            case 'commentCount':
                allResults.sort((a, b) => b.commentCount - a.commentCount);
                break;
            case 'publishDate':
                allResults.sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));
                break;
            case 'publishDateAsc':
                allResults.sort((a, b) => new Date(a.publishedAt) - new Date(b.publishedAt));
                break;
            case 'duration':
                allResults.sort((a, b) => b.duration - a.duration);
                break;
            case 'durationAsc':
                allResults.sort((a, b) => a.duration - b.duration);
                break;
        }
        
        // 결과 다시 렌더링
        currentPage = 1;
        document.getElementById('results').innerHTML = '';
        
        // 국가별 필터가 선택되었는지 확인하고 필터링 적용
        const filterRegion = document.getElementById('filterRegion').value;
        renderFilteredResults(filterRegion);
    };
    
    // 국가별 필터링 함수 추가
    window.filterByRegion = function(regionCode) {
        if (!regionCode || regionCode === 'all') {
            // 모든 결과 표시
            currentPage = 1;
            document.getElementById('results').innerHTML = '';
            renderResults();
            return;
        }
        
        // 선택된 국가로 필터링
        currentPage = 1;
        document.getElementById('results').innerHTML = '';
        renderFilteredResults(regionCode);
    };
    
    // 필터링된 결과 렌더링 함수
    function renderFilteredResults(regionCode) {
        if (!regionCode || regionCode === 'all') {
            renderResults();
            return;
        }
        
        // 국가 코드로 필터링된 결과
        const filteredResults = allResults.filter(video => 
            video.regionCode === regionCode || 
            !video.regionCode // regionCode 속성이 없는 기존 비디오도 포함
        );
        
        // 필터링 결과 표시
        const resultsContainer = document.getElementById('results');
        
        if (filteredResults.length === 0) {
            resultsContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>선택한 국가(${regionCode})에 해당하는 결과가 없습니다.
                    </div>
                </div>
            `;
            loadMoreContainer.style.display = 'none';
            return;
        }
        
        const start = 0;
        const end = Math.min(itemsPerPage, filteredResults.length);
        const pageItems = filteredResults.slice(start, end);
        
        pageItems.forEach(video => {
            const videoCard = createVideoCard(video);
            resultsContainer.innerHTML += videoCard;
        });
        
        // 더 보기 버튼 표시 여부
        if (filteredResults.length > end) {
            loadMoreContainer.style.display = 'block';
            
            // 더 보기 버튼 이벤트 수정 - 필터링된 결과에 대해 작동하도록
            loadMoreButton.onclick = function() {
                currentPage++;
                const newStart = (currentPage - 1) * itemsPerPage;
                const newEnd = currentPage * itemsPerPage;
                const nextPageItems = filteredResults.slice(newStart, newEnd);
                
                nextPageItems.forEach(video => {
                    const videoCard = createVideoCard(video);
                    resultsContainer.innerHTML += videoCard;
                });
                
                // 더 보기 버튼 표시 여부 업데이트
                if (filteredResults.length <= newEnd) {
                    loadMoreContainer.style.display = 'none';
                }
            };
        } else {
            loadMoreContainer.style.display = 'none';
        }
        
        // 결과 수 업데이트
        document.getElementById('resultCount').textContent = filteredResults.length;
    }
    
    // 정렬 및 필터 변경 이벤트 리스너
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'sortOption') {
            window.sortResults(e.target.value);
        }
        
        if (e.target && e.target.id === 'filterRegion') {
            window.filterByRegion(e.target.value);
        }
    });
    
    // 기존 performSearch 함수 수정 (정렬/필터 컨트롤 표시)
    const originalPerformSearch = window.performSearch;
    window.performSearch = function(form) {
        // 원래 함수 호출
        originalPerformSearch(form);
        
        // 정렬 컨트롤 숨김
        document.getElementById('sortingControl').style.display = 'none';
        
        // API 응답 후 정렬 컨트롤 표시 (0.5초 후)
        setTimeout(function() {
            if (allResults.length > 0) {
                document.getElementById('sortingControl').style.display = 'block';
                
                // 검색 시 사용한 region_code 값으로 기본 필터 설정
                const regionCodeSelect = document.getElementById('region_code');
                const filterRegionSelect = document.getElementById('filterRegion');
                if (regionCodeSelect && filterRegionSelect) {
                    // 검색에 사용된 region_code 값
                    const searchedRegion = regionCodeSelect.value;
                    // filterRegion 선택 옵션 갱신
                    filterRegionSelect.value = searchedRegion;
                }
                
                // 더 보기 버튼 이벤트 초기화 - 전체 결과에 대해 작동하도록
                loadMoreButton.onclick = function() {
                    currentPage++;
                    renderResults(currentPage);
                };
            }
        }, 500);
    };
}
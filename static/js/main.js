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

// Bootstrap 모달 헬퍼 함수들
function safeCloseModal(modalId) {
    try {
        const modalElement = document.getElementById(modalId);
        if (!modalElement) return;
        
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) {
            modalInstance.hide();
        } else {
            // data-bs-dismiss 방식으로 닫기
            modalElement.style.display = 'none';
            modalElement.classList.remove('show');
            document.body.classList.remove('modal-open');
            
            // backdrop 제거
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
        }
    } catch (error) {
        console.error('모달 닫기 오류:', error);
    }
}

function safeShowModal(modalId) {
    try {
        const modalElement = document.getElementById(modalId);
        if (!modalElement) return;
        
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) {
            modalInstance.show();
        } else {
            new bootstrap.Modal(modalElement).show();
        }
    } catch (error) {
        console.error('모달 열기 오류:', error);
    }
}

// 페이지 로드 시 이벤트 설정
document.addEventListener('DOMContentLoaded', function() {
    // 저장된 폼 값 복원
    loadFormValuesFromLocalStorage();
    
    // 선택된 채널 UI 업데이트
    updateSelectedChannelsUI();

    // 이미 마이그레이션이 완료되었는지 확인
    // const migrationCompleted = localStorage.getItem('migration_completed');

    // if (!migrationCompleted) {
    //     // 마이그레이션 실행
    //     migrateLocalStorageToServer();
    // }
    
    // 이벤트 리스너 설정
    setupEventListeners();
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
            localStorage.removeItem(CURRENT_PREFS_KEY);
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
    
    // 정렬 및 필터 이벤트 리스너
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'sortOption') {
            sortResults(e.target.value);
        }
        
        if (e.target && e.target.id === 'filterRegion') {
            filterByRegion(e.target.value);
        }
    });
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
        channel.thumbnail = '/static/img/placeholder-40.svg';
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
        const thumbnailUrl = channel.thumbnail || '/static/img/placeholder-24.svg';
        
        const channelItem = document.createElement('div');
        channelItem.className = 'selected-channel-item';
        channelItem.innerHTML = `
            <img src="${thumbnailUrl}" alt="${channel.title}" onerror="this.src='/static/img/placeholder-24.svg'">
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
    
    // API 호출로 검색 설정 저장
    fetch('/api/search/preferences', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formValues)
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('검색 설정이 저장되었습니다.');
        } else {
            console.error('검색 설정 저장 중 오류:', data.message);
        }
    })
    .catch(error => {
        console.error('검색 설정 저장 중 오류:', error);
    });
}


// 폼 값 복원 함수
function loadFormValuesFromLocalStorage() {
    fetch('/api/search/preferences')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.has_preferences) {
                const formValues = data.preferences;
                
                // 각 입력 필드에 저장된 값 설정
                for (const key in formValues) {
                    const input = searchForm.elements[key];
                    if (input) {
                        input.value = formValues[key];
                    }
                }
                
                console.log('저장된 검색 설정을 불러왔습니다.');
            }
        })
        .catch(error => {
            console.error('저장된 설정을 불러오는 중 오류 발생:', error);
        });
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
                    const thumbnailUrl = channel.thumbnail || '/static/img/placeholder-40.svg';
                    
                    const channelItem = document.createElement('div');
                    channelItem.className = 'channel-item';
                    channelItem.innerHTML = `
                        <img src="${thumbnailUrl}" class="channel-thumbnail" alt="${channel.title}" onerror="this.src='/static/img/placeholder-40.svg'">
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
function performSearch(form) {
    // 로딩 및 프로그레스 표시
    showSearchProgress();
    document.getElementById('results').innerHTML = '';
    document.getElementById('resultsHeader').style.display = 'none';
    document.getElementById('sortingControl').style.display = 'none';

    // 폼 데이터 가져오기
    const formData = new FormData(form);
    
    // API 요청
    fetch('/search', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        // 로딩 및 프로그레스 숨기기
        hideSearchProgress();

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
                                    <i class="fas fa-info-circle me-1"></i>다른 검색 조건을 시도해 보세요.
                                </small>
                            </p>
                        </div>
                    </div>
                `;
                return;
            }
            
            // 정렬/필터 컨트롤 표시
            document.getElementById('sortingControl').style.display = 'block';
            
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
        // 로딩 및 프로그레스 숨기기
        hideSearchProgress();

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
        resultsContainer.appendChild(videoCard);
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
    
    // 국가 정보 배지 추가
    const regionBadge = video.regionCode ? 
        `<span class="badge bg-info" title="검색 국가 코드">${video.regionCode}</span>` : '';
    
    // 설명 내용 처리
    const description = video.description || '';
    const shortDescription = description.length > 100 ? 
        description.substring(0, 100) + '...' : description;
    
    // 번역된 제목이 있으면 표시, 없으면 원본 제목만 표시
    let titleDisplay = `<h6 class="card-title">${video.title}</h6>`;
    if (video.translated_title) {
        titleDisplay = `
            <h6 class="card-title">${video.title}</h6>
            <p class="card-subtitle text-muted small mb-2">
                <i class="fas fa-language me-1"></i>${video.translated_title}
            </p>
        `;
    }
    
    // 카드 생성 - video-card 클래스 추가로 호버 효과 적용
    const card = document.createElement('div');
    card.className = 'card h-100 video-card';
    card.innerHTML = `
        <a href="${video.url}" target="_blank">
            <img src="${video.thumbnail}" class="card-img-top" alt="${video.title}">
        </a>
        <div class="card-body">
            ${titleDisplay}
            <p class="card-text small text-muted">
                <a href="https://www.youtube.com/channel/${video.channelId}" target="_blank" class="text-decoration-none">
                    <i class="fas fa-user-circle me-1"></i>${video.channelTitle}
                </a>
                ${regionBadge}
            </p>
            
            <!-- 설명 내용 표시 -->
            <div class="description-content small text-muted mt-2 mb-2" style="font-size: 0.8rem; max-height: 4.5rem; overflow: hidden;">
                ${shortDescription || '<i>설명 없음</i>'}
            </div>
            
            <div class="d-flex justify-content-between mt-2">
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
            <div class="d-grid gap-1">
                <a href="${video.url}" target="_blank" class="btn btn-sm btn-primary">
                    <i class="fab fa-youtube me-1"></i>쇼츠 보기
                </a>
                <button class="btn btn-sm btn-outline-success save-video-btn" 
                        onclick="saveVideo('${video.id}', '${video.title.replace(/'/g, "\\'")}', '${video.channelTitle.replace(/'/g, "\\'")}', '${video.channelId}', '${video.thumbnail}', '${video.url}', ${video.viewCount}, '${video.duration}', '${video.publishedAt}')">
                    <i class="fas fa-bookmark me-1"></i>영상 저장
                </button>
            </div>
        </div>
    `;
    
    return card;
}

// 정렬 함수
function sortResults(sortBy) {
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
    renderResults();
}

// 국가별 필터링 함수
function filterByRegion(regionCode) {
    const resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';
    currentPage = 1;
    
    if (!regionCode || regionCode === 'all') {
        // 모든 결과 표시
        renderResults();
        return;
    }
    
    // 필터링된 결과
    const filteredResults = allResults.filter(video => 
        video.regionCode === regionCode || !video.regionCode
    );
    
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
    
    // 임시로 allResults 변경 (렌더링 함수 재사용을 위해)
    const originalResults = [...allResults];
    allResults = filteredResults;
    
    renderResults();
    
    // allResults 복원
    allResults = originalResults;
}

// 유틸리티 함수
function formatNumber(num) {
    if (num >= 1000000) {
        return `${(num / 1000000).toFixed(1)}M`;
    }
    if (num >= 1000) {
        return `${(num / 1000).toFixed(1)}K`;
    }
    return num;
}

// 검색 기록 저장 함수
function saveSearchHistory() {
    try {
        // 현재 검색 설정 가져오기
        const formData = new FormData(searchForm);
        const formValues = {};
        
        // FormData를 객체로 변환
        for (let [key, value] of formData.entries()) {
            formValues[key] = value;
        }
        
        // API 호출로 검색 기록 저장
        fetch('/api/search/history', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formValues)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                console.log('검색 기록이 저장되었습니다.');
                updateHistoryButtonUI();
            }
        })
        .catch(error => {
            console.error('검색 기록 저장 중 오류:', error);
        });
    } catch (error) {
        console.error('검색 기록 저장 중 오류:', error);
    }
}

function updateHistoryButtonUI() {
    getSearchHistoryCount(); // 이 함수에서 UI 업데이트 처리
}

// 검색 기록 UI 업데이트
function getSearchHistoryCount() {
    // 비동기 작업이므로 초기값 반환 후 UI 업데이트 방식으로 변경
    fetch('/api/search/history')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const count = data.history.length;
                const historyBtn = document.getElementById('historyButton');
                
                if (count > 0) {
                    historyBtn.textContent = `검색 기록 (${count})`;
                    historyBtn.disabled = false;
                } else {
                    historyBtn.textContent = '검색 기록';
                    historyBtn.disabled = true;
                }
            }
        })
        .catch(error => {
            console.error('검색 기록 읽기 중 오류:', error);
        });
    
    return 0; // 초기값 반환
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

function shareCategories() {
    try {
        fetch('/api/categories')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // 모든 데이터 가져오기
                    const allData = {
                        channelCategories: data.categories,
                        exportDate: new Date().toISOString(),
                        appVersion: '1.0.0'
                    };
                    
                    // JSON 문자열로 변환
                    const jsonString = JSON.stringify(allData);
                    
                    // 데이터 크기 확인 (모바일에서 공유하기에 너무 큰지 확인)
                    const dataSizeKB = Math.round(jsonString.length / 1024);
                    
                    if (dataSizeKB > 100) {
                        showToast(`데이터 크기가 너무 큽니다 (${dataSizeKB}KB). 내보내기 기능을 사용해 주세요.`, 'warning');
                        return;
                    }
                    
                    // 데이터 URL 생성
                    const dataUrl = `data:application/json;charset=utf-8,${encodeURIComponent(jsonString)}`;
                    
                    // 공유 API 사용
                    if (navigator.share) {
                        const file = new File([jsonString], 'youtube-shorts-channels.json', {
                            type: 'application/json',
                        });
                        
                        navigator.share({
                            title: 'YouTube Shorts 채널 데이터',
                            text: 'YouTube Shorts 도구에서 내보낸 채널 카테고리 데이터입니다.',
                            files: [file]
                        }).then(() => {
                            showToast('데이터가 성공적으로 공유되었습니다!', 'success');
                        }).catch((error) => {
                            console.error('공유 오류:', error);
                            
                            // 공유 실패 시 다운로드 방식으로 대체
                            const downloadLink = document.createElement('a');
                            downloadLink.href = dataUrl;
                            downloadLink.download = `youtube-shorts-channels-${new Date().toISOString().slice(0, 10)}.json`;
                            document.body.appendChild(downloadLink);
                            downloadLink.click();
                            document.body.removeChild(downloadLink);
                            
                            showToast('공유할 수 없어 다운로드로 대체되었습니다.', 'info');
                        });
                    } else {
                        // 공유 API를 지원하지 않는 경우 다운로드
                        const downloadLink = document.createElement('a');
                        downloadLink.href = dataUrl;
                        downloadLink.download = `youtube-shorts-channels-${new Date().toISOString().slice(0, 10)}.json`;
                        document.body.appendChild(downloadLink);
                        downloadLink.click();
                        document.body.removeChild(downloadLink);
                        
                        showToast('공유 기능을 지원하지 않는 브라우저입니다. 파일이 다운로드되었습니다.', 'info');
                    }
                }
            })
            .catch(error => {
                console.error('데이터 공유 오류:', error);
                showToast('데이터 공유 중 오류가 발생했습니다.', 'danger');
            });
    } catch (error) {
        console.error('데이터 공유 오류:', error);
        showToast('데이터 공유 중 오류가 발생했습니다.', 'danger');
    }
}

// 검색 기록 모달 표시
function showSearchHistoryModal() {
    const modalBody = document.getElementById('historyModalBody');
    
    // API 호출로 검색 기록 가져오기
    fetch('/api/search/history')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const history = data.history;
                
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
                    
                    html += `
                        <a href="#" class="list-group-item list-group-item-action search-history-item" data-index="${index}">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">${keyword}</h6>
                                <small class="text-muted">${dateFormatted}</small>
                            </div>
                            <p class="mb-1">
                                <small>
                                    <span class="badge bg-primary me-1">최소 ${formatNumber(parseInt(minViews))}회</span>
                                    <span class="badge bg-secondary me-1">${categoryName}</span>
                                    <span class="badge bg-info me-1">${regionName}</span>
                                </small>
                            </p>
                        </a>
                    `;
                });
                
                html += '</div>';
                modalBody.innerHTML = html;
                
                // 각 항목에 클릭 이벤트 추가
                const historyItems = document.querySelectorAll('.search-history-item');
                historyItems.forEach((item, index) => {
                    item.addEventListener('click', function(e) {
                        e.preventDefault();
                        loadSearchHistoryItem(index);
                        
                        // 모달 닫기 (안전한 방식)
                        safeCloseModal('historyModal');
                    });
                });
            }
        })
        .catch(error => {
            console.error('검색 기록 로드 중 오류:', error);
            modalBody.innerHTML = '<div class="text-center p-4 text-danger">검색 기록을 불러오는 중 오류가 발생했습니다.</div>';
        });
}

// 특정 인덱스의 검색 기록 로드
function loadSearchHistoryItem(index) {
    fetch('/api/search/history')
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                const history = data.history;
                if (index < 0 || index >= history.length) return;
                
                const item = history[index];
                
                // 폼 값 설정
                for (const key in item) {
                    const input = searchForm.elements[key];
                    if (input && key !== 'id' && key !== 'created_at' && key !== 'dateFormatted') {
                        input.value = item[key];
                    }
                }
                
                // 선택된 채널 로드 (필요시 서버로부터 채널 정보 가져오기)
                // 이 부분은 추가 API 엔드포인트가 필요할 수 있음
                
                showToast('검색 기록이 로드되었습니다. 검색 버튼을 눌러 검색을 시작하세요.', 'success');
            }
        })
        .catch(error => {
            console.error('검색 기록 로드 중 오류:', error);
            showToast('검색 기록을 로드하는 중 오류가 발생했습니다.', 'danger');
        });
}

// 검색 기록 모두 지우기
function clearAllSearchHistory() {
    if (confirm('모든 검색 기록을 삭제하시겠습니까?')) {
        fetch('/api/search/history', {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                updateHistoryButtonUI();
                showToast('모든 검색 기록이 삭제되었습니다.', 'info');
                
                // 모달이 열려있는 경우 내용 업데이트
                const modalBody = document.getElementById('historyModalBody');
                if (modalBody) {
                    modalBody.innerHTML = '<div class="text-center p-4 text-muted">저장된 검색 기록이 없습니다.</div>';
                }
            } else {
                showToast(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('검색 기록 삭제 중 오류:', error);
            showToast('검색 기록 삭제 중 오류가 발생했습니다.', 'danger');
        });
    }
}

function migrateLocalStorageToServer() {
    // 기존 로컬 스토리지 데이터 확인
    const channelCategories = localStorage.getItem('youtubeShortChannelCategories');
    const searchPrefs = localStorage.getItem('youtubeShortSearchPrefs');
    const searchHistory = localStorage.getItem('youtubeShortSearchHistory');
    
    let migrationPromises = [];
    
    // 카테고리 데이터 마이그레이션
    if (channelCategories) {
        try {
            const categories = JSON.parse(channelCategories);
            if (categories && categories.length > 0) {
                const promise = fetch('/api/categories/import', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ categories: categories })
                });
                migrationPromises.push(promise);
            }
        } catch (e) {
            console.error('카테고리 마이그레이션 오류:', e);
        }
    }
    
    // 검색 설정 마이그레이션
    if (searchPrefs) {
        try {
            const prefs = JSON.parse(searchPrefs);
            if (prefs) {
                const promise = fetch('/api/search/preferences', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(prefs)
                });
                migrationPromises.push(promise);
            }
        } catch (e) {
            console.error('검색 설정 마이그레이션 오류:', e);
        }
    }
    
    // 검색 기록 마이그레이션
    if (searchHistory) {
        try {
            const history = JSON.parse(searchHistory);
            if (history && history.length > 0) {
                // 각 기록 항목에 대해 별도의 요청 생성
                for (const item of history) {
                    const promise = fetch('/api/search/history', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(item)
                    });
                    migrationPromises.push(promise);
                }
            }
        } catch (e) {
            console.error('검색 기록 마이그레이션 오류:', e);
        }
    }
    
    // 모든 마이그레이션 요청 처리
    if (migrationPromises.length > 0) {
        Promise.all(migrationPromises.map(p => p.catch(e => e)))
            .then(results => {
                // 마이그레이션 완료 후 로컬 스토리지 데이터 백업 (삭제하지 않고 이름 변경)
                if (channelCategories) localStorage.setItem('youtubeShortChannelCategories_backup', channelCategories);
                if (searchPrefs) localStorage.setItem('youtubeShortSearchPrefs_backup', searchPrefs);
                if (searchHistory) localStorage.setItem('youtubeShortSearchHistory_backup', searchHistory);
                
                // 마이그레이션 완료 표시
                localStorage.setItem('migration_completed', 'true');
                
                showToast('로컬 데이터가 서버로 성공적으로 마이그레이션되었습니다.', 'success');
            });
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

// 검색 프로그레스 표시 함수
function showSearchProgress() {
    const loader = document.getElementById('loader');
    const apiUsageAlert = document.querySelector('.alert-info'); // API 사용량 표시 요소
    
    loader.innerHTML = `
        <div class="search-progress">
            <div class="alert alert-info text-center">
                <div class="search-status mb-3">
                    <i class="fas fa-search me-2"></i>
                    <strong>채널에서 인기 쇼츠를 검색하는 중...</strong>
                </div>
                <div class="d-flex justify-content-center">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
                <div class="mt-2">
                    <small class="text-muted">잠시만 기다려주세요. 검색이 완료되면 결과를 표시합니다.</small>
                </div>
            </div>
        </div>
    `;
    loader.style.display = 'block';
    
    // API 사용량 알림을 임시로 숨김 (중복 프로그래스바 방지)
    if (apiUsageAlert) {
        apiUsageAlert.style.display = 'none';
    }
}

function hideSearchProgress() {
    const loader = document.getElementById('loader');
    const apiUsageAlert = document.querySelector('.alert-info'); // API 사용량 표시 요소
    
    loader.style.display = 'none';
    loader.innerHTML = '';
    
    // API 사용량 알림 다시 표시
    if (apiUsageAlert) {
        apiUsageAlert.style.display = 'block';
    }
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

// ===================== 저장된 영상 관리 함수들 =====================

/**
 * 영상을 저장하는 함수
 */
function saveVideo(videoId, title, channelTitle, channelId, thumbnail, url, viewCount, duration, publishedAt) {
    const videoData = {
        video_id: videoId,
        video_title: title,
        channel_title: channelTitle,
        channel_id: channelId,
        thumbnail_url: thumbnail,
        video_url: url,
        view_count: parseInt(viewCount) || 0,
        duration: duration,
        published_at: publishedAt
    };
    
    // 버튼 상태 변경 (로딩 표시)
    const saveButton = event.target;
    const originalText = saveButton.innerHTML;
    saveButton.disabled = true;
    saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>저장 중...';
    
    fetch('/api/saved-videos', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(videoData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // 성공 - 버튼 상태 변경
            saveButton.innerHTML = '<i class="fas fa-check me-1"></i>저장됨';
            saveButton.className = 'btn btn-sm btn-success';
            showToast('영상이 저장되었습니다!', 'success');
            
            // 3초 후 원래 상태로 복원
            setTimeout(() => {
                saveButton.disabled = false;
                saveButton.innerHTML = originalText;
                saveButton.className = 'btn btn-sm btn-outline-success save-video-btn';
            }, 3000);
        } else {
            // 실패 처리
            saveButton.disabled = false;
            saveButton.innerHTML = originalText;
            
            if (data.message && data.message.includes('이미 저장된')) {
                showToast('이미 저장된 영상입니다.', 'warning');
                // 이미 저장된 경우 버튼 상태 변경
                saveButton.innerHTML = '<i class="fas fa-bookmark me-1"></i>저장됨';
                saveButton.className = 'btn btn-sm btn-secondary';
                saveButton.disabled = true;
            } else {
                showToast(data.message || '저장 중 오류가 발생했습니다.', 'error');
            }
        }
    })
    .catch(error => {
        console.error('영상 저장 중 오류:', error);
        saveButton.disabled = false;
        saveButton.innerHTML = originalText;
        showToast('저장 중 오류가 발생했습니다.', 'error');
    });
}

/**
 * 개선된 토스트 메시지 함수 (타입별 색상 지원)
 */
function showToast(message, type = 'info') {
    // 기존 토스트 컨테이너 제거
    const existingContainer = document.querySelector('.toast-container');
    if (existingContainer) {
        existingContainer.remove();
    }
    
    // 토스트 컨테이너 생성
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = '9999';
    
    // 타입별 색상 설정
    let bgClass = 'bg-info';
    let iconClass = 'fas fa-info-circle';
    
    switch (type) {
        case 'success':
            bgClass = 'bg-success';
            iconClass = 'fas fa-check-circle';
            break;
        case 'error':
            bgClass = 'bg-danger';
            iconClass = 'fas fa-exclamation-circle';
            break;
        case 'warning':
            bgClass = 'bg-warning text-dark';
            iconClass = 'fas fa-exclamation-triangle';
            break;
    }
    
    // 토스트 생성
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white border-0 ${bgClass}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="${iconClass} me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: type === 'error' ? 5000 : 3000  // 오류 메시지는 더 오래 표시
    });
    bsToast.show();
    
    // 토스트가 숨겨진 후 컨테이너 제거
    toast.addEventListener('hidden.bs.toast', () => {
        toastContainer.remove();
    });
}
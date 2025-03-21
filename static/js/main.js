// 전역 변수 설정
let allResults = []; // 전체 결과 저장
let currentPage = 1; // 현재 페이지
let itemsPerPage = 12; // 페이지당 아이템 수

// DOM 요소 참조
const loadMoreButton = document.getElementById('loadMoreButton');
const loadMoreContainer = document.getElementById('loadMoreContainer');
const channelSearchInput = document.getElementById('channel_search');
const channelSearchResults = document.getElementById('channelSearchResults');
const selectedChannelDiv = document.getElementById('selectedChannel');
const selectedChannelImg = document.getElementById('selectedChannelImg');
const selectedChannelName = document.getElementById('selectedChannelName');
const channelIdInput = document.getElementById('channel_id');
const clearChannelBtn = document.getElementById('clearChannel');
const resetSettingsBtn = document.getElementById('resetSettings');
const searchForm = document.getElementById('searchForm');

// 페이지 로드 시 이벤트 설정
document.addEventListener('DOMContentLoaded', function() {
    // 저장된 폼 값 복원
    loadFormValuesFromLocalStorage();
    
    // 이벤트 리스너 설정
    setupEventListeners();
});

// 이벤트 리스너 설정 함수
function setupEventListeners() {
    // 채널 검색 입력 이벤트
    channelSearchInput.addEventListener('input', function() {
        searchChannel(this.value);
    });
    
    // 채널 검색 초기화 버튼
    clearChannelBtn.addEventListener('click', function() {
        channelIdInput.value = '';
        selectedChannelDiv.style.display = 'none';
        // 채널 정보가 변경되었으므로 로컬 스토리지 업데이트
        saveFormValuesToLocalStorage();
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
        
        // 검색 실행
        performSearch(this);
    });
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
    
    // 선택된 채널 정보 저장 (있는 경우)
    if (selectedChannelDiv.style.display !== 'none') {
        formValues['selectedChannelName'] = selectedChannelName.textContent;
        formValues['selectedChannelImg'] = selectedChannelImg.src;
    }
    
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
            if (input && key !== 'selectedChannelName' && key !== 'selectedChannelImg') {
                input.value = formValues[key];
            }
        }
        
        // 채널 정보 복원 (있는 경우)
        if (formValues['selectedChannelName'] && formValues['selectedChannelImg'] && formValues['channel_id']) {
            selectedChannelName.textContent = formValues['selectedChannelName'];
            selectedChannelImg.src = formValues['selectedChannelImg'];
            selectedChannelDiv.style.display = 'block';
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
    if (!query.trim()) {
        channelSearchResults.style.display = 'none';
        return;
    }
    
    fetch(`/channel-search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.channels.length > 0) {
                channelSearchResults.innerHTML = '';
                data.channels.forEach(channel => {
                    const channelItem = document.createElement('div');
                    channelItem.className = 'channel-item';
                    channelItem.innerHTML = `
                        <img src="${channel.thumbnail}" class="channel-thumbnail" alt="${channel.title}">
                        <div class="channel-info">
                            <div class="channel-title">${channel.title}</div>
                            <div class="channel-description">${channel.description || '설명 없음'}</div>
                        </div>
                    `;
                    channelItem.addEventListener('click', () => {
                        selectChannel(channel);
                    });
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

// 채널 선택 함수
function selectChannel(channel) {
    channelIdInput.value = channel.id;
    selectedChannelImg.src = channel.thumbnail;
    selectedChannelName.textContent = channel.title;
    selectedChannelDiv.style.display = 'block';
    channelSearchInput.value = '';
    channelSearchResults.style.display = 'none';
    
    // 채널 선택 시 로컬 스토리지 업데이트
    saveFormValuesToLocalStorage();
}

// 검색 및 결과 처리 함수
// 검색 실행 함수
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
    if (formData.get('channel_id') === '') {
        formData.delete('channel_id');
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
                document.getElementById('results').innerHTML = '<div class="col-12"><div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>검색 조건에 맞는 결과가 없습니다.</div></div>';
                return;
            }
            
            // 첫 페이지 렌더링
            renderResults();
        } else {
            // 오류 표시
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
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = videoCard;
        resultsContainer.appendChild(tempDiv.firstElementChild);
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
                </p>
                <div class="stats">
                    <span>
                        <i class="fas fa-eye me-1"></i>
                        ${viewCount}
                    </span>
                    <span>
                        <i class="fas fa-thumbs-up me-1"></i>
                        ${likeCount}
                    </span>
                    <span>
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
// 숫자 포맷팅 함수 (예: 1000 -> 1K, 1000000 -> 1M)
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    }
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}
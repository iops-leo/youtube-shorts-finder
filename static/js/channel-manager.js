// 채널 관리 JS
// 전역 변수 및 상수
const CHANNEL_CATEGORIES_KEY = 'youtubeShortChannelCategories';
let channelCategories = []; // 카테고리 목록 저장
let modalSelectedChannels = []; // 모달에서 선택된 채널 임시 저장

// DOM 요소 참조
const categoriesContainer = document.getElementById('categories-container');
const noCategoriesMessage = document.getElementById('no-categories-message');
const categoryForm = document.getElementById('categoryForm');
const categoryNameInput = document.getElementById('category_name');
const categoryDescInput = document.getElementById('category_description');
const channelCategorySelect = document.getElementById('channel_category_select');
const channelSearchModal = document.getElementById('channel_search_modal');
const channelSearchResultsModal = document.getElementById('channelSearchResultsModal');
const selectedChannelsModal = document.getElementById('selectedChannelsModal');
const saveChannelsBtn = document.getElementById('saveChannelsBtn');
const modalCategoryId = document.getElementById('modal_category_id');

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    // 메뉴 이벤트 리스너 설정
    setupNavigationListeners();
    
    // 카테고리 데이터 로드
    loadCategories();
    
    // 채널 카테고리 목록 업데이트
    updateChannelCategoryDropdown();

    enhanceChannelCategorySelection();
    
    // 카테고리 폼 이벤트 설정
    if (categoryForm) {
        categoryForm.addEventListener('submit', function(e) {
            e.preventDefault();
            addCategory();
        });
    }
    
    // 채널 카테고리 선택 변경 이벤트
    if (channelCategorySelect) {
        channelCategorySelect.addEventListener('change', function() {
            loadChannelsFromCategory(this.value);
        });
    }
    
    // 모달 채널 검색 이벤트
    if (channelSearchModal) {
        channelSearchModal.addEventListener('input', function() {
            searchChannelForModal(this.value);
        });
    }
    
    // 채널 저장 버튼 이벤트
    if (saveChannelsBtn) {
        saveChannelsBtn.addEventListener('click', function() {
            saveChannelsToCategory();
        });
    }
    
    // 모달이 닫힐 때 초기화
    const addChannelModal = document.getElementById('addChannelModal');
    if (addChannelModal) {
        addChannelModal.addEventListener('hidden.bs.modal', function() {
            resetChannelModal();
        });
    }
});

// 메뉴 이벤트 리스너 설정
function setupNavigationListeners() {
    // 메뉴 항목 클릭 처리
    document.querySelectorAll('.nav-link').forEach(navLink => {
        navLink.addEventListener('click', function(e) {
            e.preventDefault();
            
            // 모든 메뉴 비활성화
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });
            
            // 클릭된 메뉴 활성화
            this.classList.add('active');
            
            // 해당 페이지 표시
            const targetId = this.getAttribute('href').substring(1);
            document.querySelectorAll('.page-content').forEach(page => {
                page.style.display = 'none';
            });
            document.getElementById(targetId).style.display = 'block';
        });
    });
}

// 카테고리 관련 함수
// 카테고리 로드
function loadCategories() {
    try {
        const savedCategories = localStorage.getItem(CHANNEL_CATEGORIES_KEY);
        if (savedCategories) {
            channelCategories = JSON.parse(savedCategories);
            renderCategories();
        }
    } catch (error) {
        console.error('카테고리 로드 중 오류:', error);
        channelCategories = [];
    }
}

// 카테고리 저장
function saveCategories() {
    try {
        localStorage.setItem(CHANNEL_CATEGORIES_KEY, JSON.stringify(channelCategories));
        console.log('카테고리 저장 완료');
    } catch (error) {
        console.error('카테고리 저장 중 오류:', error);
        showToast('카테고리 저장 중 오류가 발생했습니다.', 'danger');
    }
}

// 새 카테고리 추가
function addCategory() {
    const name = categoryNameInput.value.trim();
    const description = categoryDescInput.value.trim();
    
    if (!name) {
        showToast('카테고리 이름을 입력해주세요.', 'warning');
        return;
    }
    
    // 중복 체크
    if (channelCategories.some(cat => cat.name === name)) {
        showToast('이미 존재하는 카테고리 이름입니다.', 'warning');
        return;
    }
    
    // 새 카테고리 객체 생성
    const newCategory = {
        id: Date.now().toString(), // 타임스탬프를 ID로 사용
        name: name,
        description: description,
        channels: [],
        createdAt: new Date().toISOString()
    };
    
    // 카테고리 목록에 추가
    channelCategories.push(newCategory);
    
    // 저장 및 UI 업데이트
    saveCategories();
    renderCategories();
    updateChannelCategoryDropdown();
    
    // 폼 초기화
    categoryNameInput.value = '';
    categoryDescInput.value = '';
    
    showToast(`'${name}' 카테고리가 추가되었습니다.`, 'success');
}

// 카테고리 삭제
function deleteCategory(categoryId) {
    // 삭제 확인
    const category = channelCategories.find(cat => cat.id === categoryId);
    if (!category) return;
    
    if (!confirm(`'${category.name}' 카테고리를 삭제하시겠습니까? 이 카테고리에 포함된 모든 채널 정보가 삭제됩니다.`)) {
        return;
    }
    
    // 카테고리 삭제
    channelCategories = channelCategories.filter(cat => cat.id !== categoryId);
    
    // 저장 및 UI 업데이트
    saveCategories();
    renderCategories();
    updateChannelCategoryDropdown();
    
    showToast(`'${category.name}' 카테고리가 삭제되었습니다.`, 'info');
}

// 카테고리 UI 렌더링
function renderCategories() {
    // 카테고리 컨테이너가 없으면 종료
    if (!categoriesContainer) return;
    
    // 카테고리가 없는 경우 메시지 표시
    if (channelCategories.length === 0) {
        if (noCategoriesMessage) noCategoriesMessage.style.display = 'block';
        categoriesContainer.innerHTML = '';
        return;
    }
    
    // 카테고리가 있는 경우 메시지 숨김
    if (noCategoriesMessage) noCategoriesMessage.style.display = 'none';
    
    // 카테고리 목록 렌더링
    let html = '';
    
    channelCategories.forEach(category => {
        const channelCount = category.channels.length;
        const channelText = channelCount > 0 
            ? `${channelCount}개 채널` 
            : '채널 없음';
        const createdDate = new Date(category.createdAt).toLocaleDateString();
        
        html += `
            <div class="category-card mb-4" data-category-id="${category.id}">
                <div class="card">
                    <div class="card-header bg-light d-flex justify-content-between align-items-center">
                        <h5 class="mb-0">
                            <i class="fas fa-folder me-2"></i>${category.name}
                        </h5>
                        <div>
                            <button class="btn btn-sm btn-success btn-add-channel" data-category-id="${category.id}">
                                <i class="fas fa-user-plus me-1"></i>채널 추가
                            </button>
                            <button class="btn btn-sm btn-danger btn-delete-category" data-category-id="${category.id}">
                                <i class="fas fa-trash-alt me-1"></i>삭제
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="text-muted mb-3">
                            <small><i class="fas fa-info-circle me-1"></i>${category.description || '설명 없음'}</small>
                        </p>
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="badge bg-info">${channelText}</span>
                            <small class="text-muted">생성일: ${createdDate}</small>
                        </div>
                        <div class="channels-container" id="channels-${category.id}">
                            ${renderChannelsHTML(category.channels)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    
    categoriesContainer.innerHTML = html;
    
    // 이벤트 리스너 추가
    attachCategoryEventListeners();
}

// 채널 목록 HTML 생성
function renderChannelsHTML(channels) {
    if (channels.length === 0) {
        return `
            <div class="text-center py-3 text-muted">
                <small>등록된 채널이 없습니다. '채널 추가' 버튼을 클릭하여 채널을 추가하세요.</small>
            </div>
        `;
    }
    
    let html = '<div class="row">';
    
    channels.forEach(channel => {
        // 기본 이미지 URL 설정 (썸네일이 없을 경우)
        const thumbnailUrl = channel.thumbnail || 'https://via.placeholder.com/40';
        
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="channel-card d-flex align-items-center p-2 border rounded">
                    <img src="${thumbnailUrl}" class="rounded-circle me-2" style="width: 40px; height: 40px;" alt="${channel.title}" onerror="this.src='https://via.placeholder.com/40'">
                    <div class="flex-grow-1 overflow-hidden">
                        <h6 class="mb-0 text-truncate" title="${channel.title}">${channel.title}</h6>
                        <small class="text-muted d-block text-truncate" title="${channel.description || '설명 없음'}">${channel.description || '설명 없음'}</small>
                    </div>
                    <button class="btn btn-sm btn-outline-danger btn-remove-channel" data-channel-id="${channel.id}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

// 카테고리 이벤트 리스너 추가
function attachCategoryEventListeners() {
    // 카테고리 삭제 버튼
    document.querySelectorAll('.btn-delete-category').forEach(btn => {
        btn.addEventListener('click', function() {
            const categoryId = this.dataset.categoryId;
            deleteCategory(categoryId);
        });
    });
    
    // 채널 추가 버튼
    document.querySelectorAll('.btn-add-channel').forEach(btn => {
        btn.addEventListener('click', function() {
            const categoryId = this.dataset.categoryId;
            openAddChannelModal(categoryId);
        });
    });
    
    // 채널 삭제 버튼
    document.querySelectorAll('.btn-remove-channel').forEach(btn => {
        btn.addEventListener('click', function() {
            const channelId = this.dataset.channelId;
            const categoryCard = this.closest('.category-card');
            const categoryId = categoryCard.dataset.categoryId;
            
            removeChannelFromCategory(categoryId, channelId);
        });
    });
}

// 채널 관련 함수
// 채널 카테고리 드롭다운 업데이트
function updateChannelCategoryDropdown() {
    // 드롭다운이 없으면 종료
    if (!channelCategorySelect) return;
    
    // 드롭다운 초기화
    channelCategorySelect.innerHTML = '<option value="">직접 채널 검색</option>';
    
    // 카테고리가 없으면 종료
    if (channelCategories.length === 0) {
        return;
    }
    
    // 카테고리 목록 추가
    channelCategories.forEach(category => {
        const option = document.createElement('option');
        option.value = category.id;
        option.textContent = `${category.name} (${category.channels.length}개 채널)`;
        channelCategorySelect.appendChild(option);
    });
}

// 특정 카테고리의 채널 로드
function loadChannelsFromCategory(categoryId) {
    // 카테고리 ID가 없으면 채널 목록 초기화
    if (!categoryId) {
        selectedChannels = [];
        updateSelectedChannelsUI();
        return;
    }
    
    // 해당 카테고리 찾기
    const category = channelCategories.find(cat => cat.id === categoryId);
    if (!category) {
        console.error('카테고리를 찾을 수 없습니다:', categoryId);
        return;
    }
    
    // 선택된 채널 목록 업데이트
    selectedChannels = [...category.channels];
    updateSelectedChannelsUI();
    
    // 채널 ID 필드 업데이트 (검색 시 사용하기 위함)
    if (channelIdsInput) {
        channelIdsInput.value = selectedChannels.map(ch => ch.id).join(',');
    }
    
    // 카테고리 이름으로 알림 표시
    showToast(`'${category.name}' 카테고리의 채널 ${selectedChannels.length}개를 로드했습니다.`, 'info');
    
    // 채널 카운터 업데이트
    if (channelCounter) {
        channelCounter.textContent = `선택된 채널: ${selectedChannels.length}개`;
    }
}

// 카테고리에서 채널 삭제
function removeChannelFromCategory(categoryId, channelId) {
    // 해당 카테고리 찾기
    const categoryIndex = channelCategories.findIndex(cat => cat.id === categoryId);
    if (categoryIndex === -1) return;
    
    const category = channelCategories[categoryIndex];
    
    // 삭제 확인
    const channel = category.channels.find(ch => ch.id === channelId);
    if (!channel) return;
    
    if (!confirm(`'${category.name}' 카테고리에서 '${channel.title}' 채널을 삭제하시겠습니까?`)) {
        return;
    }
    
    // 채널 삭제
    channelCategories[categoryIndex].channels = category.channels.filter(ch => ch.id !== channelId);
    
    // 저장 및 UI 업데이트
    saveCategories();
    renderCategories();
    updateChannelCategoryDropdown();
    
    // 현재 검색 폼에 해당 카테고리가 선택되어 있다면 채널 목록 업데이트
    if (channelCategorySelect && channelCategorySelect.value === categoryId) {
        loadChannelsFromCategory(categoryId);
    }
    
    showToast(`채널이 삭제되었습니다.`, 'info');
}

function enhanceChannelCategorySelection() {
    if (!channelCategorySelect) return;
    
    // 드롭다운에 설명 추가
    const helpText = document.createElement('div');
    helpText.className = 'form-text text-muted mt-1';
    helpText.innerHTML = '<small>카테고리를 선택하면 해당 카테고리의 채널들이 자동으로 로드됩니다.</small>';
    
    // 부모 요소에 추가
    const parentElement = channelCategorySelect.parentElement;
    if (parentElement && !parentElement.querySelector('.form-text')) {
        parentElement.appendChild(helpText);
    }
    
    // "카테고리 관리로 이동" 버튼 추가
    const manageBtn = document.createElement('button');
    manageBtn.type = 'button';
    manageBtn.className = 'btn btn-sm btn-outline-primary mt-1';
    manageBtn.innerHTML = '<i class="fas fa-cog me-1"></i>카테고리 관리';
    manageBtn.addEventListener('click', function() {
        // 채널 관리 페이지로 이동
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.getElementById('nav-channels').classList.add('active');
        
        document.querySelectorAll('.page-content').forEach(page => {
            page.style.display = 'none';
        });
        document.getElementById('page-channels').style.display = 'block';
    });
    
    // 버튼을 드롭다운 아래에 추가
    if (parentElement && !parentElement.querySelector('.btn-outline-primary')) {
        parentElement.appendChild(manageBtn);
    }
}

// 채널 추가 모달 관련 함수
// 채널 추가 모달 열기
function openAddChannelModal(categoryId) {
    // 해당 카테고리 찾기
    const category = channelCategories.find(cat => cat.id === categoryId);
    if (!category) return;
    
    // 모달 초기화
    modalCategoryId.value = categoryId;
    
    // 모달 제목 설정
    const modalTitle = document.getElementById('addChannelModalLabel');
    if (modalTitle) {
        modalTitle.innerHTML = `<i class="fas fa-user-plus me-2"></i>'${category.name}' 카테고리에 채널 추가`;
    }
    
    // 저장된 채널 로드
    modalSelectedChannels = [];
    updateModalSelectedChannelsUI();
    
    // 모달 표시
    const modal = new bootstrap.Modal(document.getElementById('addChannelModal'));
    modal.show();
}

// 모달 초기화
function resetChannelModal() {
    if (channelSearchModal) channelSearchModal.value = '';
    if (channelSearchResultsModal) channelSearchResultsModal.style.display = 'none';
    modalSelectedChannels = [];
    updateModalSelectedChannelsUI();
}

// 채널 검색 (모달용)
const searchChannelForModal = debounce(function(query) {
    // 입력된 검색어 정리
    query = query.trim();
    
    // 검색창이 비어있으면 결과 숨김
    if (!query) {
        channelSearchResultsModal.style.display = 'none';
        return;
    }
    
    // 최소 2글자 이상 입력 필요
    if (query.length < 2) {
        channelSearchResultsModal.innerHTML = '<div class="p-3 text-center">최소 2글자 이상 입력하세요.</div>';
        channelSearchResultsModal.style.display = 'block';
        return;
    }
    
    // 로딩 표시
    channelSearchResultsModal.innerHTML = '<div class="p-3 text-center"><i class="fas fa-spinner fa-spin me-2"></i>검색 중...</div>';
    channelSearchResultsModal.style.display = 'block';
    
    fetch(`/channel-search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' && data.channels.length > 0) {
                channelSearchResultsModal.innerHTML = '';
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
                    const isAlreadyAdded = modalSelectedChannels.some(ch => ch.id === channel.id);
                    if (isAlreadyAdded) {
                        channelItem.style.opacity = '0.7';
                        channelItem.title = '이미 추가된 채널입니다';
                    } else {
                        channelItem.addEventListener('click', () => {
                            addChannelToModal(channel);
                        });
                    }
                    
                    channelSearchResultsModal.appendChild(channelItem);
                });
                channelSearchResultsModal.style.display = 'block';
            } else {
                channelSearchResultsModal.innerHTML = '<div class="p-3 text-center">채널을 찾을 수 없습니다.</div>';
                channelSearchResultsModal.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('채널 검색 오류:', error);
            channelSearchResultsModal.innerHTML = '<div class="p-3 text-center">오류가 발생했습니다.</div>';
            channelSearchResultsModal.style.display = 'block';
        });
}, 300);

// 모달에 채널 추가
function addChannelToModal(channel) {
    // 이미 추가된 채널인지 확인
    const isAlreadyAdded = modalSelectedChannels.some(ch => ch.id === channel.id);
    if (isAlreadyAdded) {
        showToast('이미 추가된 채널입니다.', 'warning');
        return;
    }
    
    // 모달 채널 목록에 추가
    modalSelectedChannels.push(channel);
    
    // UI 업데이트
    updateModalSelectedChannelsUI();
    
    // 검색 결과 숨기기
    channelSearchResultsModal.style.display = 'none';
    channelSearchModal.value = '';
}

// 모달 선택된 채널 UI 업데이트
function updateModalSelectedChannelsUI() {
    // 컨테이너가 없으면 종료
    if (!selectedChannelsModal) return;
    
    // 컨테이너 초기화
    selectedChannelsModal.innerHTML = '';
    
    // 선택된 채널이 없는 경우
    if (modalSelectedChannels.length === 0) {
        selectedChannelsModal.innerHTML = `
            <div class="text-center py-3 text-muted">
                <small>채널을 검색하여 추가하세요</small>
            </div>
        `;
        return;
    }
    
    // 채널 목록 생성
    modalSelectedChannels.forEach(channel => {
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
            const channelId = this.dataset.channelId;
            modalSelectedChannels = modalSelectedChannels.filter(ch => ch.id !== channelId);
            updateModalSelectedChannelsUI();
        });
        
        selectedChannelsModal.appendChild(channelItem);
    });
}

// 채널 카테고리에 저장
function saveChannelsToCategory() {
    const categoryId = modalCategoryId.value;
    if (!categoryId) {
        showToast('카테고리 ID가 유효하지 않습니다.', 'danger');
        return;
    }
    
    // 저장할 채널이 없는 경우
    if (modalSelectedChannels.length === 0) {
        showToast('추가할 채널을 선택해주세요.', 'warning');
        return;
    }
    
    // 카테고리 찾기
    const categoryIndex = channelCategories.findIndex(cat => cat.id === categoryId);
    if (categoryIndex === -1) {
        showToast('유효하지 않은 카테고리입니다.', 'danger');
        return;
    }
    
    // 중복 확인 및 추가
    const category = channelCategories[categoryIndex];
    const existingChannelIds = category.channels.map(ch => ch.id);
    
    // 새로 추가되는 채널 수 계산
    let newChannelCount = 0;
    
    modalSelectedChannels.forEach(channel => {
        if (!existingChannelIds.includes(channel.id)) {
            channelCategories[categoryIndex].channels.push(channel);
            newChannelCount++;
        }
    });
    
    // 변경사항 저장 및 UI 업데이트
    saveCategories();
    renderCategories();
    updateChannelCategoryDropdown();
    
    // 모달 닫기
    const modal = bootstrap.Modal.getInstance(document.getElementById('addChannelModal'));
    modal.hide();
    
    // 알림 표시
    if (newChannelCount > 0) {
        showToast(`${newChannelCount}개의 채널이 '${category.name}' 카테고리에 추가되었습니다.`, 'success');
    } else {
        showToast('추가된 새 채널이 없습니다. 모든 채널이 이미 카테고리에 포함되어 있습니다.', 'info');
    }
}

// 토스트 알림 표시 함수
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

// 디바운스 함수 (main.js에서 가져온 것)
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function exportChannelCategories() {
    try {
        // 모든 데이터 가져오기
        const allData = {
            channelCategories: channelCategories,
            exportDate: new Date().toISOString(),
            appVersion: '1.0.0'
        };
        
        // JSON 문자열로 변환
        const jsonString = JSON.stringify(allData, null, 2);
        
        // Blob 객체 생성
        const blob = new Blob([jsonString], { type: 'application/json' });
        
        // 다운로드 링크 생성
        const downloadLink = document.createElement('a');
        downloadLink.href = URL.createObjectURL(blob);
        downloadLink.download = `youtube-shorts-channels-${new Date().toISOString().slice(0, 10)}.json`;
        
        // 링크 클릭 (다운로드 시작)
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
        
        showToast('채널 카테고리 데이터가 성공적으로 내보내기 되었습니다!', 'success');
    } catch (error) {
        console.error('데이터 내보내기 오류:', error);
        showToast('데이터 내보내기 중 오류가 발생했습니다.', 'danger');
    }
}

function importChannelCategories(file) {
    const reader = new FileReader();
    
    reader.onload = function(event) {
        try {
            const importedData = JSON.parse(event.target.result);
            
            // 데이터 유효성 검증
            if (!importedData.channelCategories || !Array.isArray(importedData.channelCategories)) {
                throw new Error('유효하지 않은 데이터 형식입니다.');
            }
            
            if (confirm('기존 채널 카테고리를 모두 대체하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
                // 데이터 적용
                channelCategories = importedData.channelCategories;
                saveCategories();
                
                // UI 업데이트
                renderCategories();
                updateChannelCategoryDropdown();
                
                showToast('채널 카테고리 데이터가 성공적으로 가져오기 되었습니다!', 'success');
            }
        } catch (error) {
            console.error('데이터 가져오기 오류:', error);
            showToast('데이터 가져오기 중 오류가 발생했습니다. 유효한 JSON 파일인지 확인하세요.', 'danger');
        }
    };
    
    reader.onerror = function() {
        showToast('파일을 읽는 중 오류가 발생했습니다.', 'danger');
    };
    
    reader.readAsText(file);
}

function mergeChannelCategories(file) {
    const reader = new FileReader();
    
    reader.onload = function(event) {
        try {
            const importedData = JSON.parse(event.target.result);
            
            // 데이터 유효성 검증
            if (!importedData.channelCategories || !Array.isArray(importedData.channelCategories)) {
                throw new Error('유효하지 않은 데이터 형식입니다.');
            }
            
            // 병합 실행
            let newCategoriesCount = 0;
            let updatedCategoriesCount = 0;
            
            importedData.channelCategories.forEach(importedCategory => {
                // 기존에 같은 ID의 카테고리가 있는지 확인
                const existingCategoryIndex = channelCategories.findIndex(cat => cat.id === importedCategory.id);
                
                if (existingCategoryIndex === -1) {
                    // 새 카테고리 추가
                    channelCategories.push(importedCategory);
                    newCategoriesCount++;
                } else {
                    // 기존 카테고리에 채널 추가 (중복 제거)
                    const existingCategory = channelCategories[existingCategoryIndex];
                    const existingChannelIds = existingCategory.channels.map(ch => ch.id);
                    
                    let newChannelsCount = 0;
                    importedCategory.channels.forEach(importedChannel => {
                        if (!existingChannelIds.includes(importedChannel.id)) {
                            existingCategory.channels.push(importedChannel);
                            newChannelsCount++;
                        }
                    });
                    
                    if (newChannelsCount > 0) {
                        updatedCategoriesCount++;
                    }
                }
            });
            
            // 변경사항 저장
            saveCategories();
            
            // UI 업데이트
            renderCategories();
            updateChannelCategoryDropdown();
            
            showToast(`데이터가 병합되었습니다! ${newCategoriesCount}개의 새 카테고리, ${updatedCategoriesCount}개의 카테고리가 업데이트되었습니다.`, 'success');
        } catch (error) {
            console.error('데이터 병합 오류:', error);
            showToast('데이터 병합 중 오류가 발생했습니다.', 'danger');
        }
    };
    
    reader.onerror = function() {
        showToast('파일을 읽는 중 오류가 발생했습니다.', 'danger');
    };
    
    reader.readAsText(file);
}

function handleFileImport(event, mode = 'replace') {
    const file = event.target.files[0];
    if (!file) return;
    
    if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
        showToast('JSON 파일만 가져올 수 있습니다.', 'warning');
        return;
    }
    
    if (mode === 'replace') {
        importChannelCategories(file);
    } else {
        mergeChannelCategories(file);
    }
    
    // 파일 입력 초기화 (같은 파일 다시 선택 가능하도록)
    event.target.value = '';
}

// UI에 내보내기/가져오기 버튼 추가
function addExportImportButtons() {
    // 카테고리 헤더 찾기
    const categoryHeader = document.querySelector('.card-header h5');
    if (!categoryHeader) return;
    
    // 컨테이너 찾기
    const headerContainer = categoryHeader.closest('.card-header');
    if (!headerContainer) return;
    
    // 이미 버튼이 있는지 확인
    if (headerContainer.querySelector('.data-export-btn')) return;
    
    // 버튼 컨테이너 생성
    const btnContainer = document.createElement('div');
    btnContainer.className = 'd-flex';
    
    // 내보내기 버튼
    const exportBtn = document.createElement('button');
    exportBtn.type = 'button';
    exportBtn.className = 'btn btn-sm btn-outline-primary me-2 data-export-btn';
    exportBtn.innerHTML = '<i class="fas fa-file-export me-1"></i>내보내기';
    exportBtn.addEventListener('click', exportChannelCategories);
    
    // 가져오기 버튼 (드롭다운)
    const importDropdown = document.createElement('div');
    importDropdown.className = 'dropdown';
    importDropdown.innerHTML = `
        <button class="btn btn-sm btn-outline-success dropdown-toggle data-import-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false">
            <i class="fas fa-file-import me-1"></i>가져오기
        </button>
        <ul class="dropdown-menu">
            <li>
                <label class="dropdown-item" style="cursor: pointer;">
                    <input type="file" id="importFileReplace" accept=".json" style="display: none;">
                    덮어쓰기
                </label>
            </li>
            <li>
                <label class="dropdown-item" style="cursor: pointer;">
                    <input type="file" id="importFileMerge" accept=".json" style="display: none;">
                    병합하기
                </label>
            </li>
            <li><hr class="dropdown-divider"></li>
            <li>
                <div class="dropdown-item">
                    <small class="text-muted">덮어쓰기: 모든 데이터 교체<br>병합하기: 새 데이터 추가</small>
                </div>
            </li>
        </ul>
    `;
    
    // 버튼 추가
    btnContainer.appendChild(exportBtn);
    btnContainer.appendChild(importDropdown);
    
    // 기존 컨테이너에 버튼 추가
    headerContainer.appendChild(btnContainer);
    
    // 파일 입력 이벤트 리스너 추가
    document.getElementById('importFileReplace').addEventListener('change', function(e) {
        handleFileImport(e, 'replace');
    });
    
    document.getElementById('importFileMerge').addEventListener('change', function(e) {
        handleFileImport(e, 'merge');
    });
}

// DOM 로드 시 내보내기/가져오기 버튼 추가
document.addEventListener('DOMContentLoaded', function() {
    // 카테고리 렌더링 후 내보내기/가져오기 버튼 추가
    const originalRenderCategories = renderCategories;
    renderCategories = function() {
        originalRenderCategories();
        addExportImportButtons();
    };
});

// QR 코드 생성 및 공유 기능 추가
function shareCategories() {
    try {
        // 모든 데이터 가져오기
        const allData = {
            channelCategories: channelCategories,
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
    } catch (error) {
        console.error('데이터 공유 오류:', error);
        showToast('데이터 공유 중 오류가 발생했습니다.', 'danger');
    }
}
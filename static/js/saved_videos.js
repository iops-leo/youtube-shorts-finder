// ===================== 저장된 영상 관리 JavaScript =====================

let savedVideos = [];
let currentPage = 1;
let totalPages = 1;
let currentSort = 'saved_at_desc';
let editingVideoId = null;
let deletingVideoId = null;

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

// DOM 로드 완료 시 실행
document.addEventListener('DOMContentLoaded', function() {
    loadSavedVideos();
});

/**
 * 저장된 영상 목록 로드
 */
function loadSavedVideos(page = 1, sort = 'saved_at_desc') {
    const loadingSpinner = document.getElementById('loadingSpinner');
    const savedVideosList = document.getElementById('savedVideosList');
    const emptyState = document.getElementById('emptyState');
    const paginationContainer = document.getElementById('paginationContainer');
    
    // 로딩 상태 표시
    loadingSpinner.style.display = 'block';
    savedVideosList.style.display = 'none';
    emptyState.style.display = 'none';
    paginationContainer.style.display = 'none';
    
    currentPage = page;
    currentSort = sort;
    
    fetch(`/api/saved-videos?page=${page}&per_page=20`)
        .then(response => response.json())
        .then(data => {
            loadingSpinner.style.display = 'none';
            
            if (data.success) {
                savedVideos = data.videos;
                totalPages = data.pagination.pages;
                
                if (savedVideos.length === 0) {
                    // 빈 상태 표시
                    emptyState.style.display = 'block';
                } else {
                    // 영상 목록 표시
                    sortVideosLocally(sort);
                    renderSavedVideos();
                    renderPagination(data.pagination);
                    savedVideosList.style.display = 'flex';
                    paginationContainer.style.display = 'block';
                }
                
                // 총 개수 업데이트
                document.getElementById('totalCount').textContent = `${data.pagination.total}개`;
            } else {
                showToast(data.message || '영상 목록을 불러올 수 없습니다.', 'error');
                emptyState.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('저장된 영상 로딩 중 오류:', error);
            loadingSpinner.style.display = 'none';
            emptyState.style.display = 'block';
            showToast('영상 목록을 불러오는 중 오류가 발생했습니다.', 'error');
        });
}

/**
 * 클라이언트 측에서 영상 정렬
 */
function sortVideosLocally(sortBy) {
    switch (sortBy) {
        case 'saved_at_desc':
            savedVideos.sort((a, b) => new Date(b.saved_at) - new Date(a.saved_at));
            break;
        case 'saved_at_asc':
            savedVideos.sort((a, b) => new Date(a.saved_at) - new Date(b.saved_at));
            break;
        case 'published_desc':
            savedVideos.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
            break;
        case 'view_count_desc':
            savedVideos.sort((a, b) => b.view_count - a.view_count);
            break;
        case 'channel_title':
            savedVideos.sort((a, b) => a.channel_title.localeCompare(b.channel_title));
            break;
    }
}

/**
 * 정렬 변경
 */
function sortVideos(sortBy) {
    sortVideosLocally(sortBy);
    renderSavedVideos();
    currentSort = sortBy;
}

/**
 * 저장된 영상 목록 렌더링
 */
function renderSavedVideos() {
    const container = document.getElementById('savedVideosList');
    container.innerHTML = '';
    
    savedVideos.forEach(video => {
        const videoCard = createSavedVideoCard(video);
        container.appendChild(videoCard);
    });
}

/**
 * 저장된 영상 카드 생성
 */
function createSavedVideoCard(video) {
    const col = document.createElement('div');
    col.className = 'col-lg-4 col-md-6 col-12';
    
    // 날짜 포맷팅
    const savedDate = new Date(video.saved_at).toLocaleDateString('ko-KR');
    const publishedDate = video.published_at ? 
        new Date(video.published_at).toLocaleDateString('ko-KR') : '정보 없음';
    
    // 조회수 포맷팅
    const viewCount = formatNumber(video.view_count);
    
    // 메모 표시
    const hasNotes = video.notes && video.notes.trim().length > 0;
    const notesPreview = hasNotes ? 
        (video.notes.length > 50 ? video.notes.substring(0, 50) + '...' : video.notes) : 
        '메모 없음';
    
    col.innerHTML = `
        <div class="card h-100">
            <a href="${video.video_url}" target="_blank">
                <img src="${video.thumbnail_url}" class="card-img-top" alt="${video.video_title}" 
                     style="height: 200px; object-fit: cover;">
            </a>
            <div class="card-body">
                <h6 class="card-title" title="${video.video_title}">
                    ${video.video_title.length > 60 ? 
                        video.video_title.substring(0, 60) + '...' : 
                        video.video_title}
                </h6>
                <p class="card-text small text-muted">
                    <a href="https://www.youtube.com/channel/${video.channel_id}" target="_blank" class="text-decoration-none">
                        <i class="fas fa-user-circle me-1"></i>${video.channel_title}
                    </a>
                </p>
                
                <!-- 메모 표시 -->
                <div class="mb-2">
                    <small class="text-muted">
                        <i class="fas fa-sticky-note me-1 ${hasNotes ? 'text-warning' : ''}"></i>
                        <span class="${hasNotes ? 'text-dark' : 'text-muted'}">${notesPreview}</span>
                    </small>
                </div>
                
                <!-- 통계 정보 -->
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-muted">
                        <i class="fas fa-eye me-1"></i>${viewCount}
                    </small>
                    <small class="text-muted">
                        <i class="fas fa-clock me-1"></i>${video.duration || '정보없음'}초
                    </small>
                </div>
                
                <!-- 날짜 정보 -->
                <div class="mb-2">
                    <small class="text-muted d-block">
                        <i class="fas fa-upload me-1"></i>업로드: ${publishedDate}
                    </small>
                    <small class="text-success d-block">
                        <i class="fas fa-bookmark me-1"></i>저장: ${savedDate}
                    </small>
                </div>
            </div>
            <div class="card-footer">
                <div class="d-grid gap-1">
                    <a href="${video.video_url}" target="_blank" class="btn btn-sm btn-primary">
                        <i class="fab fa-youtube me-1"></i>영상 보기
                    </a>
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-outline-warning" 
                                onclick="openNoteModal(${video.id}, '${video.video_title.replace(/'/g, "\\'")}', '${video.notes ? video.notes.replace(/'/g, "\\'") : ''}')"
                                title="메모 편집">
                            <i class="fas fa-sticky-note me-1"></i>메모
                        </button>
                        <button class="btn btn-sm btn-outline-danger" 
                                onclick="openDeleteModal(${video.id}, '${video.video_title.replace(/'/g, "\\'")}')"
                                title="영상 삭제">
                            <i class="fas fa-trash me-1"></i>삭제
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return col;
}

/**
 * 페이지네이션 렌더링
 */
function renderPagination(pagination) {
    const paginationElement = document.getElementById('pagination');
    paginationElement.innerHTML = '';
    
    if (pagination.pages <= 1) {
        document.getElementById('paginationContainer').style.display = 'none';
        return;
    }
    
    // 이전 페이지 버튼
    if (pagination.has_prev) {
        const prevLi = document.createElement('li');
        prevLi.className = 'page-item';
        prevLi.innerHTML = `<a class="page-link" href="#" onclick="loadSavedVideos(${pagination.page - 1}, '${currentSort}')">이전</a>`;
        paginationElement.appendChild(prevLi);
    }
    
    // 페이지 번호들
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.pages, pagination.page + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        const li = document.createElement('li');
        li.className = `page-item ${i === pagination.page ? 'active' : ''}`;
        li.innerHTML = `<a class="page-link" href="#" onclick="loadSavedVideos(${i}, '${currentSort}')">${i}</a>`;
        paginationElement.appendChild(li);
    }
    
    // 다음 페이지 버튼
    if (pagination.has_next) {
        const nextLi = document.createElement('li');
        nextLi.className = 'page-item';
        nextLi.innerHTML = `<a class="page-link" href="#" onclick="loadSavedVideos(${pagination.page + 1}, '${currentSort}')">다음</a>`;
        paginationElement.appendChild(nextLi);
    }
}

/**
 * 메모 편집 모달 열기
 */
function openNoteModal(videoId, videoTitle, currentNotes) {
    editingVideoId = videoId;
    document.getElementById('videoTitle').value = videoTitle;
    document.getElementById('videoNotes').value = currentNotes || '';
    
    safeShowModal('noteModal');
}

/**
 * 영상 메모 저장
 */
function saveVideoNotes() {
    if (!editingVideoId) return;
    
    const notes = document.getElementById('videoNotes').value;
    
    fetch(`/api/saved-videos/${editingVideoId}/notes`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ notes: notes })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('메모가 저장되었습니다.', 'success');
            
            // 로컬 데이터 업데이트
            const videoIndex = savedVideos.findIndex(v => v.id === editingVideoId);
            if (videoIndex !== -1) {
                savedVideos[videoIndex].notes = notes;
                renderSavedVideos();
            }
            
            // 모달 닫기
            safeCloseModal('noteModal');
        } else {
            showToast(data.message || '메모 저장에 실패했습니다.', 'error');
        }
    })
    .catch(error => {
        console.error('메모 저장 중 오류:', error);
        showToast('메모 저장 중 오류가 발생했습니다.', 'error');
    });
}

/**
 * 삭제 확인 모달 열기
 */
function openDeleteModal(videoId, videoTitle) {
    deletingVideoId = videoId;
    safeShowModal('deleteModal');
}

/**
 * 영상 삭제 확인
 */
function confirmDeleteVideo() {
    if (!deletingVideoId) return;
    
    fetch(`/api/saved-videos/${deletingVideoId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('영상이 삭제되었습니다.', 'success');
            
            // 로컬 데이터에서 제거
            savedVideos = savedVideos.filter(v => v.id !== deletingVideoId);
            
            // UI 업데이트
            if (savedVideos.length === 0) {
                document.getElementById('savedVideosList').style.display = 'none';
                document.getElementById('paginationContainer').style.display = 'none';
                document.getElementById('emptyState').style.display = 'block';
            } else {
                renderSavedVideos();
            }
            
            // 총 개수 업데이트
            const currentCount = parseInt(document.getElementById('totalCount').textContent);
            document.getElementById('totalCount').textContent = `${currentCount - 1}개`;
            
            // 모달 닫기
            safeCloseModal('deleteModal');
        } else {
            showToast(data.message || '영상 삭제에 실패했습니다.', 'error');
        }
    })
    .catch(error => {
        console.error('영상 삭제 중 오류:', error);
        showToast('영상 삭제 중 오류가 발생했습니다.', 'error');
    });
}

/**
 * 숫자 포맷팅 함수
 */
function formatNumber(num) {
    if (num >= 1000000) {
        return `${(num / 1000000).toFixed(1)}M`;
    }
    if (num >= 1000) {
        return `${(num / 1000).toFixed(1)}K`;
    }
    return num || 0;
}

/**
 * 토스트 메시지 표시
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
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);
    
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: type === 'error' ? 5000 : 3000
    });
    bsToast.show();
    
    // 토스트가 숨겨진 후 컨테이너 제거
    toast.addEventListener('hidden.bs.toast', () => {
        toastContainer.remove();
    });
}
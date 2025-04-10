// script-extractor.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM 요소 참조
    const scriptForm = document.getElementById('scriptForm');
    const scriptLoader = document.getElementById('scriptLoader');
    const scriptsResultHeader = document.getElementById('scriptsResultHeader');
    const scriptsResults = document.getElementById('scriptsResults');
    const scriptCount = document.getElementById('scriptCount');
    const copyAllScripts = document.getElementById('copyAllScripts');
    const downloadAllScripts = document.getElementById('downloadAllScripts');
    const modalCopyBtn = document.getElementById('modalCopyBtn');
    const modalDownloadBtn = document.getElementById('modalDownloadBtn');
    
    // 모든 추출된 스크립트 저장 배열
    let allScripts = [];
    
    // 폼 제출 이벤트 처리
    if (scriptForm) {
        scriptForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 입력값 가져오기
            const channelUrl = document.getElementById('channel_url').value.trim();
            const videoCount = parseInt(document.getElementById('video_count').value);
            const autoTranslate = document.getElementById('auto_translate').checked;
            
            // 입력 유효성 검사
            if (!channelUrl) {
                showToast('채널 URL을 입력해주세요.', 'warning');
                return;
            }
            
            if (isNaN(videoCount) || videoCount < 1 || videoCount > 50) {
                showToast('가져올 영상 수는 1~50 사이여야 합니다.', 'warning');
                return;
            }
            
            // 결과 초기화
            allScripts = [];
            scriptsResults.innerHTML = '';
            scriptsResultHeader.style.display = 'none';
            
            // 로딩 표시
            scriptLoader.style.display = 'block';
            
            // API 요청
            fetchScripts(channelUrl, videoCount, autoTranslate);
        });
    }
    
    // 스크립트 가져오기 함수
    function fetchScripts(channelUrl, videoCount, autoTranslate) {
        // 폼 데이터 생성
        const formData = new FormData();
        formData.append('channel_url', channelUrl);
        formData.append('video_count', videoCount);
        formData.append('auto_translate', autoTranslate);
        
        // API 호출
        fetch('/api/scripts/extract', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // 로딩 숨기기
            scriptLoader.style.display = 'none';
            
            if (data.status === 'success') {
                // 결과 저장
                allScripts = data.scripts;
                
                // 결과 헤더 표시
                scriptsResultHeader.style.display = 'block';
                scriptCount.textContent = allScripts.length;
                
                // 결과가 없는 경우 메시지 표시
                if (allScripts.length === 0) {
                    scriptsResults.innerHTML = `
                        <div class="col-12">
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>자막이 있는 영상을 찾을 수 없습니다.
                                <p class="mt-2 mb-0">
                                    <small>
                                        <i class="fas fa-info-circle me-1"></i>해당 채널의 영상에 자막이 없거나 접근할 수 없습니다.
                                    </small>
                                </p>
                            </div>
                        </div>
                    `;
                    return;
                }
                
                // 결과 렌더링
                renderScriptCards(allScripts);
            } 
            else if (data.status === 'error') {
                scriptsResultHeader.style.display = 'none';
                scriptsResults.innerHTML = `
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
            scriptLoader.style.display = 'none';
            
            // 오류 표시
            scriptsResultHeader.style.display = 'none';
            scriptsResults.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        <h5 class="mb-0"><i class="fas fa-wifi me-2"></i>네트워크 오류가 발생했습니다</h5>
                        <p class="mb-0">${error.message}</p>
                    </div>
                </div>
            `;
        });
    }
    
    // 스크립트 카드 렌더링 함수
    function renderScriptCards(scripts) {
        scriptsResults.innerHTML = '';
        
        scripts.forEach((script, index) => {
            const card = document.createElement('div');
            card.className = 'script-card card h-100';
            
            // 스크립트가 없는 경우
            const scriptText = script.text || '(스크립트가 없습니다)';
            const scriptPreview = scriptText.length > 200 ? 
                scriptText.substring(0, 200) + '...' : scriptText;
            
            // 재생 시간 포맷팅
            const durationStr = formatDuration(script.duration);
            
            // 카드 내용 생성
            card.innerHTML = `
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0" title="${script.title}">${truncateText(script.title, 40)}</h6>
                    <div class="ms-2 text-nowrap">
                        <span class="badge bg-primary">${durationStr}</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="d-flex mb-3">
                        <div class="ratio ratio-16x9 w-100">
                            <img src="${script.thumbnail}" class="card-img-top" alt="${script.title}">
                        </div>
                    </div>
                    <p class="card-text small script-preview" style="height: 100px; overflow-y: auto;">
                        ${scriptPreview}
                    </p>
                </div>
                <div class="card-footer d-flex justify-content-between">
                    <a href="${script.videoUrl}" target="_blank" class="btn btn-sm btn-outline-primary">
                        <i class="fab fa-youtube me-1"></i>영상 보기
                    </a>
                    <div>
                        <button class="btn btn-sm btn-outline-secondary copy-script" 
                                data-index="${index}">
                            <i class="fas fa-copy me-1"></i>복사
                        </button>
                        <button class="btn btn-sm btn-outline-success download-script" 
                                data-index="${index}">
                            <i class="fas fa-download me-1"></i>다운로드
                        </button>
                    </div>
                </div>
            `;
            
            scriptsResults.appendChild(card);
        });
        
        // 복사 버튼 이벤트 추가
        document.querySelectorAll('.copy-script').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.dataset.index);
                copyScript(allScripts[index]);
            });
        });
        
        // 다운로드 버튼 이벤트 추가
        document.querySelectorAll('.download-script').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = parseInt(this.dataset.index);
                downloadScript(allScripts[index]);
            });
        });
    }
    
    // 모든 스크립트 복사 버튼
    if (copyAllScripts) {
        copyAllScripts.addEventListener('click', function() {
            showCombinedScriptsModal();
        });
    }
    
    // 모든 스크립트 다운로드 버튼
    if (downloadAllScripts) {
        downloadAllScripts.addEventListener('click', function() {
            downloadAllScriptsAsText();
        });
    }
    
    // 모달 복사 버튼
    if (modalCopyBtn) {
        modalCopyBtn.addEventListener('click', function() {
            const combinedText = getCombinedScriptsText();
            navigator.clipboard.writeText(combinedText)
                .then(() => {
                    showToast('모든 스크립트가 클립보드에 복사되었습니다.', 'success');
                })
                .catch(err => {
                    console.error('클립보드 복사 오류:', err);
                    showToast('복사 중 오류가 발생했습니다.', 'danger');
                });
        });
    }
    
    // 모달 다운로드 버튼
    if (modalDownloadBtn) {
        modalDownloadBtn.addEventListener('click', function() {
            downloadAllScriptsAsText();
        });
    }
    
    // 통합 스크립트 모달 표시
    function showCombinedScriptsModal() {
        const combinedScriptsContainer = document.getElementById('combinedScriptsContainer');
        const combinedText = getCombinedScriptsText();
        
        combinedScriptsContainer.textContent = combinedText;
        
        // 모달 표시
        const modal = new bootstrap.Modal(document.getElementById('combinedScriptsModal'));
        modal.show();
    }
    
    // 통합 스크립트 텍스트 생성
    function getCombinedScriptsText() {
        if (allScripts.length === 0) return '스크립트가 없습니다.';
        
        return allScripts.map((script, index) => {
            return `[${index + 1}] ${script.title}\n${script.videoUrl}\n\n${script.text || '(스크립트 없음)'}\n\n${'='.repeat(50)}\n\n`;
        }).join('');
    }
    
    // 개별 스크립트 복사
    function copyScript(script) {
        if (!script) return;
        
        const textToCopy = `[${script.title}]\n${script.videoUrl}\n\n${script.text || '(스크립트 없음)'}`;
        
        navigator.clipboard.writeText(textToCopy)
            .then(() => {
                showToast('스크립트가 클립보드에 복사되었습니다.', 'success');
            })
            .catch(err => {
                console.error('클립보드 복사 오류:', err);
                showToast('복사 중 오류가 발생했습니다.', 'danger');
            });
    }
    
    // 개별 스크립트 다운로드
    function downloadScript(script) {
        if (!script) return;
        
        const textToDownload = `[${script.title}]\n${script.videoUrl}\n\n${script.text || '(스크립트 없음)'}`;
        const fileName = `script_${formatFileName(script.title)}.txt`;
        
        downloadTextFile(textToDownload, fileName);
    }
    
    // 모든 스크립트 다운로드
    function downloadAllScriptsAsText() {
        if (allScripts.length === 0) {
            showToast('다운로드할 스크립트가 없습니다.', 'warning');
            return;
        }
        
        const combinedText = getCombinedScriptsText();
        const channelName = allScripts[0].channelTitle || 'youtube_channel';
        const fileName = `scripts_${formatFileName(channelName)}_${new Date().toISOString().split('T')[0]}.txt`;
        
        downloadTextFile(combinedText, fileName);
    }
    
    // 텍스트 파일 다운로드 도우미 함수
    function downloadTextFile(text, fileName) {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast(`파일이 다운로드되었습니다: ${fileName}`, 'success');
    }
    
    // 유틸리티 함수들
    function truncateText(text, maxLength) {
        if (!text) return '';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }
    
    function formatDuration(seconds) {
        if (!seconds) return '00:00';
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    function formatFileName(text) {
        if (!text) return 'script';
        // 파일명에 사용할 수 없는 문자 제거 및 공백을 언더스코어로 변환
        return text.replace(/[\\/:*?"<>|]/g, '').replace(/\s+/g, '_').substring(0, 50);
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
});
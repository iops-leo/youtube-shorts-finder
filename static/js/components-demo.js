/* 공통 데모 상호작용 스크립트 (드롭다운/모달/커맨드 메뉴) */
(function () {
  function openModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = 'block';
    document.body.style.overflow = 'hidden';
  }
  function closeModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = 'none';
    document.body.style.overflow = 'auto';
  }
  function toggleDropdown(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const isActive = el.classList.contains('active');
    document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('active'));
    if (!isActive) el.classList.add('active');
  }
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('active'));
    }
  });
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      openModal('command-modal');
      setTimeout(() => {
        const input = document.getElementById('command-input');
        if (input) input.focus();
      }, 50);
    }
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop').forEach(m => {
        if (m.style.display === 'block') m.style.display = 'none';
        document.body.style.overflow = 'auto';
      });
      document.querySelectorAll('.dropdown').forEach(d => d.classList.remove('active'));
    }
  });

  // Command list keyboard navigation
  document.addEventListener('DOMContentLoaded', () => {
    const list = document.querySelectorAll('.command-item');
    const input = document.getElementById('command-input');
    if (!input || !list.length) return;
    let idx = 0;
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        list[idx].classList.remove('selected');
        idx = (idx + 1) % list.length;
        list[idx].classList.add('selected');
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        list[idx].classList.remove('selected');
        idx = (idx - 1 + list.length) % list.length;
        list[idx].classList.add('selected');
      } else if (e.key === 'Enter') {
        e.preventDefault();
        closeModal('command-modal');
      }
    });
  });

  // Tabs interaction (demo-only)
  document.addEventListener('click', (e) => {
    const tab = e.target.closest('.tab-item');
    if (tab && tab.parentElement.classList.contains('tabs')) {
      const tabs = tab.parentElement.querySelectorAll('.tab-item');
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const panel = tab.parentElement.parentElement.querySelector('.tab-panel');
      if (panel) panel.textContent = `${tab.textContent} 탭이 선택되었습니다.`;
    }
  });

  // Pagination interaction (demo-only)
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.page-btn');
    if (btn && btn.parentElement.classList.contains('pagination')) {
      const container = btn.parentElement;
      const pages = container.querySelectorAll('.page-btn');
      const pagesArray = Array.from(pages);
      const currentIndex = pagesArray.findIndex(p => p.classList.contains('active') || p.getAttribute('aria-current') === 'page');
      const isPrev = btn.textContent.includes('«');
      const isNext = btn.textContent.includes('»');
      let targetIndex = currentIndex;
      if (isPrev) targetIndex = Math.max(1, currentIndex - 1); // index 0은 « 버튼, 1부터 페이지
      else if (isNext) targetIndex = Math.min(pages.length - 2, currentIndex + 1); // 마지막은 » 버튼
      else targetIndex = pagesArray.indexOf(btn);
      pagesArray.forEach(p => { p.classList.remove('active'); p.removeAttribute('aria-current'); });
      pagesArray[targetIndex].classList.add('active');
      pagesArray[targetIndex].setAttribute('aria-current', 'page');
    }
  });

  // Toggle group (demo-only)
  document.addEventListener('click', (e) => {
    const container = e.target.closest('.toggle-group');
    if (container) {
      const btn = e.target.closest('.btn');
      if (!btn) return;
      const buttons = container.querySelectorAll('.btn');
      buttons.forEach(b => b.classList.remove('btn-primary'));
      buttons.forEach(b => b.classList.add('btn-outline'));
      btn.classList.remove('btn-outline');
      btn.classList.add('btn-primary');
    }
  });

  // 공개
  window.ComponentsDemo = { openModal, closeModal, toggleDropdown };
})();




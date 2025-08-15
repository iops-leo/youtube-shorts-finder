/* Theme Manager
   - 주어진 Linear JSON을 받아 CSS Custom Properties로 반영
   - data-theme 전환 및 지속성 관리(localStorage)
   - 프로젝트 전역에서 공통 사용
*/
(function () {
  const STORAGE_KEY = 'app.theme.json';
  const THEME_MODE_KEY = 'app.theme.mode';

  function setCSSVar(name, value) {
    if (value == null) return;
    document.documentElement.style.setProperty(name, String(value));
  }

  function applyActualVariables(vars) {
    if (!vars) return;
    const { layout, borders, typography, colors, animations, easing } = vars;
    [layout, borders, typography, colors, animations, easing].forEach(group => {
      if (!group) return;
      Object.entries(group).forEach(([k, v]) => setCSSVar(k, v));
    });
  }

  function applyComputedColors(computed, mode) {
    if (computed && computed[mode]) {
      const theme = computed[mode];
      if (theme.background?.hex) setCSSVar('--color-background', theme.background.hex);
      if (theme.text?.hex) setCSSVar('--color-text', theme.text.hex);
      if (theme.accent?.hex) setCSSVar('--color-accent', theme.accent.hex);
      if (theme.surface?.header) setCSSVar('--color-surface', theme.surface.header);
      if (theme.border?.subtle) setCSSVar('--color-border', theme.border.subtle);
      return true;
    }
    return false;
  }

  function applyFallbackForMode(mode) {
    if (mode === 'light') {
      setCSSVar('--color-background', '#F7F8F8');
      setCSSVar('--color-text', '#08090A');
      setCSSVar('--color-border', 'rgba(0,0,0,0.08)');
      setCSSVar('--color-surface', 'rgba(255,255,255,0.8)');
    } else {
      setCSSVar('--color-background', '#08090A');
      setCSSVar('--color-text', '#F7F8F8');
      setCSSVar('--color-border', 'rgba(255,255,255,0.08)');
      setCSSVar('--color-surface', 'rgba(10,10,10,0.8)');
    }
  }

  function setMode(mode) {
    document.documentElement.dataset.theme = mode;
    try { localStorage.setItem(THEME_MODE_KEY, mode); } catch (_) {}
    // Re-apply colors for the chosen mode using stored theme or fallback
    const saved = loadStoredTheme();
    if (!(saved && applyComputedColors(saved.actualComputedColors, mode))) {
      applyFallbackForMode(mode);
    }
  }

  function getStoredMode() {
    try { return localStorage.getItem(THEME_MODE_KEY) || 'light'; } catch (_) { return 'light'; }
  }

  function loadStoredTheme() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (_) { return null; }
  }

  function storeTheme(json) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(json)); } catch (_) {}
  }

  function applyTypographySystem(typo) {
    if (!typo) return;
    const { textStyles, letterSpacing } = typo;
    if (textStyles) {
      Object.entries(textStyles).forEach(([key, val]) => {
        const cssName = `--${key}`;
        setCSSVar(cssName, val);
      });
    }
    if (letterSpacing) {
      Object.entries(letterSpacing).forEach(([key, val]) => {
        const cssName = `--ls-${key}`;
        setCSSVar(cssName, val);
      });
    }
  }

  function applyLayoutSystem(layout) {
    if (!layout) return;
    if (layout.maxWidths?.page) setCSSVar('--page-max-width', layout.maxWidths.page);
    if (layout.maxWidths?.prose) setCSSVar('--prose-max-width', layout.maxWidths.prose);
    if (layout.spacing?.headerHeight) setCSSVar('--header-height', layout.spacing.headerHeight);
    if (layout.spacing?.pageInline) setCSSVar('--page-padding-inline', layout.spacing.pageInline);
    if (layout.spacing?.pageBlock) setCSSVar('--page-padding-block', layout.spacing.pageBlock);
  }

  function applyTheme(json, forcedMode) {
    if (!json) return;
    const mode = (forcedMode || json.metadata?.currentTheme || getStoredMode()).toLowerCase();
    document.documentElement.dataset.theme = mode;
    try { localStorage.setItem(THEME_MODE_KEY, mode); } catch (_) {}
    applyActualVariables(json.actualCSSVariables);
    const ok = applyComputedColors(json.actualComputedColors, mode);
    if (!ok) applyFallbackForMode(mode);
    applyTypographySystem(json.typographySystem);
    applyLayoutSystem(json.layoutSystem);
  }

  // 공개 API
  window.ThemeManager = {
    applyTheme,
    loadStoredTheme,
    storeTheme,
    setMode,
    getStoredMode,
  };

  // 초기화: 저장된 테마 적용 또는 기본 모드 설정(기본 라이트)
  const saved = loadStoredTheme();
  if (saved) {
    applyTheme(saved);
  } else {
    setMode(getStoredMode());
  }
})();




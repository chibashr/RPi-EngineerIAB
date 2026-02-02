const THEME_STORAGE_KEY = "rpi-theme";
const DEFAULT_THEME = "auto";
const VALID_THEMES = new Set(["light", "dark", "auto"]);

function safeGetStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function safeSetStorage(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Ignore storage failures (private mode, quota exceeded, etc.)
  }
}

function setThemeAttribute(value) {
  document.documentElement.setAttribute("data-theme", value);
}

export function getStoredTheme() {
  const stored = safeGetStorage(THEME_STORAGE_KEY);
  return VALID_THEMES.has(stored) ? stored : DEFAULT_THEME;
}

export function applyStoredTheme() {
  setThemeAttribute(getStoredTheme());
}

export function initThemeSelector(selectEl) {
  if (!selectEl) {
    return;
  }

  const storedTheme = getStoredTheme();
  selectEl.value = storedTheme;
  setThemeAttribute(storedTheme);

  selectEl.addEventListener("change", (event) => {
    const selected = event.target.value;
    const safeValue = VALID_THEMES.has(selected) ? selected : DEFAULT_THEME;
    safeSetStorage(THEME_STORAGE_KEY, safeValue);
    setThemeAttribute(safeValue);
  });
}

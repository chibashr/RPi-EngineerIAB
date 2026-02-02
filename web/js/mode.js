const MODE_STORAGE_KEY = "rpi-ui-mode";
const DEFAULT_MODE = "simple";
const VALID_MODES = new Set(["simple", "advanced"]);

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

export function getStoredMode() {
  const stored = safeGetStorage(MODE_STORAGE_KEY);
  return VALID_MODES.has(stored) ? stored : DEFAULT_MODE;
}

export function setMode(mode) {
  const safeMode = VALID_MODES.has(mode) ? mode : DEFAULT_MODE;
  safeSetStorage(MODE_STORAGE_KEY, safeMode);
}

export function ensureSimpleMode() {
  if (getStoredMode() === "advanced") {
    window.location.assign("/advanced/");
  }
}

export function ensureAdvancedMode() {
  if (getStoredMode() === "simple") {
    window.location.assign("/");
  }
}

export function confirmModeSwitch(targetMode) {
  if (targetMode !== "advanced") {
    return true;
  }

  return window.confirm(
    "Advanced Mode exposes system configuration and diagnostic tools. Continue?"
  );
}

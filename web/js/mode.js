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
    setMode("advanced");
  }
}

/**
 * Returns a Promise that resolves to true if the user confirms the mode switch, false otherwise.
 * For "advanced" mode, shows an in-page confirm modal; for "simple", resolves true without prompting.
 * @param {string} targetMode - "simple" or "advanced"
 * @returns {Promise<boolean>}
 */
export async function confirmModeSwitch(targetMode) {
  if (targetMode !== "advanced") {
    return true;
  }

  const { modalConfirm } = await import("./modal.js");
  return modalConfirm(
    "Advanced Mode exposes system configuration and diagnostic tools. Continue?"
  );
}

/** Used by advanced pages to redirect to simple dashboard. Call after setMode("simple"). */
export function goToSimpleMode() {
  window.location.assign("/");
}

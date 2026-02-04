/**
 * Copy text to the clipboard. Uses the Clipboard API when available (secure context),
 * otherwise falls back to document.execCommand("copy") so copy works over HTTP.
 * @param {string} text - Text to copy.
 * @returns {Promise<boolean>} - True if copy succeeded.
 */
export async function copyTextToClipboard(text) {
  if (!text || typeof text !== "string") return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {
    /* Clipboard API failed (e.g. non-secure context); use fallback */
  }
  return fallbackCopy(text);
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  ta.style.top = "0";
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } finally {
    document.body.removeChild(ta);
  }
  return ok;
}

/**
 * Initialize tabbed UI. Optionally sync with URL hash for deep-linking.
 * @param {Element} container - Element with [data-tabs] containing tab buttons
 * @param {{ useHash?: boolean }} options - If useHash: true, read hash on load and update hash on tab change
 */
export function initTabs(container, options = {}) {
  if (!container) {
    return;
  }
  const tabButtons = container.querySelectorAll("[data-tab-target]");
  const searchRoot = container.parentElement || document;
  const tabPanels = searchRoot.querySelectorAll("[data-tab-panel]");

  if (!tabButtons.length || !tabPanels.length) {
    return;
  }

  const useHash = options.useHash === true;
  const validTargets = new Set(
    Array.from(tabButtons).map((b) => b.dataset.tabTarget)
  );

  const activateTab = (target) => {
    if (!validTargets.has(target)) {
      return;
    }
    tabButtons.forEach((button) => {
      const isActive = button.dataset.tabTarget === target;
      button.classList.toggle("tab-button-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    tabPanels.forEach((panel) => {
      panel.hidden = panel.dataset.tabPanel !== target;
    });

    if (useHash) {
      const url = new URL(window.location.href);
      url.hash = target;
      window.history.replaceState(null, "", url.toString());
    }
  };

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tabTarget);
    });
  });

  const initialTarget = useHash
    ? (() => {
        const hash = window.location.hash.slice(1);
        return validTargets.has(hash) ? hash : tabButtons[0].dataset.tabTarget;
      })()
    : tabButtons[0].dataset.tabTarget;
  activateTab(initialTarget);
}

export function createStatusItem(label, value) {
  const item = document.createElement("li");
  item.className = "status-item";
  const labelEl = document.createElement("span");
  labelEl.className = "status-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("span");
  valueEl.className = "status-value";
  valueEl.textContent = value || "--";
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  return item;
}

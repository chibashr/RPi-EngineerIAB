/**
 * Top-bar alerts: bell icon with badge, dropdown showing server-driven alerts.
 * Same source as Dashboard "Recent Alerts" and Logs "Alerts History" (GET /api/v1/system/status).
 * Alerts are clearable (dismissed state stored in localStorage); timestamps shown.
 */

const ALERTS_POLL_INTERVAL_MS = 15000;
const DISMISSED_STORAGE_KEY = "rpi-alerts-dismissed";
const DISMISSED_MAX = 200;
let alertsPollId = null;
/** @type {Array<{ severity?: string, message?: string, timestamp?: string }>} */
let lastAlerts = [];
/** @type {Array<{ severity?: string, message?: string, timestamp?: string }>} */
let lastVisibleAlerts = [];

function escapeHtml(s) {
  if (s == null) return "";
  const div = document.createElement("div");
  div.textContent = String(s);
  return div.innerHTML;
}

function bellIcon() {
  return `<svg class="notifications-bell-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`;
}

/**
 * Format an alert timestamp for display (ISO string -> short time or date).
 * @param {string} [ts] - ISO timestamp
 * @returns {string}
 */
export function formatAlertTimestamp(ts) {
  if (!ts || typeof ts !== "string") return "";
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return "";
    const now = new Date();
    const sameDay = d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
    return sameDay ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function alertKey(alert) {
  const ts = alert.timestamp || "";
  const msg = (alert.message || "").slice(0, 80);
  return `${ts}|${msg}`;
}

function loadDismissed() {
  try {
    const raw = localStorage.getItem(DISMISSED_STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr.slice(-DISMISSED_MAX) : []);
  } catch {
    return new Set();
  }
}

function saveDismissed(set) {
  try {
    const arr = Array.from(set).slice(-DISMISSED_MAX);
    localStorage.setItem(DISMISSED_STORAGE_KEY, JSON.stringify(arr));
  } catch {
    // ignore
  }
}

/**
 * Render server alerts into the bell dropdown and update badge.
 * Filters out dismissed alerts; shows timestamp per alert.
 * @param {Array<{ severity?: string, message?: string, timestamp?: string }>} alerts
 */
function renderAlertsInBell(alerts) {
  const wrap = document.getElementById("notifications-wrap");
  if (!wrap) return;
  const listEl = wrap.querySelector(".notifications-list");
  const emptyEl = wrap.querySelector(".notifications-empty");
  const clearBtn = wrap.querySelector(".notifications-clear-all");
  const badge = wrap.querySelector(".notifications-badge");
  if (!listEl || !emptyEl) return;

  lastAlerts = Array.isArray(alerts) ? alerts : [];
  const dismissed = loadDismissed();
  lastVisibleAlerts = lastAlerts.filter((a) => !dismissed.has(alertKey(a)));

  listEl.innerHTML = "";
  emptyEl.hidden = lastVisibleAlerts.length > 0;
  if (clearBtn) clearBtn.hidden = lastVisibleAlerts.length === 0;

  lastVisibleAlerts.forEach((alert) => {
    const li = document.createElement("li");
    const severity = (alert.severity || "info").toLowerCase();
    li.className = `notifications-item notifications-item--${severity === "critical" ? "error" : severity === "warning" ? "warning" : "info"}`;
    const label = (alert.severity || "info").toUpperCase();
    const message = alert.message || "Alert";
    const timeStr = formatAlertTimestamp(alert.timestamp);
    const timeHtml = timeStr ? `<span class="notifications-item-time">${escapeHtml(timeStr)}</span>` : "";
    li.innerHTML = `<span class="notifications-item-title">${escapeHtml(label)}</span>${timeHtml}<span class="notifications-item-message">${escapeHtml(message)}</span>`;
    listEl.appendChild(li);
  });

  if (badge) {
    badge.textContent = lastVisibleAlerts.length > 99 ? "99+" : String(lastVisibleAlerts.length);
    badge.hidden = lastVisibleAlerts.length === 0;
  }
}

function clearVisibleAlerts() {
  const dismissed = loadDismissed();
  for (const a of lastVisibleAlerts) {
    dismissed.add(alertKey(a));
  }
  saveDismissed(dismissed);
  renderAlertsInBell(lastAlerts);
}

/**
 * Set alerts from an external source (e.g. WebSocket monitor_status). Updates bell dropdown and badge.
 * @param {Array<{ severity?: string, message?: string, timestamp?: string }>} alerts
 */
export function setAlerts(alerts) {
  renderAlertsInBell(alerts || []);
}

/**
 * Fetch alerts from the same API as Dashboard/Logs and update the bell.
 */
async function fetchAndRenderAlerts() {
  try {
    const url = new URL("/api/v1/system/status", window.location.origin);
    const res = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return;
    const payload = await res.json();
    const data = payload?.data ?? payload;
    const alerts = data?.alerts ?? data?.monitor?.alerts ?? [];
    renderAlertsInBell(alerts);
  } catch {
    // ignore
  }
}

function startAlertsPolling() {
  if (alertsPollId) return;
  fetchAndRenderAlerts();
  alertsPollId = window.setInterval(() => {
    if (document.hidden) return;
    fetchAndRenderAlerts();
  }, ALERTS_POLL_INTERVAL_MS);
}

function stopAlertsPolling() {
  if (alertsPollId) {
    window.clearInterval(alertsPollId);
    alertsPollId = null;
  }
}

/**
 * Initialize the notification bell in the topbar. Call once when advanced layout is loaded.
 * Injects the bell and dropdown; fetches alerts from API and polls periodically.
 */
export function initNotifications() {
  const actions = document.querySelector(".topbar-actions");
  if (!actions) return;

  const wrap = document.createElement("div");
  wrap.id = "notifications-wrap";
  wrap.className = "notifications-wrap";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-ghost notifications-bell";
  button.setAttribute("aria-label", "Alerts");
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-haspopup", "true");
  button.setAttribute("aria-controls", "notifications-dropdown");
  button.innerHTML = bellIcon();
  const badge = document.createElement("span");
  badge.className = "notifications-badge";
  badge.hidden = true;
  badge.textContent = "0";
  button.appendChild(badge);

  const dropdown = document.createElement("div");
  dropdown.id = "notifications-dropdown";
  dropdown.className = "notifications-dropdown";
  dropdown.hidden = true;
  dropdown.innerHTML = `
    <div class="notifications-dropdown-header">
      <span class="notifications-dropdown-title">Alerts</span>
      <button type="button" class="btn btn-ghost notifications-clear-all" hidden>Clear all</button>
    </div>
    <p class="notifications-empty">No alerts.</p>
    <ul class="notifications-list" aria-label="Alert list"></ul>
  `;

  wrap.appendChild(button);
  wrap.appendChild(dropdown);
  actions.insertBefore(wrap, actions.firstChild);

  button.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = dropdown.hidden;
    dropdown.hidden = !isOpen;
    button.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  dropdown.querySelector(".notifications-clear-all")?.addEventListener("click", () => {
    clearVisibleAlerts();
  });

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target) && !dropdown.hidden) {
      dropdown.hidden = true;
      button.setAttribute("aria-expanded", "false");
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !dropdown.hidden) {
      dropdown.hidden = true;
      button.setAttribute("aria-expanded", "false");
    }
  });

  startAlertsPolling();
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopAlertsPolling();
  } else if (document.getElementById("notifications-wrap")) {
    startAlertsPolling();
  }
});

window.addEventListener("beforeunload", stopAlertsPolling);

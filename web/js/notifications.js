/**
 * Top-bar notifications: bell icon with badge, dropdown to read and clear.
 * Persists in localStorage (rpi-notifications). Use addNotification() from other modules to push.
 */

const STORAGE_KEY = "rpi-notifications";
const MAX_ITEMS = 100;

function loadNotifications() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list.slice(-MAX_ITEMS) : [];
  } catch {
    return [];
  }
}

function saveNotifications(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(-MAX_ITEMS)));
  } catch {
    // ignore
  }
}

/**
 * Add a notification. Optional: title, type ('info'|'success'|'warning'|'error').
 * @param {{ title?: string, message: string, type?: string }} opts
 */
export function addNotification(opts) {
  const list = loadNotifications();
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  const item = {
    id,
    title: opts.title ?? null,
    message: opts.message ?? "",
    type: opts.type ?? "info",
    createdAt: Date.now(),
  };
  list.push(item);
  saveNotifications(list);
  const wrap = document.getElementById("notifications-wrap");
  if (wrap) {
    updateBadge(wrap, list.length);
    const panel = wrap.querySelector(".notifications-dropdown");
    if (panel) renderList(panel, list);
  }
}

export function getNotifications() {
  return loadNotifications();
}

export function clearNotifications() {
  saveNotifications([]);
  const wrap = document.getElementById("notifications-wrap");
  if (wrap) {
    updateBadge(wrap, 0);
    const panel = wrap.querySelector(".notifications-dropdown");
    if (panel) renderList(panel, []);
  }
}

function updateBadge(wrap, count) {
  const badge = wrap.querySelector(".notifications-badge");
  if (!badge) return;
  badge.textContent = count > 99 ? "99+" : String(count);
  badge.hidden = count === 0;
}

function renderList(panel, list) {
  const listEl = panel.querySelector(".notifications-list");
  const emptyEl = panel.querySelector(".notifications-empty");
  const clearBtn = panel.querySelector(".notifications-clear-all");
  if (!listEl || !emptyEl) return;

  listEl.innerHTML = "";
  emptyEl.hidden = list.length > 0;
  if (clearBtn) clearBtn.hidden = list.length === 0;

  list.forEach((item) => {
    const li = document.createElement("li");
    li.className = `notifications-item notifications-item--${item.type ?? "info"}`;
    const title = item.title ? `<span class="notifications-item-title">${escapeHtml(item.title)}</span>` : "";
    li.innerHTML = `${title}<span class="notifications-item-message">${escapeHtml(item.message)}</span>`;
    listEl.appendChild(li);
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function bellIcon() {
  return `<svg class="notifications-bell-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`;
}

/**
 * Initialize the notification bell in the topbar. Call once when advanced layout is loaded.
 * Injects the bell and dropdown into .topbar-actions.
 */
export function initNotifications() {
  const actions = document.querySelector(".topbar-actions");
  if (!actions) return;

  const list = loadNotifications();

  const wrap = document.createElement("div");
  wrap.id = "notifications-wrap";
  wrap.className = "notifications-wrap";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn btn-ghost notifications-bell";
  button.setAttribute("aria-label", "Notifications");
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-haspopup", "true");
  button.setAttribute("aria-controls", "notifications-dropdown");
  button.innerHTML = bellIcon();
  const badge = document.createElement("span");
  badge.className = "notifications-badge";
  badge.hidden = list.length === 0;
  badge.textContent = list.length > 99 ? "99+" : String(list.length);
  button.appendChild(badge);

  const dropdown = document.createElement("div");
  dropdown.id = "notifications-dropdown";
  dropdown.className = "notifications-dropdown";
  dropdown.hidden = true;
  dropdown.innerHTML = `
    <div class="notifications-dropdown-header">
      <span class="notifications-dropdown-title">Notifications</span>
      <button type="button" class="btn btn-ghost notifications-clear-all" ${list.length === 0 ? "hidden" : ""}>Clear all</button>
    </div>
    <p class="notifications-empty" ${list.length > 0 ? "hidden" : ""}>No notifications.</p>
    <ul class="notifications-list" aria-label="Notification list"></ul>
  `;

  wrap.appendChild(button);
  wrap.appendChild(dropdown);
  actions.insertBefore(wrap, actions.firstChild);

  renderList(dropdown, list);

  button.addEventListener("click", (e) => {
    e.stopPropagation();
    const isOpen = dropdown.hidden;
    dropdown.hidden = !isOpen;
    button.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  dropdown.querySelector(".notifications-clear-all")?.addEventListener("click", () => {
    clearNotifications();
    dropdown.hidden = true;
    button.setAttribute("aria-expanded", "false");
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
}

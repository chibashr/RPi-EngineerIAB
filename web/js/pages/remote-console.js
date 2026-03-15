/**
 * SSH/Telnet page: targets, sessions, and browser terminal.
 */

import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { getContainer, bindEscape, trapFocus, escapeHtml } from "../modal.js";

const REMOTE_API_TIMEOUT_MS = 20000;

const elements = {
  targetList: document.getElementById("remote-target-list"),
  listPlaceholder: document.getElementById("remote-list-placeholder"),
  detailEmpty: document.getElementById("remote-detail-empty"),
  detailContent: document.getElementById("remote-detail-content"),
  sessionsMeta: document.getElementById("remote-sessions-meta"),
  consolePanels: document.getElementById("remote-console-panels"),
};

let targetCache = [];
let sessionMap = new Map();
let activeSessions = [];
let activeTabSessionId = null;

function showToast(message, variant = "info") {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  region.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function updateSessionsMeta() {
  if (!elements.sessionsMeta) return;
  const n = sessionMap.size;
  elements.sessionsMeta.textContent = n > 0 ? `${n} active` : "";
}

function updateEmptyState() {
  const showContent = sessionMap.size > 0;
  if (elements.detailEmpty) elements.detailEmpty.hidden = showContent;
  if (elements.detailContent) elements.detailContent.hidden = !showContent;
}

function sessionLabel(session) {
  const t = session.type || "ssh";
  const h = session.host || "?";
  const p = session.port != null ? session.port : 22;
  return `${t.toUpperCase()} ${h}:${p}`;
}

function createTabAndConnect(sessionId, label) {
  if (sessionMap.has(sessionId)) return sessionMap.get(sessionId);

  const state = {
    sessionId,
    label,
    wsClient: null,
    wsStatus: "",
    connectTimeoutId: null,
    tabPanelEl: null,
    statusEl: null,
    xtermInstance: null,
    resizeObserver: null,
  };
  sessionMap.set(sessionId, state);

  const panel = document.createElement("div");
  panel.className = "console-tab-panel console-block";
  panel.dataset.sessionId = sessionId;
  panel.setAttribute("role", "tabpanel");
  state.tabPanelEl = panel;

  const toolbarRow = document.createElement("div");
  toolbarRow.className = "console-toolbar-row";
  const toolbar = document.createElement("div");
  toolbar.className = "console-toolbar";
  const clearBtn = document.createElement("button");
  clearBtn.className = "btn btn-secondary btn-sm";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", () => state.xtermInstance?.clear());
  const disconnectBtn = document.createElement("button");
  disconnectBtn.className = "btn btn-ghost btn-danger-ghost btn-sm";
  disconnectBtn.textContent = "Disconnect";
  disconnectBtn.title = "Close this session";
  disconnectBtn.addEventListener("click", () => disconnectSession(sessionId));
  toolbar.append(clearBtn, disconnectBtn);
  toolbarRow.append(toolbar);

  const status = document.createElement("div");
  status.className = "console-status status-disconnected";
  status.textContent = "Connecting...";
  state.statusEl = status;

  const body = document.createElement("div");
  body.className = "console-block-body";
  const wrapper = document.createElement("div");
  wrapper.className = "console-window-wrapper";
  const container = document.createElement("div");
  container.className = "console-window xterm-container";
  container.setAttribute("aria-label", "Remote console");
  wrapper.appendChild(container);
  body.appendChild(wrapper);

  const term = new window.Terminal({
    scrollback: 5000,
    convertEol: false,
    fontFamily: '"Courier New", Consolas, monospace',
    fontSize: 14,
    lineHeight: 1.4,
    theme: {
      background: "#0d0e11",
      foreground: "#c8cdd4",
      cursor: "#c8cdd4",
      selectionBackground: "rgba(47, 111, 237, 0.35)",
      black: "#1e2129",
      brightBlack: "#3a4049",
      white: "#c8cdd4",
      brightWhite: "#eef1f4",
    },
  });
  state.xtermInstance = term;
  term.open(container);

  const containerDiv = container;
  const resizeObserver = new ResizeObserver(() => {
    if (!term._core) return;
    const screen = containerDiv.querySelector(".xterm-screen");
    const viewport = containerDiv.querySelector(".xterm-viewport");
    if (!screen) return;
    const dims = term._core._renderService?.dimensions;
    const cellW = dims?.actualCellWidth || dims?.css?.cell?.width;
    const cellH = dims?.actualCellHeight || dims?.css?.cell?.height;
    if (!cellW || !cellH) return;
    const availW =
      containerDiv.clientWidth -
      (viewport
        ? (parseInt(getComputedStyle(viewport).paddingLeft) || 0) +
          (parseInt(getComputedStyle(viewport).paddingRight) || 0)
        : 0) -
      16;
    const availH = containerDiv.clientHeight;
    const cols = Math.max(1, Math.floor(availW / cellW));
    const rows = Math.max(1, Math.floor(availH / cellH));
    if (cols !== term.cols || rows !== term.rows) {
      term.resize(cols, rows);
    }
  });
  resizeObserver.observe(containerDiv);
  state.resizeObserver = resizeObserver;

  const main = document.createElement("div");
  main.className = "console-panel-main";
  main.append(status, body);
  panel.append(toolbarRow, main);
  elements.consolePanels?.appendChild(panel);

  term.onData((data) => {
    sendToSession(sessionId, data);
  });

  switchTab(sessionId);
  updateEmptyState();
  updateSessionsMeta();

  state.wsClient = createWebSocketClient(`/ws/remote-console/${sessionId}`, { autoReconnect: false });
  state.wsClient.onStatus((status) => {
    state.wsStatus = status;
    if (status === "connected" || status === "disconnected" || status === "error") {
      if (state.connectTimeoutId != null) {
        window.clearTimeout(state.connectTimeoutId);
        state.connectTimeoutId = null;
      }
    }
    if (state.statusEl) {
      state.statusEl.textContent = status;
      state.statusEl.className = "console-status status-" + status;
    }
    if (status === "connected" && activeTabSessionId === sessionId) {
      state.xtermInstance?.focus();
    }
    if (status === "disconnected" || status === "error") {
      state.wsClient = null;
      state.wsStatus = "";
    }
    renderTargets();
  });
  state.wsClient.on("data", (message) => {
    const raw = message.data || "";
    state.xtermInstance?.write(raw);
  });
  state.wsClient.on("status", (message) => {
    if (state.statusEl) {
      const tx = message.bytes_tx || 0;
      const rx = message.bytes_rx || 0;
      state.statusEl.textContent = `Tx ${tx} / Rx ${rx}`;
    }
  });
  state.wsClient.on("error", (message) => {
    showToast(message?.message || "Connection error.", "error");
  });
  state.wsClient.connect();

  state.connectTimeoutId = window.setTimeout(() => {
    if (!state.wsStatus || state.wsStatus === "connecting") {
      if (state.wsClient) {
        state.wsClient.close();
        state.wsClient = null;
      }
      state.wsStatus = "";
      if (state.statusEl) {
        state.statusEl.textContent = "Disconnected (timeout)";
        state.statusEl.className = "console-status status-error";
      }
      showToast("Connection timed out. Check host and credentials.", "error");
      renderTargets();
    }
    state.connectTimeoutId = null;
  }, 20000);
  state.xtermInstance?.focus();
  return state;
}

function sendToSession(sessionId, data) {
  const state = sessionMap.get(sessionId);
  if (!state?.wsClient) {
    showToast("Not connected.", "error");
    return false;
  }
  const sent = state.wsClient.send({ type: "data", data });
  if (!sent) showToast("Connection not ready.", "error");
  return sent;
}

function switchTab(sessionId) {
  activeTabSessionId = sessionId;
  sessionMap.forEach((s, sid) => {
    s.tabPanelEl?.classList.toggle("is-active", sid === sessionId);
  });
  const state = sessionMap.get(sessionId);
  state?.xtermInstance?.focus();
  renderTargets();
}

function removeTab(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state) return;
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
    state.connectTimeoutId = null;
  }
  if (state.wsClient) {
    state.wsClient.close();
    state.wsClient = null;
  }
  state.xtermInstance?.dispose();
  state.resizeObserver?.disconnect();
  state.tabPanelEl?.remove();
  sessionMap.delete(sessionId);
  if (activeTabSessionId === sessionId) {
    activeTabSessionId = sessionMap.size > 0 ? Array.from(sessionMap.keys())[0] : null;
    if (activeTabSessionId) switchTab(activeTabSessionId);
  }
  updateEmptyState();
  updateSessionsMeta();
  renderTargets();
}

async function disconnectSession(sessionId) {
  try {
    await apiDelete(`/api/v1/remote-console/sessions/${encodeURIComponent(sessionId)}`, {
      timeoutMs: REMOTE_API_TIMEOUT_MS,
    });
    showToast("Session closed.", "success");
  } catch {
    showToast("Unable to close session.", "error");
  }
  removeTab(sessionId);
}

function renderTargets() {
  if (!elements.targetList) return;
  const items = [];

  targetCache.forEach((t) => {
    const li = document.createElement("li");
    li.className = "serial-list-item";
    li.dataset.targetId = t.id;
    const dot = document.createElement("span");
    dot.className = "serial-list-item-dot";
    const label = document.createElement("span");
    label.className = "serial-list-item-label";
    label.textContent = t.friendly_name || t.host || t.id;
    const badge = document.createElement("span");
    badge.className = "remote-type-badge " + (t.type === "telnet" ? "telnet" : "ssh");
    badge.textContent = t.type === "telnet" ? "Telnet" : "SSH";
    li.append(dot, label, badge);
    li.addEventListener("click", async () => {
      const result = await openSessionCreatorModal(t);
      await handleSessionCreatorResult(result, t);
    });
    items.push(li);
  });

  activeSessions.forEach((s) => {
    const state = sessionMap.get(s.session_id);
    const connected = state && state.wsStatus === "connected";
    const li = document.createElement("li");
    li.className = "serial-list-item" + (activeTabSessionId === s.session_id ? " is-active" : "");
    li.dataset.sessionId = s.session_id;
    const dot = document.createElement("span");
    dot.className = "serial-list-item-dot" + (connected ? " is-connected" : "");
    const label = document.createElement("span");
    label.className = "serial-list-item-label";
    label.textContent = sessionLabel(s);
    const badge = document.createElement("span");
    badge.className = "remote-type-badge " + (s.type === "telnet" ? "telnet" : "ssh");
    badge.textContent = s.type === "telnet" ? "Telnet" : "SSH";
    li.append(dot, label, badge);
    li.addEventListener("click", () => switchTab(s.session_id));
    items.push(li);
  });

  elements.targetList.innerHTML = "";
  if (items.length === 0) {
    const ph = document.createElement("li");
    ph.className = "serial-list-placeholder";
    ph.id = "remote-list-placeholder";
    ph.textContent = targetCache.length === 0 && activeSessions.length === 0 ? "No targets. Add one or use New Session." : "";
    elements.targetList.appendChild(ph);
  } else {
    items.forEach((el) => elements.targetList.appendChild(el));
  }
}

/**
 * Open the single session creator modal. Pre-fill if editing a saved target (password not returned by API).
 * @param {object} [initialTarget] - Saved target to edit/connect to; omit for new session.
 * @returns {Promise<{ action: 'save'|'connect', data: Record<string, string> }|null>}
 */
function openSessionCreatorModal(initialTarget = null) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const connType = initialTarget ? initialTarget.type : "ssh";
  const defaultPort = connType === "telnet" ? "23" : "22";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "session-creator-title");

  let resolveRef;
  const promise = new Promise((resolve) => {
    resolveRef = resolve;
  });

  const close = (value) => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
    resolveRef(value);
  };

  const title = initialTarget ? "Edit session" : "New Session";
  const nameVal = initialTarget ? escapeHtml(initialTarget.friendly_name || initialTarget.host) : "";
  const hostVal = initialTarget ? escapeHtml(initialTarget.host) : "";
  const portVal = initialTarget ? String(initialTarget.port) : defaultPort;
  const userVal = initialTarget && initialTarget.username ? escapeHtml(initialTarget.username) : "";

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-form">
      <h2 id="session-creator-title" class="modal-title">${escapeHtml(title)}</h2>
      <form class="modal-form" id="session-creator-form">
        <div class="field" data-field-name="session_name">
          <label class="field-label" for="session-creator-name">Session name (for save)</label>
          <input type="text" id="session-creator-name" name="session_name" class="modal-input" value="${nameVal}" placeholder="e.g. Router A" />
        </div>
        <div class="session-type-switcher field" role="group" aria-label="Connection type">
          <span class="field-label">Type</span>
          <div class="btn-group-inline">
            <button type="button" class="btn btn-secondary session-type-btn ${connType === "ssh" ? "is-active" : ""}" data-type="ssh">SSH</button>
            <button type="button" class="btn btn-secondary session-type-btn ${connType === "telnet" ? "is-active" : ""}" data-type="telnet">Telnet</button>
          </div>
          <input type="hidden" name="type" id="session-creator-type" value="${escapeHtml(connType)}" />
        </div>
        <div class="field" data-field-name="host">
          <label class="field-label" for="session-creator-host">Host</label>
          <input type="text" id="session-creator-host" name="host" class="modal-input" value="${hostVal}" placeholder="192.168.1.1 or hostname" />
        </div>
        <div class="field" data-field-name="port">
          <label class="field-label" for="session-creator-port">Port</label>
          <input type="text" id="session-creator-port" name="port" class="modal-input" value="${portVal}" placeholder="22 or 23" />
        </div>
        <div class="field" data-field-name="username">
          <label class="field-label" for="session-creator-username">Username (for connection)</label>
          <input type="text" id="session-creator-username" name="username" class="modal-input" value="${userVal}" placeholder="Optional" autocomplete="off" />
        </div>
        <div class="field" data-field-name="password">
          <label class="field-label" for="session-creator-password">Password (for connection)</label>
          <input type="password" id="session-creator-password" name="password" class="modal-input" value="" placeholder="Optional" autocomplete="off" />
        </div>
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
          <button type="button" class="btn btn-secondary session-save-btn">Save</button>
          <button type="button" class="btn btn-primary session-connect-btn">Connect</button>
        </div>
      </form>
    </div>
  `;

  const form = overlay.querySelector("#session-creator-form");
  const typeInput = overlay.querySelector("#session-creator-type");
  const portInput = overlay.querySelector("#session-creator-port");
  const typeBtns = overlay.querySelectorAll(".session-type-btn");

  typeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const t = btn.dataset.type;
      typeInput.value = t;
      typeBtns.forEach((b) => b.classList.toggle("is-active", b.dataset.type === t));
      const defaultP = t === "telnet" ? "23" : "22";
      if (!portInput.value || portInput.value === "22" || portInput.value === "23") {
        portInput.value = defaultP;
      }
    });
  });

  function getFormData() {
    return {
      session_name: (overlay.querySelector("#session-creator-name")?.value ?? "").trim(),
      type: (overlay.querySelector("#session-creator-type")?.value ?? "ssh").toLowerCase(),
      host: (overlay.querySelector("#session-creator-host")?.value ?? "").trim(),
      port: (overlay.querySelector("#session-creator-port")?.value ?? "22").trim(),
      username: (overlay.querySelector("#session-creator-username")?.value ?? "").trim(),
      password: (overlay.querySelector("#session-creator-password")?.value ?? "").trim(),
    };
  }

  overlay.querySelector(".modal-cancel").addEventListener("click", () => close(null));
  overlay.querySelector(".session-save-btn").addEventListener("click", () => close({ action: "save", data: getFormData() }));
  overlay.querySelector(".session-connect-btn").addEventListener("click", () => close({ action: "connect", data: getFormData() }));
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    close({ action: "connect", data: getFormData() });
  });

  bindEscape(overlay, () => close(null));
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));
  const firstInput = overlay.querySelector(".modal-input");
  if (firstInput) {
    firstInput.focus();
    if (typeof firstInput.select === "function") firstInput.select();
  }

  return promise;
}

async function handleSessionCreatorResult(result, initialTarget) {
  if (!result) return;
  const { action, data } = result;
  const host = (data.host || "").trim();
  const port = parseInt(data.port, 10) || (data.type === "telnet" ? 23 : 22);
  const connType = (data.type || "ssh").toLowerCase();
  const username = (data.username || "").trim() || undefined;
  const password = (data.password || "").trim() || undefined;
  const friendlyName = (data.session_name || host).trim();

  if (action === "save") {
    try {
      if (initialTarget) {
        const payload = {
          friendly_name: friendlyName || initialTarget.host,
          host,
          port,
          type: connType,
          username: username || null,
        };
        if (password) payload.password = password;
        await apiPut(
          `/api/v1/remote-console/targets/${encodeURIComponent(initialTarget.id)}`,
          payload,
          { timeoutMs: REMOTE_API_TIMEOUT_MS }
        );
        showToast("Session updated.", "success");
      } else {
        if (!host) {
          showToast("Host is required to save.", "error");
          return;
        }
        const payload = {
          host,
          port,
          type: connType,
          friendly_name: friendlyName || host,
          username: username || null,
        };
        if (password) payload.password = password;
        await apiPost("/api/v1/remote-console/targets", payload, { timeoutMs: REMOTE_API_TIMEOUT_MS });
        showToast("Session saved.", "success");
      }
      await loadTargets();
      renderTargets();
    } catch (e) {
      showToast(e?.message || "Unable to save.", "error");
    }
    return;
  }

  if (action === "connect") {
    if (!host) {
      showToast("Host is required to connect.", "error");
      return;
    }
    const payload = initialTarget
      ? { target_id: initialTarget.id }
      : { host, port, type: connType, username };
    if (password !== undefined && password !== "") payload.password = password;
    const label = sessionLabel({ type: connType, host, port });
    await createSessionAndConnect(payload, label);
  }
}

async function createSessionAndConnect(payload, label) {
  showToast("Connecting…", "info");
  try {
    const res = await apiPost("/api/v1/remote-console/sessions", payload, { timeoutMs: REMOTE_API_TIMEOUT_MS });
    const data = extractData(res) || {};
    const sessionId = data.session_id;
    if (!sessionId) {
      showToast("Invalid response from server.", "error");
      return;
    }
    showToast("Session created.", "success");
    activeSessions.push({
      session_id: sessionId,
      target_id: data.target_id,
      type: data.type,
      host: data.host,
      port: data.port,
    });
    renderTargets();
    createTabAndConnect(sessionId, label);
    renderTargets();
  } catch (err) {
    const msg = err?.message || "";
    if (msg.includes("401") || msg.includes("Unauthorized")) {
      showToast("Admin login required.", "error");
    } else {
      showToast(msg || "Unable to create session.", "error");
    }
  }
}


async function loadTargets() {
  try {
    const payload = await apiGet("/api/v1/remote-console/targets", { timeoutMs: REMOTE_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    targetCache = data.targets || [];
  } catch {
    targetCache = [];
    showToast("Unable to load targets.", "error");
  }
}

async function loadSessions() {
  try {
    const payload = await apiGet("/api/v1/remote-console/sessions", { timeoutMs: REMOTE_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    const apiSessions = data.sessions || [];
    const apiIds = new Set(apiSessions.map((s) => s.session_id));
    activeSessions = apiSessions;
    sessionMap.forEach((st, sessionId) => {
      if (!apiIds.has(sessionId)) {
        removeTab(sessionId);
      }
    });
    apiSessions.forEach((s) => {
      if (!sessionMap.has(s.session_id)) {
        createTabAndConnect(s.session_id, sessionLabel(s));
      }
    });
    renderTargets();
  } catch {
    showToast("Unable to load sessions.", "error");
  }
}

async function init() {
  const refresh = document.getElementById("refresh-remote-console");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadTargets();
      loadSessions();
    });
  }
  const newBtn = document.getElementById("new-remote-session");
  if (newBtn) {
    newBtn.addEventListener("click", async () => {
      const result = await openSessionCreatorModal();
      await handleSessionCreatorResult(result, null);
    });
  }
  const addTargetBtn = document.getElementById("add-target-btn");
  if (addTargetBtn) {
    addTargetBtn.addEventListener("click", async () => {
      const result = await openSessionCreatorModal();
      await handleSessionCreatorResult(result, null);
    });
  }
  await loadTargets();
  await loadSessions();
  renderTargets();
}

init();

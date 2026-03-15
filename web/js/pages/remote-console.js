/**
 * Remote Console (SSH / Telnet) page: targets, sessions, and browser terminal.
 */

import { apiGet, apiPost, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalConfirm } from "../modal.js";

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
    li.addEventListener("click", () => openConnectToTargetModal(t));
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

async function openConnectToTargetModal(target) {
  const fields = [
    { name: "target_id", label: "Target", type: "display", default: target.friendly_name || target.host },
  ];
  if (target.type === "ssh") {
    fields.push({
      name: "password",
      label: "Password (leave blank if using key)",
      type: "password",
      default: "",
      placeholder: "Optional",
    });
  }
  const form = await modalForm(fields, "Connect to " + (target.friendly_name || target.host));
  if (!form) return;
  const payload = { target_id: target.id };
  if (target.type === "ssh" && form.password) payload.password = form.password;
  await createSessionAndConnect(payload, sessionLabel({ type: target.type, host: target.host, port: target.port }));
}

async function openNewSessionModal() {
  const targetOptions = targetCache.map((t) => ({
    value: t.id,
    label: (t.friendly_name || t.host) + " (" + (t.type === "ssh" ? "SSH" : "Telnet") + ")",
  }));
  const fields = [
    {
      name: "mode",
      label: "Mode",
      type: "select",
      default: targetOptions.length ? "saved" : "quick",
      options: [
        { value: "saved", label: "Saved target" },
        { value: "quick", label: "Quick connect" },
      ],
    },
    {
      name: "target_id",
      label: "Target",
      type: "select",
      default: targetOptions[0]?.value ?? "",
      options: targetOptions.length ? targetOptions : [{ value: "", label: "No targets saved" }],
    },
    { name: "password", label: "Password (for saved SSH)", type: "password", default: "", placeholder: "Optional" },
    { name: "host", label: "Host (quick connect)", type: "text", default: "", placeholder: "e.g. 192.168.1.1" },
    { name: "port", label: "Port (quick connect)", type: "text", default: "22", placeholder: "22 or 23" },
    {
      name: "type",
      label: "Type (quick connect)",
      type: "select",
      default: "ssh",
      options: [
        { value: "ssh", label: "SSH" },
        { value: "telnet", label: "Telnet" },
      ],
    },
    { name: "username", label: "Username (quick connect)", type: "text", default: "", placeholder: "Optional" },
    { name: "quick_password", label: "Password (quick connect)", type: "password", default: "", placeholder: "Optional" },
  ];
  const form = await modalForm(fields, "New Session");
  if (!form) return;
  let payload;
  let label;
  if (form.mode === "saved" && form.target_id) {
    const t = targetCache.find((x) => x.id === form.target_id);
    if (!t) {
      showToast("Target not found.", "error");
      return;
    }
    payload = { target_id: form.target_id };
    if (t.type === "ssh" && form.password) payload.password = form.password;
    label = (t.friendly_name || t.host) + " " + (t.type === "ssh" ? "SSH" : "Telnet");
  } else {
    const host = (form.host || "").trim();
    if (!host) {
      showToast("Host is required for quick connect.", "error");
      return;
    }
    const port = parseInt(form.port, 10) || 22;
    payload = { host, port, type: form.type || "ssh", username: (form.username || "").trim() || undefined };
    if (form.quick_password) payload.password = form.quick_password;
    label = (form.type === "telnet" ? "Telnet" : "SSH") + " " + host + ":" + port;
  }
  await createSessionAndConnect(payload, label);
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

async function openAddTargetModal() {
  const form = await modalForm(
    [
      { name: "friendly_name", label: "Name", type: "text", default: "", placeholder: "e.g. Router A" },
      { name: "host", label: "Host", type: "text", default: "", placeholder: "192.168.1.1 or hostname" },
      { name: "port", label: "Port", type: "text", default: "22", placeholder: "22 (SSH) or 23 (Telnet)" },
      {
        name: "type",
        label: "Type",
        type: "select",
        default: "ssh",
        options: [
          { value: "ssh", label: "SSH" },
          { value: "telnet", label: "Telnet" },
        ],
      },
      { name: "username", label: "Username", type: "text", default: "", placeholder: "Optional" },
      {
        name: "auth_type",
        label: "Auth (SSH)",
        type: "select",
        default: "password",
        options: [
          { value: "password", label: "Password (enter at connect)" },
          { value: "key", label: "Private key path" },
        ],
      },
      { name: "private_key_path", label: "Private key path", type: "text", default: "", placeholder: "e.g. /home/pi/.ssh/id_rsa" },
    ],
    "Add Target"
  );
  if (!form) return;
  const host = (form.host || "").trim();
  if (!host) {
    showToast("Host is required.", "error");
    return;
  }
  const port = parseInt(form.port, 10) || 22;
  const payload = {
    host,
    port,
    type: (form.type || "ssh").toLowerCase(),
    friendly_name: (form.friendly_name || host).trim(),
    username: (form.username || "").trim() || undefined,
    auth_type: form.auth_type === "key" ? "key" : undefined,
    private_key_path: form.auth_type === "key" && form.private_key_path ? form.private_key_path.trim() : undefined,
  };
  try {
    await apiPost("/api/v1/remote-console/targets", payload, { timeoutMs: REMOTE_API_TIMEOUT_MS });
    showToast("Target added.", "success");
    await loadTargets();
    renderTargets();
  } catch (e) {
    showToast(e?.message || "Unable to add target.", "error");
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
    newBtn.addEventListener("click", () => openNewSessionModal());
  }
  const addTargetBtn = document.getElementById("add-target-btn");
  if (addTargetBtn) {
    addTargetBtn.addEventListener("click", () => openAddTargetModal());
  }
  await loadTargets();
  await loadSessions();
  renderTargets();
}

init();

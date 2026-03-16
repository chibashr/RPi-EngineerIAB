/**
 * SSH / Telnet console page: saved connections, sessions, and browser terminal.
 */

import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
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
  container.setAttribute("aria-label", "SSH or Telnet session");
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
  elements.targetList.innerHTML = "";

  const hasSaved = targetCache.length > 0;
  const hasActive = activeSessions.length > 0;

  if (!hasSaved && !hasActive) {
    const ph = document.createElement("li");
    ph.className = "serial-list-placeholder";
    ph.id = "remote-list-placeholder";
    ph.textContent = "No saved connections. Use Connect to start a session.";
    elements.targetList.appendChild(ph);
    return;
  }

  if (hasSaved) {
    const savedLabel = document.createElement("li");
    savedLabel.className = "serial-list-section-label";
    savedLabel.textContent = "Saved";
    elements.targetList.appendChild(savedLabel);
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
      elements.targetList.appendChild(li);
    });
  }

  if (hasActive) {
    const activeLabel = document.createElement("li");
    activeLabel.className = "serial-list-section-label";
    activeLabel.textContent = "Active";
    elements.targetList.appendChild(activeLabel);
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
      elements.targetList.appendChild(li);
    });
  }
}

async function openConnectToTargetModal(target) {
  const modalTitle = target.friendly_name || target.host;
  const authDefault = target.auth_type === "key" ? "key" : "password";
  const fields = [
    {
      name: "type",
      label: "Type",
      type: "select",
      default: target.type || "ssh",
      options: [
        { value: "ssh", label: "SSH" },
        { value: "telnet", label: "Telnet" },
      ],
    },
    { name: "host", label: "Host", type: "text", default: target.host || "", placeholder: "192.168.1.1 or hostname" },
    { name: "port", label: "Port", type: "text", default: String(target.port != null ? target.port : 22), placeholder: "22" },
    { name: "username", label: "Username", type: "text", default: target.username || "", placeholder: "Optional" },
    {
      name: "auth",
      label: "Auth",
      type: "select",
      default: authDefault,
      options: [
        { value: "password", label: "Password" },
        { value: "key", label: "Key" },
      ],
    },
    { name: "password", label: "Password", type: "password", default: "", placeholder: "Optional" },
    { name: "private_key_path", label: "Key path", type: "text", default: target.private_key_path || "", placeholder: "/home/pi/.ssh/id_rsa" },
    { name: "_divider", label: "", type: "display", default: "" },
    { name: "save_as", label: "Save as", type: "text", default: target.friendly_name || "", placeholder: "Leave blank to not save · defaults to host" },
  ];
  const form = await modalForm(fields, modalTitle, {
    onOpen(overlay) {
      const typeSelect = overlay.querySelector("#modal-form-type");
      const portInput = overlay.querySelector("#modal-form-port");
      const authSelect = overlay.querySelector("#modal-form-auth");
      const authRow = overlay.querySelector('[data-field-name="auth"]');
      const passwordRow = overlay.querySelector('[data-field-name="password"]');
      const keyRow = overlay.querySelector('[data-field-name="private_key_path"]');
      const saveAsInput = overlay.querySelector("#modal-form-save_as");
      const dividerRow = overlay.querySelector('[data-field-name="_divider"]');
      if (dividerRow) dividerRow.classList.add("modal-section-divider");
      const warningEl = document.createElement("div");
      warningEl.className = "modal-field-warning";
      warningEl.setAttribute("aria-live", "polite");
      saveAsInput?.closest(".field")?.appendChild(warningEl);

      const modalActions = overlay.querySelector(".modal-actions");
      if (modalActions) {
        modalActions.style.justifyContent = "space-between";
        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.className = "btn btn-ghost btn-danger-ghost btn-sm";
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", async () => {
          try {
            await apiDelete(`/api/v1/remote-console/targets/${encodeURIComponent(target.id)}`, { timeoutMs: REMOTE_API_TIMEOUT_MS });
            showToast("Connection deleted.", "success");
            await loadTargets();
            renderTargets();
            overlay.querySelector(".modal-cancel")?.click();
          } catch {
            showToast("Unable to delete connection.", "error");
          }
        });
        modalActions.insertBefore(deleteBtn, modalActions.firstChild);
      }

      function updatePort() {
        if (!typeSelect || !portInput) return;
        portInput.value = typeSelect.value === "telnet" ? "23" : "22";
      }
      function updateCredentialVisibility() {
        const isTelnet = typeSelect?.value === "telnet";
        if (authRow) authRow.hidden = isTelnet;
        if (isTelnet) {
          if (passwordRow) {
            passwordRow.hidden = false;
            const lab = passwordRow.querySelector(".field-label");
            if (lab) lab.textContent = "Password";
            const inp = passwordRow.querySelector("input");
            if (inp) inp.placeholder = "Optional";
          }
          if (keyRow) keyRow.hidden = true;
        } else {
          const isKey = authSelect?.value === "key";
          if (passwordRow) {
            passwordRow.hidden = isKey;
            const lab = passwordRow.querySelector(".field-label");
            if (lab) lab.textContent = "Password";
            const inp = passwordRow.querySelector("input");
            if (inp) inp.placeholder = "Optional";
          }
          if (keyRow) keyRow.hidden = !isKey;
        }
      }
      function updateSaveAsWarning() {
        const raw = saveAsInput?.value ?? "";
        const { collision, suggested } = getCollisionSuggest(raw, target.id);
        if (warningEl) {
          warningEl.textContent = collision ? `"${raw.trim()}" already exists. Will save as "${suggested}" unless you rename above.` : "";
        }
      }
      typeSelect?.addEventListener("change", () => {
        updatePort();
        updateCredentialVisibility();
      });
      authSelect?.addEventListener("change", updateCredentialVisibility);
      saveAsInput?.addEventListener("blur", updateSaveAsWarning);
      updatePort();
      updateCredentialVisibility();
    },
  });
  if (!form) return;

  const host = (form.host || "").trim();
  if (!host) {
    showToast("Host is required.", "error");
    return;
  }
  const port = parseInt(form.port, 10) || 22;
  const type = (form.type || "ssh").toLowerCase();
  const isTelnet = type === "telnet";
  const auth = form.auth || "password";
  const username = (form.username || "").trim() || undefined;
  const saveAsTrimmed = (form.save_as || "").trim();
  const keyPath = !isTelnet && auth === "key" && form.private_key_path ? form.private_key_path.trim() : undefined;

  const typeChanged = (target.type || "ssh") !== type;
  const hostChanged = (target.host || "") !== host;
  const portChanged = (target.port != null ? target.port : 22) !== port;
  const usernameChanged = (target.username || "") !== (username || "");
  const authChanged = (target.auth_type === "key" ? "key" : "password") !== auth;
  const keyPathChanged = (target.private_key_path || "") !== (keyPath || "");
  const saveAsChanged = (target.friendly_name || "") !== saveAsTrimmed;
  const anyChanged = typeChanged || hostChanged || portChanged || usernameChanged || authChanged || keyPathChanged || saveAsChanged;

  if (!anyChanged) {
    const payload = { target_id: target.id };
    if (target.type === "ssh" && form.password) payload.password = form.password;
    await createSessionAndConnect(payload, sessionLabel({ type: target.type, host: target.host, port: target.port }));
    return;
  }

  let resolvedName = saveAsTrimmed || host;
  if (saveAsTrimmed) {
    const { collision, suggested } = getCollisionSuggest(saveAsTrimmed, target.id);
    resolvedName = collision ? suggested : saveAsTrimmed;
  }
  try {
    await apiPut(`/api/v1/remote-console/targets/${encodeURIComponent(target.id)}`, {
      host,
      port,
      type,
      friendly_name: resolvedName,
      username,
      auth_type: !isTelnet && auth === "key" ? "key" : undefined,
      private_key_path: keyPath,
    }, { timeoutMs: REMOTE_API_TIMEOUT_MS });
    if (resolvedName !== (target.friendly_name || "")) {
      showToast("Connection saved.", "success");
      await loadTargets();
      renderTargets();
    }
  } catch (e) {
    showToast(e?.message || "Unable to save connection.", "error");
    return;
  }
  const payload = { target_id: target.id };
  if (type === "ssh" && form.password) payload.password = form.password;
  await createSessionAndConnect(payload, sessionLabel({ type, host, port }));
}

function getCollisionSuggest(name, excludeTargetId) {
  const trimmed = (name || "").trim();
  if (!trimmed) return { collision: false };
  const names = new Set(
    targetCache
      .filter((t) => !excludeTargetId || t.id !== excludeTargetId)
      .map((t) => (t.friendly_name || "").trim())
      .filter(Boolean)
  );
  if (!names.has(trimmed)) return { collision: false };
  let suggested = trimmed;
  let n = 2;
  while (names.has(suggested)) {
    suggested = `${trimmed}_${n}`;
    n += 1;
  }
  return { collision: true, suggested };
}

async function openNewSessionModal() {
  const fields = [
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
    { name: "host", label: "Host", type: "text", default: "", placeholder: "192.168.1.1 or hostname" },
    { name: "port", label: "Port", type: "text", default: "22", placeholder: "22" },
    { name: "username", label: "Username", type: "text", default: "", placeholder: "Optional" },
    {
      name: "auth",
      label: "Auth",
      type: "select",
      default: "password",
      options: [
        { value: "password", label: "Password" },
        { value: "key", label: "Key" },
      ],
    },
    { name: "password", label: "Password", type: "password", default: "", placeholder: "Optional" },
    { name: "private_key_path", label: "Key path", type: "text", default: "", placeholder: "/home/pi/.ssh/id_rsa" },
    { name: "_divider", label: "", type: "display", default: "" },
    { name: "save_as", label: "Save as", type: "text", default: "", placeholder: "Leave blank to not save · defaults to host" },
  ];
  const form = await modalForm(fields, "Connect", {
    onOpen(overlay) {
      const typeSelect = overlay.querySelector("#modal-form-type");
      const portInput = overlay.querySelector("#modal-form-port");
      const authSelect = overlay.querySelector("#modal-form-auth");
      const authRow = overlay.querySelector('[data-field-name="auth"]');
      const passwordRow = overlay.querySelector('[data-field-name="password"]');
      const keyRow = overlay.querySelector('[data-field-name="private_key_path"]');
      const saveAsInput = overlay.querySelector("#modal-form-save_as");
      const dividerRow = overlay.querySelector('[data-field-name="_divider"]');
      if (dividerRow) dividerRow.classList.add("modal-section-divider");
      const warningEl = document.createElement("div");
      warningEl.className = "modal-field-warning";
      warningEl.setAttribute("aria-live", "polite");
      saveAsInput?.closest(".field")?.appendChild(warningEl);

      function updatePort() {
        if (!typeSelect || !portInput) return;
        portInput.value = typeSelect.value === "telnet" ? "23" : "22";
      }
      function updateCredentialVisibility() {
        const isTelnet = typeSelect?.value === "telnet";
        if (authRow) authRow.hidden = isTelnet;
        if (isTelnet) {
          if (passwordRow) {
            passwordRow.hidden = false;
            const lab = passwordRow.querySelector(".field-label");
            if (lab) lab.textContent = "Password";
            const inp = passwordRow.querySelector("input");
            if (inp) inp.placeholder = "Optional";
          }
          if (keyRow) keyRow.hidden = true;
        } else {
          const isKey = authSelect?.value === "key";
          if (passwordRow) {
            passwordRow.hidden = isKey;
            const lab = passwordRow.querySelector(".field-label");
            if (lab) lab.textContent = "Password";
            const inp = passwordRow.querySelector("input");
            if (inp) inp.placeholder = "Optional";
          }
          if (keyRow) keyRow.hidden = !isKey;
        }
      }
      function updateSaveAsWarning() {
        const raw = saveAsInput?.value ?? "";
        const { collision, suggested } = getCollisionSuggest(raw);
        if (warningEl) {
          warningEl.textContent = collision ? `"${raw.trim()}" already exists. Will save as "${suggested}" unless you rename above.` : "";
        }
      }
      typeSelect?.addEventListener("change", () => {
        updatePort();
        updateCredentialVisibility();
      });
      authSelect?.addEventListener("change", updateCredentialVisibility);
      saveAsInput?.addEventListener("blur", updateSaveAsWarning);
      updatePort();
      updateCredentialVisibility();
    },
  });
  if (!form) return;
  const host = (form.host || "").trim();
  if (!host) {
    showToast("Host is required.", "error");
    return;
  }
  const port = parseInt(form.port, 10) || 22;
  const type = (form.type || "ssh").toLowerCase();
  const isTelnet = type === "telnet";
  const auth = form.auth || "password";
  const username = (form.username || "").trim() || undefined;
  const payload = { host, port, type, username };
  if (isTelnet || auth === "password") {
    if (form.password) payload.password = form.password;
  }
  const label = (isTelnet ? "Telnet" : "SSH") + " " + host + ":" + port;
  let resolvedName = null;
  const saveAsTrimmed = (form.save_as || "").trim();
  if (saveAsTrimmed) {
    const { collision, suggested } = getCollisionSuggest(saveAsTrimmed);
    resolvedName = collision ? suggested : saveAsTrimmed;
  }
  if (resolvedName) {
    try {
      await apiPost("/api/v1/remote-console/targets", {
        host,
        port,
        type,
        friendly_name: resolvedName,
        username,
        auth_type: !isTelnet && auth === "key" ? "key" : undefined,
        private_key_path: !isTelnet && auth === "key" && form.private_key_path ? form.private_key_path.trim() : undefined,
      }, { timeoutMs: REMOTE_API_TIMEOUT_MS });
      showToast("Connection saved.", "success");
      await loadTargets();
      renderTargets();
    } catch (e) {
      showToast(e?.message || "Unable to save connection.", "error");
      return;
    }
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

async function loadTargets() {
  try {
    const payload = await apiGet("/api/v1/remote-console/targets", { timeoutMs: REMOTE_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    targetCache = data.targets || [];
  } catch {
    targetCache = [];
    showToast("Unable to load connections.", "error");
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
  await loadTargets();
  await loadSessions();
  renderTargets();
}

init();

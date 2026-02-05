import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalPrompt, modalConfirm } from "../modal.js";

const SYNTAX_STORAGE_KEY = "rpi-serial-syntax";
const CUSTOM_RULES_KEY = "rpi-serial-syntax-custom";

const CISCO_RULES = [
  { pattern: /^[^\s]+(>|#|\(config[^)]*\)#)/gm, class: "sh-prompt" },
  { pattern: /% (Invalid|Error|Incomplete|Ambiguous)[^\n]*/g, class: "sh-error" },
  { pattern: /\b(show|configure|interface|enable|disable|exit|end|no|copy|ping|traceroute|telnet|ssh|write|reload)\b/g, class: "sh-command" },
  { pattern: /\b(ip |ipv6 |access-list|router |vlan |line |hostname |logging )/g, class: "sh-config" },
  { pattern: /(up|down|administratively down)/g, class: "sh-status" },
];

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getCustomRules() {
  try {
    const raw = localStorage.getItem(CUSTOM_RULES_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((r) => r?.pattern && r?.class) : [];
  } catch {
    return [];
  }
}

async function openCustomSyntaxModal(state) {
  const rules = getCustomRules();
  const json = JSON.stringify(rules, null, 2);
  const result = await modalForm(
    [
      {
        name: "rules",
        label: "Custom regex rules (JSON array)",
        type: "textarea",
        default: json,
      },
      {
        name: "help",
        label: "Example",
        type: "display",
        default: '[{"pattern": "\\\\b(show|config)\\\\b", "class": "sh-command", "flags": "g"}]',
      },
    ],
    "Custom syntax highlighting"
  );
  if (!result) return;
  let arr;
  try {
    arr = JSON.parse(result.rules || "[]");
    if (!Array.isArray(arr)) throw new Error("Must be an array");
    arr = arr.filter((r) => r && typeof r.pattern === "string" && typeof r.class === "string");
  } catch (e) {
    showToast("Invalid JSON: " + (e?.message || "parse error"), "error");
    return;
  }
  saveCustomRules(arr);
  state.syntaxRules = getSyntaxRules("custom");
  const html = applySyntaxHighlighting(state.terminalBuffer.join("\n"), state.syntaxRules);
  if (state.terminalEl) state.terminalEl.innerHTML = html || "Click here to focus, then type to send data.";
  scrollConsoleToBottom(state);
  showToast("Custom rules saved.", "success");
}

function saveCustomRules(rules) {
  try {
    localStorage.setItem(CUSTOM_RULES_KEY, JSON.stringify(rules));
  } catch {
    /* ignore */
  }
}

function getSyntaxRules(mode) {
  if (mode === "cisco") return CISCO_RULES;
  if (mode === "custom") {
    const custom = getCustomRules();
    return custom.map((r) => ({ pattern: new RegExp(r.pattern, r.flags || "g"), class: r.class }));
  }
  return [];
}

function applySyntaxHighlighting(text, rules) {
  if (!text || !rules?.length) return escapeHtml(text);
  let out = escapeHtml(text);
  for (const { pattern, class: cls } of rules) {
    out = out.replace(pattern, (m) => `<span class="${cls}">${m}</span>`);
  }
  return out;
}

const elements = {
  deviceListBody: document.getElementById("serial-device-list-body"),
  consoleTabs: document.getElementById("serial-console-tabs"),
  consolePanels: document.getElementById("serial-console-panels"),
  consoleEmpty: document.getElementById("serial-console-empty"),
  banner: document.getElementById("serial-connection-banner"),
  logsTable: document.getElementById("serial-logs-table-body"),
};

let activeSessions = [];
let deviceCache = [];
const MAX_TERMINAL_LINES = 100;
let lastNotConnectedToast = 0;

const sessionMap = new Map();
let activeTabSessionId = null;

function showToast(message, variant = "info") {
  const toastRegion = document.getElementById("toast-region");
  if (!toastRegion) return;
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function getSessionForDevice(deviceId) {
  return activeSessions.find((s) => s.device_id === deviceId);
}

function getSessionState(sessionId) {
  return sessionMap.get(sessionId);
}

function isSessionWsConnected(sessionId) {
  const state = sessionMap.get(sessionId);
  return state && state.wsStatus === "connected";
}

function deviceDisplayName(device) {
  const name = device.friendly_name || device.path || device.id || "";
  if (!name || name.toLowerCase() === "n/a") {
    return device.path || device.id || "Serial Device";
  }
  return name;
}

function updateConsoleEmptyState() {
  if (!elements.consoleEmpty) return;
  const hasTabs = sessionMap.size > 0;
  elements.consoleEmpty.classList.toggle("is-visible", !hasTabs);
  if (elements.consolePanels) {
    elements.consolePanels.style.display = hasTabs ? "block" : "none";
  }
}

function renderDevices(devices) {
  if (!elements.deviceListBody) return;
  const validDevices = (devices || []).filter(
    (d) => d && (d.id || d.path) && String(d.id || d.path).trim()
  );
  deviceCache = validDevices;
  elements.deviceListBody.textContent = "";

  if (!validDevices.length) {
    const p = document.createElement("p");
    p.className = "empty-state";
    p.textContent = "No serial devices detected.";
    elements.deviceListBody.appendChild(p);
    return;
  }

  validDevices.forEach((device) => {
    const session = getSessionForDevice(device.id);
    const state = session ? sessionMap.get(session.session_id) : null;
    const wsStatus = state?.wsStatus || "";
    const isWsConnected = session && isSessionWsConnected(session.session_id);
    const deviceStatus = device.status || "unknown";
    const item = document.createElement("div");
    item.className = "device-item";
    const name = deviceDisplayName(device);
    const chipset = device.chipset || "Unknown";

    const nameEl = document.createElement("div");
    nameEl.className = "device-name";
    nameEl.textContent = name;
    item.appendChild(nameEl);

    const metaEl = document.createElement("div");
    metaEl.className = "device-meta";
    metaEl.textContent = `${chipset} · ${statusLabel(deviceStatus, !!session, isWsConnected, wsStatus)}`;
    item.appendChild(metaEl);

    const actions = document.createElement("div");
    actions.className = "device-actions";
    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    if (session) {
      toggleBtn.className = "btn btn-secondary btn-sm";
      toggleBtn.textContent = "Disconnect";
      toggleBtn.addEventListener("click", () => disconnectDevice(session.session_id));
    } else {
      toggleBtn.className = "btn btn-primary btn-sm";
      toggleBtn.textContent = "Connect";
      toggleBtn.disabled = deviceStatus === "in_use";
      toggleBtn.addEventListener("click", () => connectDevice(device.id));
    }
    const configBtn = document.createElement("button");
    configBtn.className = "btn btn-ghost btn-sm";
    configBtn.textContent = "Configure";
    configBtn.type = "button";
    configBtn.addEventListener("click", () => configureSerial(device.id));
    actions.append(toggleBtn, configBtn);
    item.appendChild(actions);
    elements.deviceListBody.appendChild(item);
  });
}

function statusLabel(deviceStatus, hasSession, isWsConnected, wsStatus) {
  if (isWsConnected) return "Connected";
  if (hasSession && wsStatus === "connecting") return "Connecting";
  if (hasSession) return "Session active";
  if (deviceStatus === "in_use") return "In use";
  if (deviceStatus === "available") return "Available";
  return "Disconnected";
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) return;
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function ensureTerminalLine(state) {
  if (state.terminalBuffer.length === 0) state.terminalBuffer.push("");
}

function processReceivedChar(state, c, i, s) {
  ensureTerminalLine(state);
  const line = state.terminalBuffer[state.terminalBuffer.length - 1];
  if (c === "\n") {
    state.terminalBuffer.push("");
  } else if (c === "\r") {
    if (i + 1 < s.length && s[i + 1] === "\n") {
      state.terminalBuffer.push("");
      return 1;
    }
    state.terminalBuffer[state.terminalBuffer.length - 1] = "";
  } else if (c === "\x7f" || c === "\x08") {
    if (line.length > 0) {
      state.terminalBuffer[state.terminalBuffer.length - 1] = line.slice(0, -1);
    }
  } else if (c === "\t") {
    state.terminalBuffer[state.terminalBuffer.length - 1] += "    ";
  } else if (c >= " " || c === "\t") {
    state.terminalBuffer[state.terminalBuffer.length - 1] += c;
  }
  return 0;
}

function updateTerminalForSession(sessionId, text) {
  const state = sessionMap.get(sessionId);
  if (!state || !state.terminalEl) return;
  const s = String(text);
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    const skip = processReceivedChar(state, c, i, s);
    if (skip) i += skip;
  }
  if (state.terminalBuffer.length > MAX_TERMINAL_LINES) {
    state.terminalBuffer = state.terminalBuffer.slice(-MAX_TERMINAL_LINES);
  }
  const html = applySyntaxHighlighting(state.terminalBuffer.join("\n"), state.syntaxRules);
  state.terminalEl.innerHTML = html;
  scrollConsoleToBottom(state);
}

function appendLocalEchoForSession(sessionId, char) {
  const state = sessionMap.get(sessionId);
  if (!state || !state.terminalEl) return;
  ensureTerminalLine(state);
  if (char === "\n") {
    state.terminalBuffer.push("");
  } else if (char === "\x7f" || char === "\x08") {
    const line = state.terminalBuffer[state.terminalBuffer.length - 1];
    if (line.length > 0) {
      state.terminalBuffer[state.terminalBuffer.length - 1] = line.slice(0, -1);
    }
  } else if (char === "\t") {
    state.terminalBuffer[state.terminalBuffer.length - 1] += "    ";
  } else {
    state.terminalBuffer[state.terminalBuffer.length - 1] += char;
  }
  if (state.terminalBuffer.length > MAX_TERMINAL_LINES) {
    state.terminalBuffer = state.terminalBuffer.slice(-MAX_TERMINAL_LINES);
  }
  const html = applySyntaxHighlighting(state.terminalBuffer.join("\n"), state.syntaxRules);
  state.terminalEl.innerHTML = html;
  scrollConsoleToBottom(state);
}

function scrollConsoleToBottom(state) {
  if (state?.wrapperEl) {
    state.wrapperEl.scrollTop = state.wrapperEl.scrollHeight;
  }
}

function createTabAndConnect(sessionId, deviceId, deviceName) {
  if (sessionMap.has(sessionId)) return sessionMap.get(sessionId);

  const syntaxMode = () => (typeof localStorage !== "undefined" ? localStorage.getItem(SYNTAX_STORAGE_KEY) || "none" : "none");
  const state = {
    sessionId,
    deviceId,
    deviceName,
    wsClient: null,
    wsStatus: "",
    terminalBuffer: [],
    localEcho: false,
    syntaxRules: getSyntaxRules(syntaxMode()),
    tabEl: null,
    tabPanelEl: null,
    terminalEl: null,
    inputEl: null,
    statusEl: null,
    wrapperEl: null,
  };
  sessionMap.set(sessionId, state);

  const tab = document.createElement("button");
  tab.type = "button";
  tab.className = "console-tab";
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", "false");
  tab.dataset.sessionId = sessionId;
  tab.innerHTML = `<span>${deviceName}</span><span class="console-tab-close" aria-label="Close">×</span>`;
  tab.querySelector(".console-tab-close").addEventListener("click", (e) => {
    e.stopPropagation();
    disconnectDevice(sessionId);
  });
  tab.addEventListener("click", () => switchTab(sessionId));
  state.tabEl = tab;

  const panel = document.createElement("div");
  panel.className = "console-tab-panel";
  panel.dataset.sessionId = sessionId;
  panel.setAttribute("role", "tabpanel");
  state.tabPanelEl = panel;

  const controls = document.createElement("div");
  controls.className = "console-controls";
  const clearBtn = document.createElement("button");
  clearBtn.className = "btn btn-secondary btn-sm";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", () => {
    state.terminalBuffer = [];
    if (state.terminalEl) {
      state.terminalEl.textContent = "Click here to focus, then type to send data.";
    }
  });
  const breakBtn = document.createElement("button");
  breakBtn.className = "btn btn-secondary btn-sm";
  breakBtn.textContent = "Break";
  breakBtn.title = "Send break signal";
  breakBtn.addEventListener("click", () => sendBreakForSession(sessionId));
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-secondary btn-sm";
  saveBtn.textContent = "Save Log";
  saveBtn.addEventListener("click", () => saveSerialLogForSession(sessionId));
  const syntaxSelect = document.createElement("select");
  syntaxSelect.className = "select serial-syntax-select";
  syntaxSelect.title = "Syntax highlighting";
  syntaxSelect.innerHTML = '<option value="none">None</option><option value="cisco">Cisco</option><option value="custom">Custom</option>';
  syntaxSelect.value = syntaxMode();
  const syntaxConfigBtn = document.createElement("button");
  syntaxConfigBtn.type = "button";
  syntaxConfigBtn.className = "btn btn-ghost btn-sm";
  syntaxConfigBtn.textContent = "Configure";
  syntaxConfigBtn.title = "Edit custom regex rules";
  syntaxConfigBtn.style.display = syntaxSelect.value === "custom" ? "inline-block" : "none";
  syntaxSelect.addEventListener("change", (e) => {
    const mode = e.target.value;
    try {
      localStorage.setItem(SYNTAX_STORAGE_KEY, mode);
    } catch {
      /* ignore */
    }
    syntaxConfigBtn.style.display = mode === "custom" ? "inline-block" : "none";
    state.syntaxRules = getSyntaxRules(mode);
    const html = applySyntaxHighlighting(state.terminalBuffer.join("\n"), state.syntaxRules);
    if (state.terminalEl) state.terminalEl.innerHTML = html || "Click here to focus, then type to send data.";
    scrollConsoleToBottom(state);
  });
  syntaxConfigBtn.addEventListener("click", () => openCustomSyntaxModal(state));
  const syntaxLabel = document.createElement("label");
  syntaxLabel.className = "field";
  syntaxLabel.innerHTML = '<span class="field-label">Syntax</span>';
  syntaxLabel.append(syntaxSelect, syntaxConfigBtn);
  const echoLabel = document.createElement("label");
  echoLabel.className = "field checkbox-field";
  echoLabel.title = "Enable if the device does not echo typed characters";
  echoLabel.innerHTML = '<input type="checkbox" class="serial-local-echo" /><span class="field-label">Local echo</span>';
  echoLabel.querySelector("input").addEventListener("change", (e) => {
    state.localEcho = e.target.checked;
  });
  controls.append(clearBtn, breakBtn, saveBtn, syntaxLabel, echoLabel);
  panel.appendChild(controls);

  const status = document.createElement("div");
  status.className = "console-status status-disconnected";
  status.textContent = "Connecting...";
  state.statusEl = status;
  panel.appendChild(status);

  const wrapper = document.createElement("div");
  wrapper.className = "console-window-wrapper";
  state.wrapperEl = wrapper;
  const terminal = document.createElement("div");
  terminal.className = "console-window";
  terminal.textContent = "Click here to focus, then type to send data.";
  state.terminalEl = terminal;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "console-input-overlay";
  input.setAttribute("aria-label", "Serial console input");
  input.autocomplete = "off";
  input.autocapitalize = "off";
  input.autocorrect = "off";
  input.spellcheck = false;
  state.inputEl = input;
  wrapper.append(terminal, input);
  panel.appendChild(wrapper);

  elements.consoleTabs?.appendChild(tab);
  elements.consolePanels?.appendChild(panel);

  setupTerminalInputForSession(state);
  switchTab(sessionId);
  updateConsoleEmptyState();

  state.wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, { autoReconnect: false });
  state.wsClient.onStatus((status) => {
    state.wsStatus = status;
    if (state.statusEl) {
      state.statusEl.textContent = status;
      state.statusEl.className = "console-status status-" + status;
    }
    if (status === "connected") {
      updateBanner("Serial console connected.", false);
    }
    if (status === "disconnected" || status === "error") {
      state.wsClient = null;
      state.wsStatus = "";
    }
    renderDevices(deviceCache);
  });
  state.wsClient.on("data", (message) => {
    updateTerminalForSession(sessionId, message.data || "");
  });
  state.wsClient.on("status", (message) => {
    if (state.statusEl) {
      const tx = message.bytes_tx || 0;
      const rx = message.bytes_rx || 0;
      state.statusEl.textContent = `Tx ${tx} / Rx ${rx}`;
      state.statusEl.title = tx > 0 && rx === 0
        ? "No output yet. Verify baud rate in Configure if the device should respond."
        : "";
    }
  });
  state.wsClient.on("error", (message) => {
    showToast(message?.message || "Serial connection error.", "error");
  });
  state.wsClient.connect();
  state.inputEl?.focus();

  return state;
}

function setupTerminalInputForSession(state) {
  const input = state.inputEl;
  const wrapper = state.wrapperEl;
  const sessionId = state.sessionId;
  if (!input || !wrapper) return;
  wrapper.tabIndex = 0;
  input.addEventListener("keydown", (event) => {
    const char = charFromKeyEvent(event);
    if (char !== null) {
      event.preventDefault();
      event.stopPropagation();
      if (sendToSerialForSession(sessionId, char)) {
        if (state.localEcho) appendLocalEchoForSession(sessionId, char);
      }
    }
  });
  input.addEventListener("wheel", (e) => {
    wrapper.scrollTop += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  wrapper.addEventListener("click", () => input?.focus());
}

function switchTab(sessionId) {
  activeTabSessionId = sessionId;
  sessionMap.forEach((state, sid) => {
    const isActive = sid === sessionId;
    state.tabEl?.classList.toggle("is-active", isActive);
    state.tabEl?.setAttribute("aria-selected", isActive ? "true" : "false");
    state.tabPanelEl?.classList.toggle("is-active", isActive);
  });
  const state = sessionMap.get(sessionId);
  state?.inputEl?.focus();
}

function removeTabAndDisconnect(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state) return;
  if (state.wsClient) {
    state.wsClient.close();
    state.wsClient = null;
  }
  state.tabEl?.remove();
  state.tabPanelEl?.remove();
  sessionMap.delete(sessionId);
  if (activeTabSessionId === sessionId) {
    activeTabSessionId = sessionMap.size > 0 ? Array.from(sessionMap.keys())[0] : null;
    if (activeTabSessionId) switchTab(activeTabSessionId);
  }
  updateConsoleEmptyState();
  renderDevices(deviceCache);
}

function charFromKeyEvent(event) {
  if (event.ctrlKey || event.metaKey) {
    const c = event.key.toLowerCase();
    if (c >= "a" && c <= "z") return String.fromCharCode(c.charCodeAt(0) - 96);
    if (c === "@") return "\x00";
    if (c === "[") return "\x1b";
    if (c === "\\") return "\x1c";
    if (c === "]") return "\x1d";
    if (c === "^" || c === "6") return "\x1e";
    if (c === "_" || c === "-") return "\x1f";
  }
  if (event.key === "Enter") return "\n";
  if (event.key === "Backspace") return "\x7f";
  if (event.key === "Tab") return "\t";
  if (event.key.length === 1) return event.key;
  return null;
}

function sendBreakForSession(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state?.wsClient?.send) return;
  const sent = state.wsClient.send({ type: "control", action: "break", duration: 0.25 });
  if (sent) showToast("Break signal sent.", "info");
  else showToast("Not connected.", "error");
}

function sendToSerialForSession(sessionId, data) {
  const state = sessionMap.get(sessionId);
  if (!state?.wsClient) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Not connected.", "error");
    }
    return false;
  }
  const sent = state.wsClient.send({ type: "data", data });
  if (!sent) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Connection not ready.", "error");
    }
    return false;
  }
  return true;
}

async function connectDevice(deviceId) {
  try {
    await closeAllSessions();
    Array.from(sessionMap.keys()).forEach((sid) => removeTabAndDisconnect(sid));
    activeSessions = [];
    renderDevices(deviceCache);
    const payload = await apiPost("/api/v1/serial/sessions", {
      device_id: deviceId,
      config: {},
    });
    const data = extractData(payload) || {};
    const sessionId = data.session_id;
    const deviceName = deviceDisplayName(deviceCache.find((d) => d.id === deviceId) || { id: deviceId });
    showToast("Session created.", "success");
    activeSessions.push({ session_id: sessionId, device_id: deviceId });
    renderDevices(deviceCache);
    await loadSessions();
    createTabAndConnect(sessionId, deviceId, deviceName);
    renderDevices(deviceCache);
  } catch (error) {
    activeSessions = activeSessions.filter((s) => s.device_id !== deviceId);
    renderDevices(deviceCache);
    showToast(error?.message || "Unable to create session.", "error");
  }
}

async function disconnectDevice(sessionId) {
  if (!sessionId) return;
  removeTabAndDisconnect(sessionId);
  try {
    await apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(sessionId)}`);
    showToast("Session closed.", "success");
  } catch (err) {
    if (String(err?.message || "").includes("404")) {
      showToast("Session closed.", "success");
    } else {
      showToast("Unable to close session.", "error");
    }
  }
  await loadSessions();
}

async function configureSerial(deviceId) {
  const devices = deviceCache.length ? deviceCache : [];
  if (!devices.length) {
    showToast("No serial devices available.", "error");
    return;
  }
  const targetId = deviceId || devices[0]?.id || "";
  const device = devices.find((d) => d.id === targetId) || devices[0];
  const form = await modalForm(
    [
      { name: "device_id", label: "Device ID to configure", default: device?.id || "" },
      { name: "friendly_name", label: "Friendly name (optional)", default: device?.friendly_name || "" },
      { name: "baud_rate", label: "Baud rate", default: String(device?.baud_rate || 9600) },
      { name: "data_bits", label: "Data bits", default: "8" },
      { name: "parity", label: "Parity (none/even/odd)", default: "none" },
      { name: "stop_bits", label: "Stop bits", default: "1" },
    ],
    "Configure serial device"
  );
  if (!form) return;
  const { device_id: devId, friendly_name: friendlyName, baud_rate: baudRate, data_bits: dataBits, parity: parity, stop_bits: stopBits } = form;
  if (!devId.trim()) {
    showToast("Device ID is required.", "error");
    return;
  }
  const payload = {
    device_id: devId.trim(),
    baud_rate: Number(baudRate) || 9600,
    data_bits: Number(dataBits) || 8,
    parity: (parity || "none").toLowerCase(),
    stop_bits: Number(stopBits) || 1,
  };
  if (friendlyName.trim()) payload.friendly_name = friendlyName;
  try {
    await apiPut("/api/v1/serial/devices/configure", payload);
    showToast("Serial device updated.", "success");
    loadDevices();
  } catch {
    showToast("Unable to update device.", "error");
  }
}

async function saveSerialLogForSession(sessionId) {
  if (!sessionId) {
    showToast("Select a session first.", "error");
    return;
  }
  try {
    const payload = await apiGet(`/api/v1/serial/logs/${encodeURIComponent(sessionId)}/content`);
    const data = extractData(payload) || {};
    const content = data.content || "";
    downloadText(`serial-${sessionId}.log`, content);
    showToast("Log downloaded.", "success");
  } catch {
    showToast("Unable to download log.", "error");
  }
}

function formatDuration(seconds) {
  if (seconds == null || seconds < 0) return "--";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatSize(bytes) {
  if (bytes == null) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function renderLogs(logs) {
  if (!elements.logsTable) return;
  elements.logsTable.textContent = "";
  if (!logs.length) {
    const row = document.createElement("tr");
    row.appendChild(document.createElement("td"));
    row.cells[0].colSpan = 6;
    row.cells[0].textContent = "No recorded sessions.";
    elements.logsTable.appendChild(row);
    return;
  }
  logs.forEach((log) => {
    const row = document.createElement("tr");
    [log.name || log.id, log.device || "--", formatDate(log.created || log.modified), formatDuration(log.duration_seconds), formatSize(log.size_bytes)].forEach((v) => {
      const cell = document.createElement("td");
      cell.textContent = v || "--";
      row.appendChild(cell);
    });
    const actionCell = document.createElement("td");
    const renameBtn = document.createElement("button");
    renameBtn.className = "btn btn-ghost btn-sm";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", () => renameLog(log.id));
    const exportBtn = document.createElement("button");
    exportBtn.className = "btn btn-secondary btn-sm";
    exportBtn.textContent = "Export";
    exportBtn.addEventListener("click", () => exportLog(log.id));
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost btn-sm";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => deleteLog(log.id));
    actionCell.append(renameBtn, exportBtn, deleteBtn);
    row.appendChild(actionCell);
    elements.logsTable.appendChild(row);
  });
}

async function renameLog(logId) {
  const name = await modalPrompt("New name", logId, { label: "Name" });
  if (name === null || !name.trim()) return;
  try {
    await apiPut(`/api/v1/serial/logs/${encodeURIComponent(logId)}`, { name: name.trim() });
    showToast("Log renamed.", "success");
    loadLogs();
  } catch {
    showToast("Unable to rename log.", "error");
  }
}

async function deleteLog(logId) {
  const confirmed = await modalConfirm(`Delete session log "${logId}"? This cannot be undone.`);
  if (!confirmed) return;
  try {
    await apiDelete(`/api/v1/serial/logs/${encodeURIComponent(logId)}`);
    showToast("Log deleted.", "success");
    loadLogs();
  } catch {
    showToast("Unable to delete log.", "error");
  }
}

async function exportLog(logId) {
  try {
    const payload = await apiPost("/api/v1/serial/logs/export", { log_ids: [logId] });
    const data = extractData(payload) || {};
    const archiveName = (data.archive || "").split(/[/\\]/).pop();
    if (archiveName) {
      window.location.assign(`/api/v1/serial/logs/export/${archiveName}`);
      showToast("Export started.", "success");
    }
  } catch {
    showToast("Unable to export log.", "error");
  }
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

async function loadDevices() {
  try {
    const payload = await apiGet("/api/v1/serial/devices");
    const data = extractData(payload) || {};
    renderDevices(data.devices || []);
  } catch {
    showToast("Unable to load serial devices.", "error");
  }
}

async function loadSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions");
    const data = extractData(payload) || {};
    const apiSessions = data.sessions || [];
    const apiIds = new Set(apiSessions.map((s) => s.session_id));
    const kept = activeSessions.filter((s) => !apiIds.has(s.session_id));
    activeSessions = [...apiSessions, ...kept];
    sessionMap.forEach((st, sessionId) => {
      if (!activeSessions.some((s) => s.session_id === sessionId)) {
        activeSessions.push({ session_id: sessionId, device_id: st.deviceId });
      }
    });
    renderDevices(deviceCache);
    activeSessions.forEach((session) => {
      if (!sessionMap.has(session.session_id)) {
        const deviceName = deviceDisplayName(deviceCache.find((d) => d.id === session.device_id) || { id: session.device_id });
        createTabAndConnect(session.session_id, session.device_id, deviceName);
      }
    });
    const toRemove = [];
    sessionMap.forEach((st, sid) => {
      if (!activeSessions.some((s) => s.session_id === sid)) {
        toRemove.push(sid);
      }
    });
    toRemove.forEach((sid) => removeTabAndDisconnect(sid));
    renderDevices(deviceCache);
  } catch {
    showToast("Unable to load serial sessions.", "error");
  }
}

async function loadLogs() {
  try {
    const payload = await apiGet("/api/v1/serial/logs");
    const data = extractData(payload) || {};
    renderLogs(data.logs || []);
  } catch {
    showToast("Unable to load serial logs.", "error");
  }
}

async function closeAllSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions");
    const data = extractData(payload) || {};
    const sessions = data.sessions || [];
    for (const s of sessions) {
      try {
        await apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(s.session_id)}`);
      } catch {
        /* ignore per-session errors */
      }
    }
  } catch {
    /* ignore */
  }
}

function init() {
  const refresh = document.getElementById("refresh-serial");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadDevices();
      loadSessions();
      loadLogs();
    });
  }
  (async () => {
    await closeAllSessions();
    loadDevices();
    loadSessions();
    loadLogs();
  })();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  sessionMap.forEach((state) => state.wsClient?.close());
});

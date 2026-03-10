import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalPrompt, modalConfirm } from "../modal.js";

const SYNTAX_STORAGE_KEY = "rpi-serial-syntax";
const CUSTOM_RULES_KEY = "rpi-serial-syntax-custom";
const CONSOLE_LINES_KEY = "rpi-serial-console-lines";
const DEFAULT_CONSOLE_LINES = 24;
const CONSOLE_LINE_OPTIONS = [16, 24, 32, 48, 96];
const CONSOLE_LINE_HEIGHT_REM = 1.26;
const CONSOLE_PADDING_REM = 2;

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

function getConsoleLines() {
  try {
    const n = parseInt(localStorage.getItem(CONSOLE_LINES_KEY), 10);
    return CONSOLE_LINE_OPTIONS.includes(n) ? n : DEFAULT_CONSOLE_LINES;
  } catch {
    return DEFAULT_CONSOLE_LINES;
  }
}

function applyConsoleLinesHeight(state) {
  if (!state?.wrapperEl) return;
  const lines = state.consoleLines ?? getConsoleLines();
  state.wrapperEl.style.height = `${CONSOLE_PADDING_REM + lines * CONSOLE_LINE_HEIGHT_REM}rem`;
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

const SERIAL_API_TIMEOUT_MS = 60000;

// Resolve from document on each access so tests (or DOM changes) always see current nodes.
const elements = {
  get deviceList() {
    return document.getElementById("serial-device-list");
  },
  get listPlaceholder() {
    return document.getElementById("serial-list-placeholder");
  },
  get detailEmpty() {
    return document.getElementById("serial-detail-empty");
  },
  get detailContent() {
    return document.getElementById("serial-detail-content");
  },
  get emptyConnectBtn() {
    return document.getElementById("serial-empty-connect");
  },
  get emptyConfigureBtn() {
    return document.getElementById("serial-empty-configure");
  },
  get consoleTabs() {
    return document.getElementById("serial-console-tabs");
  },
  get consolePanels() {
    return document.getElementById("serial-console-panels");
  },
  get logsTable() {
    return document.getElementById("serial-logs-table-body");
  },
};

let activeSessions = [];
let deviceCache = [];
let serialLogsCache = [];
let logsPageSize = 10;
let logsPageIndex = 0;
const MAX_TERMINAL_LINES = 100;
const LOGS_PAGE_SIZES = [10, 25, 50];
let lastNotConnectedToast = 0;
let connectingDeviceId = null;

const sessionMap = new Map();
let activeTabSessionId = null;
let selectedDeviceId = null;

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
  const path = device.path || device.id || "";
  const name = device.friendly_name || path || "";
  if (!name || name.toLowerCase() === "n/a") {
    return path || "Serial Device";
  }
  return path && path !== name ? `${name} (${path})` : name;
}

function updateConsoleEmptyState() {
  const hasSessions = sessionMap.size > 0;
  const detailEmpty = elements.detailEmpty;
  const detailContent = elements.detailContent;
  const emptyConnectBtn = elements.emptyConnectBtn;
  if (detailEmpty) {
    detailEmpty.hidden = hasSessions;
  }
  if (detailContent) {
    detailContent.hidden = !hasSessions;
  }
  if (emptyConnectBtn) {
    const showConnect = !hasSessions && selectedDeviceId;
    emptyConnectBtn.hidden = !showConnect;
  }
  const emptyConfigureBtn = elements.emptyConfigureBtn;
  if (emptyConfigureBtn) {
    emptyConfigureBtn.hidden = !selectedDeviceId;
  }
}

function selectDevice(deviceId) {
  selectedDeviceId = deviceId;
  updateListSelection();
  updateConsoleEmptyState();
  setupEmptyStateButtons();
  const session = deviceId ? getSessionForDevice(deviceId) : null;
  if (session) {
    switchTab(session.session_id);
  }
}

function updateListSelection() {
  const list = elements.deviceList;
  if (!list) return;
  list.querySelectorAll(".serial-list-item").forEach((li) => {
    const id = li.dataset.deviceId;
    li.classList.toggle("is-active", id === selectedDeviceId);
    li.setAttribute("aria-selected", id === selectedDeviceId ? "true" : "false");
  });
}

function setupEmptyStateButtons() {
  const connectBtn = elements.emptyConnectBtn;
  if (connectBtn) {
    connectBtn.onclick = () => {
      if (selectedDeviceId) connectDevice(selectedDeviceId);
    };
  }
  const configureBtn = elements.emptyConfigureBtn;
  if (configureBtn) {
    configureBtn.onclick = () => {
      if (selectedDeviceId) configureSerial(selectedDeviceId);
    };
  }
}

function renderDevices(devices) {
  const list = elements.deviceList;
  const placeholder = elements.listPlaceholder;
  if (!list) return;
  const validDevices = (devices || []).filter(
    (d) => d && (d.id || d.path) && String(d.id || d.path).trim()
  );
  deviceCache = validDevices;

  if (placeholder) placeholder.remove();

  if (!validDevices.length) {
    const li = document.createElement("li");
    li.className = "serial-list-placeholder";
    li.textContent = "No serial devices detected.";
    list.appendChild(li);
    return;
  }

  validDevices.forEach((device) => {
    const session = getSessionForDevice(device.id);
    const state = session ? sessionMap.get(session.session_id) : null;
    const isWsConnected = session && isSessionWsConnected(session.session_id);
    const isConnecting = state?.wsStatus === "connecting";
    const deviceStatus = device.status || "unknown";
    const item = document.createElement("li");
    item.className = "serial-list-item";
    item.dataset.deviceId = device.id;
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", device.id === selectedDeviceId ? "true" : "false");
    if (device.id === selectedDeviceId) item.classList.add("is-active");

    const dot = document.createElement("span");
    dot.className = "serial-list-item-dot";
    if (isWsConnected) dot.classList.add("is-connected");
    else if (isConnecting) dot.classList.add("is-connecting");
    item.appendChild(dot);

    const info = document.createElement("div");
    info.className = "serial-list-item-info";
    const nameEl = document.createElement("div");
    nameEl.className = "serial-list-item-name";
    nameEl.textContent = deviceDisplayName(device);
    const subtitleEl = document.createElement("div");
    subtitleEl.className = "serial-list-item-subtitle";
    const path = device.path || device.id || "";
    const pathPart = path ? ` · ${path}` : "";
    subtitleEl.textContent = `${device.chipset || "Unknown"}${pathPart} · ${statusLabel(deviceStatus, !!session, isWsConnected, state?.wsStatus || "")}`;
    info.append(nameEl, subtitleEl);
    item.appendChild(info);

    item.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      selectDevice(device.id);
    });

    list.appendChild(item);
  });
  setupEmptyStateButtons();
}

function statusLabel(deviceStatus, hasSession, isWsConnected, wsStatus) {
  if (isWsConnected) return "Connected";
  if (hasSession && wsStatus === "connecting") return "Connecting";
  if (hasSession) return "Disconnected";
  if (deviceStatus === "in_use") return "In use";
  if (deviceStatus === "available") return "Available";
  return "Disconnected";
}

function updateSessionsMeta() {
  const el = document.getElementById("serial-sessions-meta");
  if (!el) return;
  const n = sessionMap.size;
  el.textContent = n > 0 ? `${n} active` : "";
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
    connectTimeoutId: null,
    terminalBuffer: [],
    localEcho: false,
    consoleLines: getConsoleLines(),
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
  tab.className = "tab-button";
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", "false");
  tab.dataset.sessionId = sessionId;
  tab.appendChild(document.createTextNode(deviceName));
  const closeSpan = document.createElement("span");
  closeSpan.className = "serial-tab-close";
  closeSpan.setAttribute("aria-label", "Close");
  closeSpan.textContent = "×";
  closeSpan.addEventListener("click", (e) => {
    e.stopPropagation();
    disconnectDevice(sessionId);
  });
  tab.appendChild(closeSpan);
  tab.addEventListener("click", (e) => {
    if (e.target !== closeSpan) switchTab(sessionId);
  });
  state.tabEl = tab;

  const panel = document.createElement("div");
  panel.className = "console-tab-panel console-block";
  panel.dataset.sessionId = sessionId;
  panel.setAttribute("role", "tabpanel");
  state.tabPanelEl = panel;

  const toolbar = document.createElement("div");
  toolbar.className = "console-toolbar";
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
  toolbar.append(clearBtn, breakBtn, saveBtn);

  const details = document.createElement("details");
  details.className = "console-settings";
  const summary = document.createElement("summary");
  summary.textContent = "Settings";
  details.appendChild(summary);
  const syntaxSelect = document.createElement("select");
  syntaxSelect.className = "select";
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
  const linesLabel = document.createElement("label");
  linesLabel.className = "field";
  linesLabel.innerHTML = '<span class="field-label">Console lines</span>';
  const linesSelect = document.createElement("select");
  linesSelect.className = "select";
  linesSelect.title = "Visible lines in console (fixed height)";
  CONSOLE_LINE_OPTIONS.forEach((n) => {
    const opt = document.createElement("option");
    opt.value = String(n);
    opt.textContent = String(n);
    if (n === state.consoleLines) opt.selected = true;
    linesSelect.appendChild(opt);
  });
  linesSelect.addEventListener("change", () => {
    const n = parseInt(linesSelect.value, 10);
    state.consoleLines = n;
    try {
      localStorage.setItem(CONSOLE_LINES_KEY, String(n));
    } catch {
      /* ignore */
    }
    applyConsoleLinesHeight(state);
  });
  linesLabel.appendChild(linesSelect);
  const echoLabel = document.createElement("label");
  echoLabel.className = "field checkbox-field";
  echoLabel.title = "Enable if the device does not echo typed characters";
  echoLabel.innerHTML = '<input type="checkbox" class="serial-local-echo" /><span class="field-label">Local echo</span>';
  echoLabel.querySelector("input").addEventListener("change", (e) => {
    state.localEcho = e.target.checked;
  });
  details.append(syntaxLabel, linesLabel, echoLabel);

  const side = document.createElement("div");
  side.className = "console-panel-side";
  side.append(toolbar, details);

  const status = document.createElement("div");
  status.className = "console-status status-disconnected";
  status.textContent = "Connecting...";
  state.statusEl = status;

  const body = document.createElement("div");
  body.className = "console-block-body";
  const wrapper = document.createElement("div");
  wrapper.className = "console-window-wrapper console-window-fixed-lines";
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
  body.appendChild(wrapper);
  applyConsoleLinesHeight(state);

  const main = document.createElement("div");
  main.className = "console-panel-main";
  main.append(status, body);

  const row = document.createElement("div");
  row.className = "console-panel-row";
  row.append(side, main);
  panel.appendChild(row);

  elements.consoleTabs?.appendChild(tab);
  elements.consolePanels?.appendChild(panel);

  setupTerminalInputForSession(state);
  switchTab(sessionId);
  updateConsoleEmptyState();
  updateSessionsMeta();

  state.wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, { autoReconnect: false });
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
    if (status === "connected") {
      if (activeTabSessionId === sessionId) {
        state.inputEl?.focus();
      }
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
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
  }
  state.connectTimeoutId = window.setTimeout(() => {
    if (!state.wsStatus || state.wsStatus === "connecting") {
      if (state.wsClient) {
        state.wsClient.close();
        state.wsClient = null;
      }
      state.wsStatus = "";
      if (state.statusEl) {
        state.statusEl.textContent = "Disconnected (connection timed out)";
        state.statusEl.className = "console-status status-error";
      }
      showToast(
        "Serial connection timed out. Try reconnecting or check the network and device.",
        "error"
      );
      renderDevices(deviceCache);
    }
    state.connectTimeoutId = null;
  }, 15000);
  state.inputEl?.focus();

  return state;
}

function setupTerminalInputForSession(state) {
  const input = state.inputEl;
  const wrapper = state.wrapperEl;
  const sessionId = state.sessionId;
  if (!input || !wrapper) return;
  wrapper.tabIndex = 0;
  const scrollToBottomOnFocus = () => scrollConsoleToBottom(state);
  wrapper.addEventListener("focus", scrollToBottomOnFocus);
  input.addEventListener("focus", scrollToBottomOnFocus);
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
  const state = sessionMap.get(sessionId);
  if (state?.deviceId) selectedDeviceId = state.deviceId;
  sessionMap.forEach((s, sid) => {
    const isActive = sid === sessionId;
    s.tabEl?.classList.toggle("tab-button-active", isActive);
    s.tabEl?.setAttribute("aria-selected", isActive ? "true" : "false");
    s.tabPanelEl?.classList.toggle("is-active", isActive);
  });
  updateListSelection();
  state?.inputEl?.focus();
}

function removeTabAndDisconnect(sessionId) {
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
  state.tabEl?.remove();
  state.tabPanelEl?.remove();
  sessionMap.delete(sessionId);
  if (activeTabSessionId === sessionId) {
    activeTabSessionId = sessionMap.size > 0 ? Array.from(sessionMap.keys())[0] : null;
    if (activeTabSessionId) switchTab(activeTabSessionId);
  }
  updateConsoleEmptyState();
  updateSessionsMeta();
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

function reconnectSession(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state?.tabPanelEl) return;
  if (state.wsClient) {
    state.wsClient.close();
    state.wsClient = null;
  }
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
    state.connectTimeoutId = null;
  }
  state.wsStatus = "";
  if (state.statusEl) {
    state.statusEl.textContent = "Connecting...";
    state.statusEl.className = "console-status status-connecting";
  }
  showToast("Reconnecting…", "info");
  state.wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, { autoReconnect: false });
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
    if (status === "connected") {
      showToast("Reconnected.", "success");
      if (activeTabSessionId === sessionId) {
        state.inputEl?.focus();
      }
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
  switchTab(sessionId);
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
  }
  state.connectTimeoutId = window.setTimeout(() => {
    if (!state.wsStatus || state.wsStatus === "connecting") {
      if (state.wsClient) {
        state.wsClient.close();
        state.wsClient = null;
      }
      state.wsStatus = "";
      if (state.statusEl) {
        state.statusEl.textContent = "Disconnected (connection timed out)";
        state.statusEl.className = "console-status status-error";
      }
      showToast(
        "Serial reconnection timed out. Try again or check the network and device.",
        "error"
      );
      renderDevices(deviceCache);
    }
    state.connectTimeoutId = null;
  }, 15000);
  state.inputEl?.focus();
}

async function connectDevice(deviceId) {
  connectingDeviceId = deviceId;
  renderDevices(deviceCache);
  showToast("Connecting…", "info");
  try {
    let payload;
    try {
      payload = await apiPost(
        "/api/v1/serial/sessions",
        { device_id: deviceId, config: {} },
        { timeoutMs: 20000 }
      );
    } catch (createErr) {
      const msg = String(createErr?.message || "");
      if (msg.includes("Device already in use") || msg.includes("Device already")) {
        // Device already has a session; reuse it instead of tearing everything down.
        await loadSessions();
        const existing = getSessionForDevice(deviceId);
        if (existing) {
          const deviceName = deviceDisplayName(
            deviceCache.find((d) => d.id === deviceId) || { id: deviceId }
          );
          if (!sessionMap.has(existing.session_id)) {
            createTabAndConnect(existing.session_id, deviceId, deviceName);
          }
          switchTab(existing.session_id);
          showToast("Device already connected; switched to existing session.", "info");
        } else {
          showToast(msg || "Device is already in use.", "error");
        }
        return;
      }
      if (msg.includes("Maximum sessions")) {
        showToast(
          "Maximum serial sessions reached. Close an existing session before starting a new one.",
          "error"
        );
        return;
      }
      throw createErr;
    }
    const data = extractData(payload) || {};
    const sessionId = data.session_id;
    const deviceName = deviceDisplayName(deviceCache.find((d) => d.id === deviceId) || { id: deviceId });
    showToast("Session created.", "success");
    activeSessions.push({ session_id: sessionId, device_id: deviceId });
    renderDevices(deviceCache);
    createTabAndConnect(sessionId, deviceId, deviceName);
    renderDevices(deviceCache);
  } catch (error) {
    activeSessions = activeSessions.filter((s) => s.device_id !== deviceId);
    const msg = String(error?.message || "");
    const hint = msg.includes("timed out")
      ? "Connection timed out. The device may be slow. Try again or check the serial connection."
      : msg || "Unable to create session.";
    showToast(hint, "error");
  } finally {
    connectingDeviceId = null;
    renderDevices(deviceCache);
  }
}

async function disconnectDevice(sessionId) {
  if (!sessionId) return;
  removeTabAndDisconnect(sessionId);
  activeSessions = activeSessions.filter(s => s.session_id !== sessionId);
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

function updateLogsMeta(count) {
  const el = document.getElementById("serial-logs-meta");
  if (!el) return;
  el.textContent = count > 0 ? `${count} sessions` : "";
}

function renderLogs(logsArg) {
  if (arguments.length > 0 && Array.isArray(logsArg)) {
    serialLogsCache = logsArg;
    logsPageIndex = 0;
  }
  if (!elements.logsTable) return;
  const logs = serialLogsCache;
  const total = logs.length;
  updateLogsMeta(total);

  const toolbarEl = document.getElementById("serial-logs-toolbar");
  if (toolbarEl) {
    toolbarEl.textContent = "";
    if (total > 0) {
      const perPageLabel = document.createElement("label");
      perPageLabel.className = "field";
      perPageLabel.innerHTML = '<span class="field-label">Rows per page</span>';
      const perPageSelect = document.createElement("select");
      perPageSelect.className = "select per-page-select";
      perPageSelect.setAttribute("aria-label", "Rows per page");
      LOGS_PAGE_SIZES.forEach((n) => {
        const opt = document.createElement("option");
        opt.value = String(n);
        opt.textContent = String(n);
        if (n === logsPageSize) opt.selected = true;
        perPageSelect.appendChild(opt);
      });
      perPageSelect.addEventListener("change", () => {
        logsPageSize = Number(perPageSelect.value) || 10;
        logsPageIndex = 0;
        renderLogs();
      });
      perPageLabel.appendChild(perPageSelect);
      toolbarEl.appendChild(perPageLabel);

      const totalPages = Math.max(1, Math.ceil(total / logsPageSize));
      if (logsPageIndex >= totalPages) logsPageIndex = totalPages - 1;
      const pagination = document.createElement("div");
      pagination.className = "logs-pagination";
      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "btn btn-secondary btn-sm tab-button";
      prevBtn.textContent = "Previous";
      prevBtn.disabled = logsPageIndex === 0;
      prevBtn.addEventListener("click", () => {
        if (logsPageIndex > 0) {
          logsPageIndex--;
          renderLogs();
        }
      });
      pagination.appendChild(prevBtn);
      for (let p = 0; p < totalPages; p++) {
        const pageBtn = document.createElement("button");
        pageBtn.type = "button";
        pageBtn.className = "tab-button" + (p === logsPageIndex ? " tab-button-active" : "");
        pageBtn.textContent = String(p + 1);
        pageBtn.setAttribute("aria-label", `Page ${p + 1}`);
        const page = p;
        pageBtn.addEventListener("click", () => {
          logsPageIndex = page;
          renderLogs();
        });
        pagination.appendChild(pageBtn);
      }
      const nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "btn btn-secondary btn-sm tab-button";
      nextBtn.textContent = "Next";
      nextBtn.disabled = logsPageIndex >= totalPages - 1;
      nextBtn.addEventListener("click", () => {
        if (logsPageIndex < totalPages - 1) {
          logsPageIndex++;
          renderLogs();
        }
      });
      pagination.appendChild(nextBtn);
      toolbarEl.appendChild(pagination);
    }
  }

  elements.logsTable.textContent = "";
  if (!total) {
    const row = document.createElement("tr");
    row.appendChild(document.createElement("td"));
    row.cells[0].colSpan = 6;
    row.cells[0].textContent = "No recorded sessions.";
    elements.logsTable.appendChild(row);
    return;
  }

  const start = logsPageIndex * logsPageSize;
  const pageLogs = logs.slice(start, start + logsPageSize);
  pageLogs.forEach((log) => {
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

async function loadDevices(forceRefresh = false) {
  try {
    const url = forceRefresh ? "/api/v1/serial/devices?refresh=1" : "/api/v1/serial/devices";
    const payload = await apiGet(url, { timeoutMs: SERIAL_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    renderDevices(data.devices || []);
  } catch {
    showToast("Unable to load serial devices.", "error");
  }
}

async function loadSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions", { timeoutMs: SERIAL_API_TIMEOUT_MS });
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
    serialLogsCache = data.logs || [];
    logsPageIndex = 0;
    renderLogs();
  } catch {
    showToast("Unable to load serial logs.", "error");
  }
}

async function closeAllSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions", { timeoutMs: SERIAL_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    const sessions = data.sessions || [];
    await Promise.all(
      sessions.map((s) =>
        apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(s.session_id)}`, {
          timeoutMs: SERIAL_API_TIMEOUT_MS,
        }).catch(() => {})
      )
    );
  } catch {
    /* ignore */
  }
}

async function openNewSerialSessionModal() {
  if (!deviceCache.length) {
    await loadDevices(true);
  }
  const available = deviceCache.filter((d) => {
    const status = d.status || "unknown";
    if (status === "in_use") return false;
    const session = getSessionForDevice(d.id);
    return !session || !isSessionWsConnected(session.session_id);
  });
  const options = available.map((d) => ({
    value: d.id,
    label: deviceDisplayName(d),
  }));
  if (!options.length) {
    showToast("No devices available. Refresh or disconnect an existing session.", "error");
    return;
  }
  const form = await modalForm(
    [
      {
        name: "device_id",
        label: "Device",
        type: "select",
        default: options[0].value,
        options,
      },
    ],
    "New serial session"
  );
  if (!form?.device_id) return;
  await connectDevice(form.device_id);
}

async function init() {
  const refresh = document.getElementById("refresh-serial");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadDevices(true);
      loadSessions();
      loadLogs();
    });
  }
  const newSessionBtn = document.getElementById("new-serial-session");
  if (newSessionBtn) {
    newSessionBtn.addEventListener("click", () => openNewSerialSessionModal());
  }
  await loadDevices();
  await loadSessions();
  loadLogs();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  sessionMap.forEach((state) => state.wsClient?.close());
});

// Reset module state for tests so each test starts with a clean sessionMap/activeSessions.
function resetStateForTest() {
  sessionMap.forEach((st) => {
    if (st.connectTimeoutId != null) {
      window.clearTimeout(st.connectTimeoutId);
      st.connectTimeoutId = null;
    }
    st.wsClient?.close?.();
  });
  sessionMap.clear();
  activeSessions.length = 0;
  connectingDeviceId = null;
  activeTabSessionId = null;
  selectedDeviceId = null;
  deviceCache.length = 0;
}

// Internal hooks exported for tests only. Has no effect when loaded via <script>.
export const __testHooks = {
  state: {
    get activeSessions() {
      return activeSessions;
    },
    get deviceCache() {
      return deviceCache;
    },
    get sessionMap() {
      return sessionMap;
    },
    get activeTabSessionId() {
      return activeTabSessionId;
    },
    get connectingDeviceId() {
      return connectingDeviceId;
    },
  },
  resetStateForTest,
  renderDevices,
  loadDevices,
  loadSessions,
  connectDevice,
  disconnectDevice,
  reconnectSession,
  createTabAndConnect,
  switchTab,
};

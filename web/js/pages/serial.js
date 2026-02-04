import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalPrompt, modalConfirm } from "../modal.js";

const elements = {
  deviceTable: document.getElementById("serial-device-table-body"),
  sessionSelect: document.getElementById("serial-session-select"),
  terminal: document.getElementById("terminal-placeholder"),
  terminalInput: document.getElementById("serial-terminal-input"),
  banner: document.getElementById("serial-connection-banner"),
  status: document.getElementById("serial-status"),
  logsTable: document.getElementById("serial-logs-table-body"),
};

let activeSessions = [];
let deviceCache = [];
let wsClient = null;
let currentSessionId = null;
const MAX_TERMINAL_LINES = 100;
let terminalBuffer = [];
let terminalInputReady = false;
let lastNotConnectedToast = 0;

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

function deviceDisplayName(device) {
  const name = device.friendly_name || device.path || device.id || "";
  if (!name || name.toLowerCase() === "n/a") {
    return device.path || device.id || "Serial Device";
  }
  return name;
}

function renderDevices(devices) {
  if (!elements.deviceTable) return;
  const validDevices = (devices || []).filter(
    (d) => d && (d.id || d.path) && String(d.id || d.path).trim()
  );
  deviceCache = validDevices;
  elements.deviceTable.textContent = "";

  if (!validDevices.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No serial devices detected.";
    row.appendChild(cell);
    elements.deviceTable.appendChild(row);
    return;
  }

  validDevices.forEach((device) => {
    const session = getSessionForDevice(device.id);
    const isWsConnected =
      session && currentSessionId === session.session_id && wsClient;
    const deviceStatus = device.status || "unknown";
    const row = document.createElement("tr");
    const name = deviceDisplayName(device);
    const chipset = device.chipset || "Unknown";
    const sessionInfo = session
      ? `${session.session_id.slice(0, 8)}...`
      : "--";

    const nameCell = document.createElement("td");
    nameCell.textContent = name;
    row.appendChild(nameCell);

    const statusCell = document.createElement("td");
    const statusSpan = document.createElement("span");
    statusSpan.className = "status-pill status-pill-" + statusPillClass(deviceStatus, !!session, isWsConnected);
    statusSpan.textContent = statusLabel(deviceStatus, !!session, isWsConnected);
    statusCell.appendChild(statusSpan);
    row.appendChild(statusCell);

    const chipsetCell = document.createElement("td");
    chipsetCell.textContent = chipset;
    row.appendChild(chipsetCell);

    const sessionCell = document.createElement("td");
    sessionCell.textContent = sessionInfo;
    row.appendChild(sessionCell);

    const actionCell = document.createElement("td");
    actionCell.className = "device-actions";

    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.dataset.deviceId = device.id;
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
    actionCell.appendChild(toggleBtn);

    const configBtn = document.createElement("button");
    configBtn.className = "btn btn-ghost btn-sm";
    configBtn.textContent = "Configure";
    configBtn.type = "button";
    configBtn.addEventListener("click", () => configureSerial(device.id));
    actionCell.appendChild(configBtn);

    row.appendChild(actionCell);
    elements.deviceTable.appendChild(row);
  });
}

function statusLabel(deviceStatus, hasSession, isWsConnected) {
  if (isWsConnected) return "Connected";
  if (hasSession) return "Session active";
  if (deviceStatus === "in_use") return "In use";
  if (deviceStatus === "available") return "Available";
  return "Disconnected";
}

function statusPillClass(deviceStatus, hasSession, isWsConnected) {
  if (isWsConnected) return "success";
  if (hasSession) return "info";
  if (deviceStatus === "in_use") return "warning";
  if (deviceStatus === "available") return "success";
  return "muted";
}

function renderSessionSelect() {
  if (!elements.sessionSelect) return;
  const current = elements.sessionSelect.value;
  elements.sessionSelect.textContent = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "No session selected";
  elements.sessionSelect.appendChild(empty);

  activeSessions.forEach((session) => {
    const opt = document.createElement("option");
    opt.value = session.session_id;
    const deviceName =
      deviceCache.find((d) => d.id === session.device_id)?.friendly_name ||
      session.device_id;
    opt.textContent = `${deviceName} (${session.session_id.slice(0, 8)}...)`;
    elements.sessionSelect.appendChild(opt);
  });

  if (current && activeSessions.some((s) => s.session_id === current)) {
    elements.sessionSelect.value = current;
  } else if (activeSessions.length && !current) {
    elements.sessionSelect.value = activeSessions[0].session_id;
  }
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) return;
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function ensureTerminalLine() {
  if (terminalBuffer.length === 0) terminalBuffer.push("");
}

function processReceivedChar(c, i, s) {
  ensureTerminalLine();
  const line = terminalBuffer[terminalBuffer.length - 1];
  if (c === "\n") {
    terminalBuffer.push("");
  } else if (c === "\r") {
    if (i + 1 < s.length && s[i + 1] === "\n") {
      terminalBuffer.push("");
      return 1;
    }
    terminalBuffer[terminalBuffer.length - 1] = "";
  } else if (c === "\x7f" || c === "\x08") {
    if (line.length > 0) {
      terminalBuffer[terminalBuffer.length - 1] = line.slice(0, -1);
    }
  } else if (c === "\t") {
    terminalBuffer[terminalBuffer.length - 1] += "    ";
  } else if (c >= " " || c === "\t") {
    terminalBuffer[terminalBuffer.length - 1] += c;
  }
  return 0;
}

function updateTerminal(text) {
  if (!elements.terminal) return;
  const s = String(text);
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    const skip = processReceivedChar(c, i, s);
    if (skip) i += skip;
  }
  if (terminalBuffer.length > MAX_TERMINAL_LINES) {
    terminalBuffer = terminalBuffer.slice(-MAX_TERMINAL_LINES);
  }
  elements.terminal.textContent = terminalBuffer.join("\n");
  elements.terminal.scrollTop = elements.terminal.scrollHeight;
}

function connectWebSocket(sessionId) {
  if (!sessionId) {
    showToast("No session selected.", "error");
    return;
  }
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  currentSessionId = sessionId;
  wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, {
    autoReconnect: false,
  });
  wsClient.onStatus((status) => {
    if (elements.status) {
      elements.status.textContent = status;
      elements.status.className = "console-status status-" + status;
    }
    if (status === "connected") {
      updateBanner("Serial console connected.", false);
      renderDevices(deviceCache);
    } else if (status === "disconnected") {
      wsClient = null; /* Clear so device table shows "Session active" not "Connected" */
      updateBanner("Serial console disconnected.");
      renderDevices(deviceCache);
    } else if (status === "connecting") {
      updateBanner("Connecting to serial console...");
    } else if (status === "error") {
      wsClient = null; /* Clear so device table reflects failed connection */
      updateBanner("Serial console connection error.");
      renderDevices(deviceCache);
    }
  });
  wsClient.on("data", (message) => {
    updateTerminal(message.data || "");
  });
  wsClient.on("status", (message) => {
    if (elements.status) {
      const tx = message.bytes_tx || 0;
      const rx = message.bytes_rx || 0;
      elements.status.textContent = `Tx ${tx} / Rx ${rx}`;
      elements.status.title = tx > 0 && rx === 0
        ? "No output yet. Verify baud rate in Configure if the device should respond."
        : "";
    }
  });
  wsClient.on("error", (message) => {
    showToast(message?.message || "Serial connection error.", "error");
  });
  wsClient.connect();
  focusTerminal();
}

function disconnectWebSocket() {
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  currentSessionId = null;
  if (elements.status) {
    elements.status.textContent = "Disconnected";
    elements.status.className = "console-status status-disconnected";
  }
  updateBanner("Serial console disconnected.", true);
  renderDevices(deviceCache);
}

async function connectDevice(deviceId) {
  try {
    const payload = await apiPost("/api/v1/serial/sessions", {
      device_id: deviceId,
      config: {},
    });
    const data = extractData(payload) || {};
    showToast("Session created. Connect via console dropdown.", "success");
    await loadSessions();
    renderSessionSelect();
    if (elements.sessionSelect) {
      elements.sessionSelect.value = data.session_id;
      connectWebSocket(data.session_id);
    }
  } catch (error) {
    showToast(error?.message || "Unable to create session.", "error");
  }
}

async function disconnectDevice(sessionId) {
  if (!sessionId) return;
  if (currentSessionId === sessionId) {
    disconnectWebSocket();
  }
  try {
    await apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(sessionId)}`);
    showToast("Session closed.", "success");
    await loadSessions();
    renderSessionSelect();
    if (currentSessionId === sessionId) {
      currentSessionId = null;
    }
  } catch (error) {
    showToast(error?.message || "Unable to close session.", "error");
  }
}

function setupActions() {
  const sessionSelect = document.getElementById("serial-session-select");
  if (sessionSelect) {
    sessionSelect.addEventListener("change", () => {
      const sessionId = sessionSelect.value;
      if (sessionId) {
        connectWebSocket(sessionId);
      } else {
        disconnectWebSocket();
      }
    });
  }

  const actions = [
    {
      id: "serial-clear",
      action: () => {
        if (elements.terminal) {
          terminalBuffer = [];
          elements.terminal.textContent = "Click here to focus, then type to send data.";
        }
      },
    },
    { id: "serial-save-log", action: saveSerialLog },
  ];

  actions.forEach((action) => {
    const button = document.getElementById(action.id);
    if (!button) return;
    button.addEventListener("click", () => action.action());
  });
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

function sendToSerial(data) {
  if (!wsClient) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Not connected. Select a session and connect.", "error");
    }
    return false;
  }
  const sent = wsClient.send({ type: "data", data });
  if (!sent) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Connection not ready. Wait for \"Connected\" status.", "error");
    }
    return false;
  }
  return true;
}

function appendLocalEcho(char) {
  if (!elements.terminal) return;
  ensureTerminalLine();
  if (char === "\n") {
    terminalBuffer.push("");
  } else if (char === "\x7f" || char === "\x08") {
    const line = terminalBuffer[terminalBuffer.length - 1];
    if (line.length > 0) {
      terminalBuffer[terminalBuffer.length - 1] = line.slice(0, -1);
    }
  } else if (char === "\t") {
    terminalBuffer[terminalBuffer.length - 1] += "    ";
  } else {
    terminalBuffer[terminalBuffer.length - 1] += char;
  }
  if (terminalBuffer.length > MAX_TERMINAL_LINES) {
    terminalBuffer = terminalBuffer.slice(-MAX_TERMINAL_LINES);
  }
  elements.terminal.textContent = terminalBuffer.join("\n");
  elements.terminal.scrollTop = elements.terminal.scrollHeight;
}

function setupTerminalInput() {
  if (!elements.terminal || terminalInputReady) return;
  const input = elements.terminalInput;
  const wrapper = elements.terminal?.closest(".console-window-wrapper");
  if (wrapper) wrapper.tabIndex = 0;
  if (input) {
    input.addEventListener("keydown", (event) => {
      const char = charFromKeyEvent(event);
      if (char !== null) {
        event.preventDefault();
        event.stopPropagation();
        if (sendToSerial(char)) {
          appendLocalEcho(char);
        }
      }
    });
    input.addEventListener("wheel", (e) => {
      wrapper.scrollTop += e.deltaY;
      e.preventDefault();
    }, { passive: false });
    wrapper?.addEventListener("click", () => input?.focus());
  } else {
    elements.terminal.tabIndex = 0;
    elements.terminal.addEventListener("keydown", (event) => {
      const char = charFromKeyEvent(event);
      if (char !== null) {
        event.preventDefault();
        if (sendToSerial(char)) appendLocalEcho(char);
      }
    });
  }
  terminalInputReady = true;
}

function focusTerminal() {
  (elements.terminalInput || elements.terminal)?.focus();
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
      {
        name: "device_id",
        label: "Device ID to configure",
        default: device?.id || "",
      },
      {
        name: "friendly_name",
        label: "Friendly name (optional)",
        default: device?.friendly_name || "",
      },
      { name: "baud_rate", label: "Baud rate", default: String(device?.baud_rate || 9600) },
      { name: "data_bits", label: "Data bits", default: "8" },
      {
        name: "parity",
        label: "Parity (none/even/odd)",
        default: "none",
      },
      { name: "stop_bits", label: "Stop bits", default: "1" },
    ],
    "Configure serial device"
  );
  if (!form) return;
  const {
    device_id: devId,
    friendly_name: friendlyName,
    baud_rate: baudRate,
    data_bits: dataBits,
    parity: parity,
    stop_bits: stopBits,
  } = form;
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

function activeSessionId() {
  return currentSessionId || elements.sessionSelect?.value || "";
}

async function saveSerialLog() {
  const sessionId = activeSessionId();
  if (!sessionId) {
    showToast("Select a session first.", "error");
    return;
  }
  try {
    const payload = await apiGet(
      `/api/v1/serial/logs/${encodeURIComponent(sessionId)}/content`
    );
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
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

function renderLogs(logs) {
  if (!elements.logsTable) return;
  elements.logsTable.textContent = "";

  if (!logs.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.textContent = "No recorded sessions.";
    row.appendChild(cell);
    elements.logsTable.appendChild(row);
    return;
  }

  logs.forEach((log) => {
    const row = document.createElement("tr");
    const name = log.name || log.id;
    const device = log.device || "--";
    const when = formatDate(log.created || log.modified);
    const duration = formatDuration(log.duration_seconds);
    const size = formatSize(log.size_bytes);

    [name, device, when, duration, size].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });

    const actionCell = document.createElement("td");
    const renameBtn = document.createElement("button");
    renameBtn.className = "btn btn-ghost btn-sm";
    renameBtn.textContent = "Rename";
    renameBtn.type = "button";
    renameBtn.addEventListener("click", () => renameLog(log.id));

    const exportBtn = document.createElement("button");
    exportBtn.className = "btn btn-secondary btn-sm";
    exportBtn.textContent = "Export";
    exportBtn.type = "button";
    exportBtn.addEventListener("click", () => exportLog(log.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost btn-sm";
    deleteBtn.textContent = "Delete";
    deleteBtn.type = "button";
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
    await apiPut(`/api/v1/serial/logs/${encodeURIComponent(logId)}`, {
      name: name.trim(),
    });
    showToast("Log renamed.", "success");
    loadLogs();
  } catch {
    showToast("Unable to rename log.", "error");
  }
}

async function deleteLog(logId) {
  const confirmed = await modalConfirm(
    `Delete session log "${logId}"? This cannot be undone.`
  );
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
    const payload = await apiPost("/api/v1/serial/logs/export", {
      log_ids: [logId],
    });
    const data = extractData(payload) || {};
    const archivePath = data.archive || "";
    const archiveName = archivePath.split(/[/\\]/).pop();
    if (archiveName) {
      window.location.assign(`/api/v1/serial/logs/export/${archiveName}`);
      showToast("Export started.", "success");
    } else {
      showToast("Export created.", "success");
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
    activeSessions = data.sessions || [];
    renderDevices(deviceCache);
    renderSessionSelect();
    const selected = elements.sessionSelect?.value;
    if (selected && (currentSessionId !== selected || !wsClient)) {
      connectWebSocket(selected);
    }
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
    showToast("Unable to load session logs.", "error");
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
  setupActions();
  setupTerminalInput();
  loadDevices();
  loadSessions();
  loadLogs();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (wsClient) wsClient.close();
});

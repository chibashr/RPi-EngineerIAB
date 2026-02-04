import { apiGet, apiPost, apiPut, extractData } from "../api.js";
import { createStatusItem } from "../components.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalPrompt } from "../modal.js";

const elements = {
  deviceList: document.getElementById("serial-device-list"),
  sessionList: document.getElementById("serial-session-list"),
  terminal: document.getElementById("terminal-placeholder"),
  banner: document.getElementById("serial-connection-banner"),
  status: document.getElementById("serial-status"),
};

let activeSessions = [];
let wsClient = null;
let deviceCache = [];
const MAX_TERMINAL_LINES = 500;
let terminalBuffer = [];
let terminalInputReady = false;

function showToast(message, variant = "info") {
  const toastRegion = document.getElementById("toast-region");
  if (!toastRegion) {
    return;
  }
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function renderDevices(devices) {
  if (!elements.deviceList) {
    return;
  }
  deviceCache = devices;
  elements.deviceList.textContent = "";
  if (!devices.length) {
    const item = document.createElement("li");
    item.textContent = "No serial devices detected.";
    elements.deviceList.appendChild(item);
    return;
  }

  devices.forEach((device) => {
    const label = device.friendly_name || device.path || device.id;
    const value = `${device.status || "unknown"} • ${
      device.chipset || "chipset"
    }`;
    elements.deviceList.appendChild(createStatusItem(label, value));
  });
}

function renderSessions(sessions) {
  if (!elements.sessionList) {
    return;
  }
  activeSessions = sessions;
  elements.sessionList.textContent = "";
  if (!sessions.length) {
    const item = document.createElement("li");
    item.textContent = "No active sessions.";
    elements.sessionList.appendChild(item);
    return;
  }

  sessions.forEach((session) => {
    const label = session.name || session.session_id || session.device_id || "Session";
    const value = session.status || "active";
    elements.sessionList.appendChild(createStatusItem(label, value));
  });
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) {
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function updateTerminal(text) {
  if (!elements.terminal) {
    return;
  }
  const lines = String(text).split("\n");
  terminalBuffer = terminalBuffer.concat(lines);
  if (terminalBuffer.length > MAX_TERMINAL_LINES) {
    terminalBuffer = terminalBuffer.slice(-MAX_TERMINAL_LINES);
  }
  elements.terminal.textContent = terminalBuffer.join("\n");
  elements.terminal.scrollTop = elements.terminal.scrollHeight;
}

function connectWebSocket() {
  if (!activeSessions.length) {
    showToast("No active session available to connect.", "error");
    return;
  }
  const sessionId = activeSessions[0].session_id;
  if (!sessionId) {
    showToast("Session ID unavailable.", "error");
    return;
  }

  if (wsClient) {
    wsClient.close();
  }
  wsClient = createWebSocketClient(`/ws/serial/${sessionId}`);
  wsClient.onStatus((status) => {
    if (elements.status) {
      elements.status.textContent = status;
    }
    if (status === "connected") {
      updateBanner("Serial console connected.", false);
    } else if (status === "disconnected") {
      updateBanner("Serial console disconnected. Reconnecting...");
    } else if (status === "connecting") {
      updateBanner("Connecting to serial console...");
    } else if (status === "error") {
      updateBanner("Serial console connection error.");
    }
  });
  wsClient.on("data", (message) => {
    updateTerminal(message.data || "");
  });
  wsClient.on("status", (message) => {
    if (elements.status) {
      elements.status.textContent = `Tx ${message.bytes_tx || 0} / Rx ${
        message.bytes_rx || 0
      }`;
    }
  });
  wsClient.connect();
  focusTerminal();
}

function disconnectWebSocket() {
  if (wsClient) {
    wsClient.close();
    wsClient = null;
  }
  updateBanner("Serial console disconnected.", true);
}

function setupActions() {
  const actions = [
    { id: "open-console", message: "Select a session then connect." },
    { id: "configure-serial", action: configureSerial },
    { id: "serial-connect", action: connectWebSocket },
    { id: "serial-disconnect", action: disconnectWebSocket },
    { id: "serial-clear", action: () => {
      if (elements.terminal) {
        elements.terminal.textContent = "";
        terminalBuffer = [];
      }
    }},
    { id: "serial-save-log", action: saveSerialLog },
    { id: "export-serial-logs", action: exportSerialLogs },
  ];

  actions.forEach((action) => {
    const button = document.getElementById(action.id);
    if (!button) {
      return;
    }
    button.addEventListener("click", () => {
      if (action.action) {
        action.action();
      } else {
        showToast(action.message, "info");
      }
    });
  });
}

function setupTerminalInput() {
  if (!elements.terminal || terminalInputReady) {
    return;
  }
  elements.terminal.tabIndex = 0;
  elements.terminal.addEventListener("keydown", (event) => {
    if (!wsClient) {
      return;
    }
    let data = null;
    if (event.key === "Enter") {
      data = "\n";
    } else if (event.key === "Backspace") {
      data = "\x7f";
    } else if (event.key.length === 1) {
      data = event.key;
    }
    if (data !== null) {
      event.preventDefault();
      wsClient.send({ type: "data", data });
    }
  });
  terminalInputReady = true;
}

function focusTerminal() {
  if (elements.terminal) {
    elements.terminal.focus();
  }
}

async function configureSerial() {
  if (!deviceCache.length) {
    showToast("No serial devices available.", "error");
    return;
  }
  const defaultId = deviceCache[0]?.id || "";
  const form = await modalForm(
    [
      { name: "device_id", label: "Device ID to configure", default: defaultId },
      { name: "friendly_name", label: "Friendly name (optional)", default: "" },
      { name: "baud_rate", label: "Baud rate", default: "9600" },
      { name: "data_bits", label: "Data bits", default: "8" },
      { name: "parity", label: "Parity (none/even/odd)", default: "none" },
      { name: "stop_bits", label: "Stop bits", default: "1" },
    ],
    "Configure serial device"
  );
  if (!form) {
    return;
  }
  const {
    device_id: deviceId,
    friendly_name: friendlyName,
    baud_rate: baudRate,
    data_bits: dataBits,
    parity: parity,
    stop_bits: stopBits,
  } = form;
  if (!deviceId.trim()) {
    showToast("Device ID is required.", "error");
    return;
  }
  const payload = {};
  if (friendlyName.trim()) {
    payload.friendly_name = friendlyName;
  }
  if (baudRate) {
    payload.baud_rate = Number(baudRate);
  }
  if (dataBits) {
    payload.data_bits = Number(dataBits);
  }
  if (parity) {
    payload.parity = parity;
  }
  if (stopBits) {
    payload.stop_bits = Number(stopBits);
  }
  apiPut(`/api/v1/serial/devices/${encodeURIComponent(deviceId)}`, payload)
    .then(() => {
      showToast("Serial device updated.", "success");
      loadDevices();
    })
    .catch(() => showToast("Unable to update device.", "error"));
}

function activeSessionId() {
  return activeSessions[0]?.session_id || "";
}

async function saveSerialLog() {
  const sessionId = activeSessionId();
  if (!sessionId) {
    showToast("No active session available.", "error");
    return;
  }
  try {
    const payload = await apiGet(`/api/v1/serial/logs/${sessionId}/content`);
    const data = extractData(payload) || {};
    const content = data.content || "";
    downloadText(`serial-${sessionId}.log`, content);
    showToast("Log downloaded.", "success");
  } catch (error) {
    showToast("Unable to download log.", "error");
  }
}

async function exportSerialLogs() {
  const defaultIds = activeSessions.map((session) => session.session_id).join(",");
  const idsInput = await modalPrompt(
    "Session IDs to export (comma-separated)",
    defaultIds,
    { label: "Session IDs" }
  );
  if (idsInput === null || !idsInput.trim()) {
    return;
  }
  const logIds = idsInput
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!logIds.length) {
    showToast("No session IDs provided.", "error");
    return;
  }
  try {
    const payload = await apiPost("/api/v1/serial/logs/export", {
      log_ids: logIds,
    });
    const data = extractData(payload) || {};
    const archivePath = data.archive || "";
    const archiveName = archivePath.split("/").pop();
    if (archiveName) {
      window.location.assign(`/api/v1/serial/logs/export/${archiveName}`);
    } else {
      showToast("Export created.", "success");
    }
  } catch (error) {
    showToast("Unable to export logs.", "error");
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
  } catch (error) {
    showToast("Unable to load serial devices.", "error");
  }
}

async function loadSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions");
    const data = extractData(payload) || {};
    renderSessions(data.sessions || []);
  } catch (error) {
    showToast("Unable to load serial sessions.", "error");
  }
}

function init() {
  const refresh = document.getElementById("refresh-serial");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadDevices();
      loadSessions();
    });
  }
  setupActions();
  setupTerminalInput();
  loadDevices();
  loadSessions();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (wsClient) {
    wsClient.close();
  }
});

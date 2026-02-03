import { apiGet, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";

const elements = {
  metrics: {
    cpu: {
      value: document.getElementById("dash-cpu-value"),
      meter: document.getElementById("dash-cpu-meter"),
    },
    memory: {
      value: document.getElementById("dash-memory-value"),
      meter: document.getElementById("dash-memory-meter"),
    },
    temp: {
      value: document.getElementById("dash-temp-value"),
      meter: document.getElementById("dash-temp-meter"),
    },
    storage: {
      value: document.getElementById("dash-storage-value"),
      meter: document.getElementById("dash-storage-meter"),
    },
  },
  network: {
    summary: document.getElementById("network-summary"),
    tableBody: document.getElementById("network-table-body"),
  },
  services: {
    summary: document.getElementById("service-summary"),
    list: document.getElementById("service-list"),
  },
  captures: {
    summary: document.getElementById("capture-summary"),
    list: document.getElementById("capture-list"),
  },
  alerts: {
    summary: document.getElementById("alert-summary"),
    list: document.getElementById("alert-list"),
  },
  remote: {
    summary: document.getElementById("remote-summary"),
    list: document.getElementById("remote-tools-list"),
  },
  banner: document.getElementById("dashboard-connection-banner"),
};

let pollId = null;
let statusWs = null;
let hasShownWsError = false;
const MAX_POLL_INTERVAL = 5000;

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

function setMetric(metric, value, unit, maxValue = 100) {
  if (!metric?.value || !metric?.meter) {
    return;
  }
  const safeValue = Number.isFinite(value) ? value : null;
  const percentValue =
    safeValue === null
      ? null
      : Math.min(Math.max((safeValue / maxValue) * 100, 0), 100);

  metric.value.textContent =
    safeValue === null ? "--" : `${safeValue}${unit}`;
  metric.meter.style.width =
    percentValue === null ? "0%" : `${percentValue}%`;
}

function renderNetwork(interfaces) {
  if (!elements.network.tableBody || !elements.network.summary) {
    return;
  }
  elements.network.tableBody.textContent = "";
  if (!interfaces.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No interfaces detected.";
    row.appendChild(cell);
    elements.network.tableBody.appendChild(row);
    elements.network.summary.textContent = "No interfaces available.";
    return;
  }

  const wan = interfaces.find(
    (iface) => iface.role === "wan" && iface.status === "up"
  );
  elements.network.summary.textContent = wan
    ? `WAN Connected via ${wan.name}`
    : "No active WAN connection.";

  interfaces.forEach((iface) => {
    const row = document.createElement("tr");
    [iface.name || iface.id, iface.status, iface.ip_address, iface.type].forEach(
      (value) => {
        const cell = document.createElement("td");
        cell.textContent = value || "--";
        row.appendChild(cell);
      }
    );
    elements.network.tableBody.appendChild(row);
  });
}

function renderServices(services) {
  if (!elements.services.list || !elements.services.summary) {
    return;
  }
  elements.services.list.textContent = "";
  if (!services || Object.keys(services).length === 0) {
    const item = document.createElement("li");
    item.textContent = "No service data available.";
    elements.services.list.appendChild(item);
    elements.services.summary.textContent = "No services reported.";
    return;
  }

  const entries = Object.entries(services);
  elements.services.summary.textContent = `${entries.length} services`;
  entries.forEach(([name, status]) => {
    const item = document.createElement("li");
    item.className = "status-item";
    const label = document.createElement("span");
    label.className = "status-label";
    label.textContent = name;
    const value = document.createElement("span");
    value.className = "status-value";
    value.textContent = status;
    item.appendChild(label);
    item.appendChild(value);
    elements.services.list.appendChild(item);
  });
}

function renderCaptures(captures) {
  if (!elements.captures.list || !elements.captures.summary) {
    return;
  }
  elements.captures.list.textContent = "";
  if (!captures.length) {
    const item = document.createElement("li");
    item.textContent = "No active captures.";
    elements.captures.list.appendChild(item);
    elements.captures.summary.textContent = "No active captures.";
    return;
  }

  elements.captures.summary.textContent = `${captures.length} active`;
  captures.forEach((capture) => {
    const item = document.createElement("li");
    item.className = "status-item";
    const label = document.createElement("span");
    label.className = "status-label";
    label.textContent = capture.name || capture.id || "Capture";
    const value = document.createElement("span");
    value.className = "status-value";
    value.textContent = capture.status || "running";
    item.appendChild(label);
    item.appendChild(value);
    elements.captures.list.appendChild(item);
  });
}

function renderAlerts(alerts) {
  if (!elements.alerts.list || !elements.alerts.summary) {
    return;
  }
  elements.alerts.list.textContent = "";
  if (!alerts || alerts.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No active alerts.";
    elements.alerts.list.appendChild(item);
    elements.alerts.summary.textContent = "No alerts reported.";
    return;
  }

  elements.alerts.summary.textContent = `${alerts.length} alerts`;
  alerts.slice(0, 5).forEach((alert) => {
    const item = document.createElement("li");
    item.className = "status-item";
    const label = document.createElement("span");
    label.className = "status-label";
    label.textContent = (alert.severity || "info").toUpperCase();
    const value = document.createElement("span");
    value.className = "status-value";
    value.textContent = alert.message || "Alert";
    item.appendChild(label);
    item.appendChild(value);
    elements.alerts.list.appendChild(item);
  });
}

const REMOTE_TOOL_DISPLAY = {
  anydesk: "AnyDesk",
  teamviewer: "TeamViewer",
  vnc: "VNC",
  rpi_connect: "Raspberry Pi Connect",
};

function getEnabledRemoteTools(tools) {
  if (!tools || !Array.isArray(tools)) {
    return [];
  }
  return tools.filter(
    (t) =>
      (t.connection_id && String(t.connection_id).trim() !== "") ||
      t.status === "running"
  );
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderRemoteTools(tools) {
  if (!elements.remote.list || !elements.remote.summary) {
    return;
  }
  elements.remote.list.textContent = "";
  const enabled = getEnabledRemoteTools(tools);

  if (enabled.length === 0) {
    elements.remote.summary.textContent = "None configured";
    const msg = document.createElement("p");
    msg.className = "remote-tools-empty";
    msg.textContent = "No remote access tools enabled.";
    elements.remote.list.appendChild(msg);
    return;
  }

  elements.remote.summary.textContent =
    enabled.length === 1 ? "1 tool" : `${enabled.length} tools`;
  enabled.forEach((tool) => {
    const label = REMOTE_TOOL_DISPLAY[tool.name] || tool.name || "Remote";
    const connectionId = tool.connection_id || "--";
    const idAttr = `remote-id-${tool.name}`;
    const entry = document.createElement("div");
    entry.className = "remote-tool-entry";
    entry.innerHTML = `
      <div class="remote-tool-header">
        <span class="remote-tool-name">${escapeHtml(label)}</span>
        <span class="status-pill ${tool.status === "running" ? "status-pill-success" : "status-pill-warning"}">${tool.status === "running" ? "Running" : "Stopped"}</span>
      </div>
      <div class="remote-connection-row">
        <span class="connection-label">Connection</span>
        <span class="connection-value" id="${idAttr}">${escapeHtml(connectionId)}</span>
        <button class="btn btn-ghost btn-copy" type="button" data-copy-target="${idAttr}">Copy</button>
      </div>
    `;
    elements.remote.list.appendChild(entry);
  });
}

function setupRemoteCopyDelegation() {
  document.body.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-copy-target]");
    if (!button || !elements.remote.list?.contains(button)) {
      return;
    }
    const targetId = button.dataset.copyTarget;
    const target = document.getElementById(targetId);
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target.textContent.trim());
      showToast("Copied to clipboard.", "success");
    } catch (err) {
      showToast("Copy failed. Select and copy manually.", "error");
    }
  });
}

async function loadSystemStatus() {
  return loadSystemStatusWithOptions({});
}

async function loadSystemStatusWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    setMetric(elements.metrics.cpu, data.resources?.cpu_percent, "%");
    setMetric(elements.metrics.memory, data.resources?.memory_percent, "%");
    setMetric(elements.metrics.temp, data.resources?.temperature_c, " C", 100);
    setMetric(elements.metrics.storage, data.resources?.disk_percent, "%");
    renderServices(data.services);
  } catch (error) {
    if (!options.suppressError) {
      showToast("Unable to load system status.", "error");
    }
  }
}

async function loadNetworkStatus() {
  return loadNetworkStatusWithOptions({});
}

async function loadNetworkStatusWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/network/interfaces");
    const data = extractData(payload) || {};
    renderNetwork(data.interfaces || []);
  } catch (error) {
    elements.network.summary.textContent = "Network status unavailable.";
    if (!options.suppressError) {
      showToast("Unable to load network interfaces.", "error");
    }
  }
}

async function loadCaptures() {
  return loadCapturesWithOptions({});
}

async function loadCapturesWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/capture/active");
    const data = extractData(payload) || {};
    renderCaptures(data.captures || []);
  } catch (error) {
    elements.captures.summary.textContent = "Capture data unavailable.";
    if (!options.suppressError) {
      showToast("Unable to load capture status.", "error");
    }
  }
}

async function loadAlerts() {
  return loadAlertsWithOptions({});
}

async function loadAlertsWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    renderAlerts(data.alerts || data.monitor?.alerts || []);
  } catch (error) {
    elements.alerts.summary.textContent = "Alerts unavailable.";
    if (!options.suppressError) {
      showToast("Unable to load alerts.", "error");
    }
  }
}

async function loadRemoteStatus() {
  return loadRemoteStatusWithOptions({});
}

async function loadRemoteStatusWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/remote/status");
    const data = extractData(payload) || {};
    renderRemoteTools(data.tools);
  } catch (error) {
    if (elements.remote.summary) elements.remote.summary.textContent = "Unavailable";
    if (elements.remote.list) elements.remote.list.textContent = "";
    if (!options.suppressError) {
      showToast("Unable to load remote access status.", "error");
    }
  }
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) {
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function startPolling() {
  if (pollId) {
    return;
  }
  pollId = window.setInterval(() => {
    if (document.hidden) {
      return;
    }
    loadSystemStatusWithOptions({ suppressError: true });
    loadNetworkStatusWithOptions({ suppressError: true });
    loadCapturesWithOptions({ suppressError: true });
    loadAlertsWithOptions({ suppressError: true });
    loadRemoteStatusWithOptions({ suppressError: true });
  }, MAX_POLL_INTERVAL);
}

function stopPolling() {
  if (pollId) {
    window.clearInterval(pollId);
    pollId = null;
  }
}

function initStatusWebSocket() {
  statusWs = createWebSocketClient("/ws/status", { autoReconnect: true });
  statusWs.onStatus((status) => {
    if (status === "connected") {
      updateBanner("Live updates connected.", false);
      hasShownWsError = false;
      stopPolling();
    } else if (status === "disconnected" || status === "error") {
      if (!hasShownWsError) {
        updateBanner("Live updates unavailable. Polling every 5s.");
        hasShownWsError = true;
      }
      startPolling();
    }
  });
  statusWs.on("system_metrics", (message) => {
    const data = message.data || {};
    setMetric(elements.metrics.cpu, data.resources?.cpu_percent, "%");
    setMetric(elements.metrics.memory, data.resources?.memory_percent, "%");
    setMetric(elements.metrics.temp, data.resources?.temperature_c, " C", 100);
    setMetric(elements.metrics.storage, data.resources?.disk_percent, "%");
    renderServices(data.services);
  });
  statusWs.on("network_status", (message) => {
    const data = message.data || {};
    if (elements.network.summary) {
      elements.network.summary.textContent =
        data.wan_status === "connected" && data.wan_interface
          ? `WAN Connected via ${data.wan_interface}`
          : "No active WAN connection.";
    }
  });
  statusWs.on("network_interfaces", (message) => {
    const data = message.data || {};
    renderNetwork(data.interfaces || []);
  });
  statusWs.connect();
}

function init() {
  setupRemoteCopyDelegation();
  loadSystemStatus();
  loadNetworkStatus();
  loadCaptures();
  loadAlerts();
  loadRemoteStatus();
  initStatusWebSocket();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (statusWs) {
    statusWs.close();
  }
  stopPolling();
});

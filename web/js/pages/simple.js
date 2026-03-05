import { apiGet, extractData } from "../api.js";
import { copyTextToClipboard } from "../components.js";
import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureSimpleMode, setMode } from "../mode.js";
import { createWebSocketClient } from "../websocket.js";

const elements = {
  health: document.getElementById("system-health"),
  networkSummary: document.getElementById("network-summary"),
  interfaceList: document.getElementById("interface-list"),
  serviceList: document.getElementById("service-list"),
  alertList: document.getElementById("alert-list"),
  metrics: {
    cpu: document.getElementById("metric-cpu"),
    memory: document.getElementById("metric-memory"),
    temp: document.getElementById("metric-temp"),
    storage: document.getElementById("metric-storage"),
  },
  meters: {
    cpu: document.getElementById("meter-cpu"),
    memory: document.getElementById("meter-memory"),
    temp: document.getElementById("meter-temp"),
    storage: document.getElementById("meter-storage"),
  },
  wifi: {
    status: document.getElementById("wifi-status"),
    ssid: document.getElementById("wifi-ssid"),
    password: document.getElementById("wifi-password"),
  },
  remote: {
    status: document.getElementById("remote-status"),
    list: document.getElementById("remote-tools-list"),
  },
  quick: {
    capture: document.getElementById("action-capture"),
    serial: document.getElementById("action-serial"),
    logs: document.getElementById("action-logs"),
  },
  footer: {
    version: document.getElementById("version-label"),
    lastUpdate: document.getElementById("last-update"),
  },
  banner: document.getElementById("simple-connection-banner"),
};

let wifiPasswordCache = null;
let pollId = null;
let statusWs = null;
let hasShownWsError = false;
const MAX_POLL_INTERVAL = 5000;

function setStatusIndicator(status) {
  const dot = elements.health.querySelector(".status-dot");
  const text = elements.health.querySelector(".status-text");
  const normalized = (status || "unknown").toLowerCase();

  dot.style.background = "var(--color-muted)";
  if (normalized === "healthy") {
    dot.style.background = "var(--color-success)";
  } else if (normalized === "warning") {
    dot.style.background = "var(--color-warning)";
  } else if (normalized === "error") {
    dot.style.background = "var(--color-danger)";
  }

  text.textContent = `Status: ${status || "Unknown"}`;
}

function setMetric(id, value, unit, meterEl) {
  if (!elements.metrics[id] || !meterEl) {
    return;
  }
  const safeValue = Number.isFinite(value) ? value : null;
  const percentValue =
    safeValue === null ? null : Math.min(Math.max(safeValue, 0), 100);
  elements.metrics[id].textContent =
    safeValue === null ? "--" : `${safeValue}${unit}`;
  meterEl.style.width =
    percentValue === null ? "0%" : `${percentValue}%`;
}

function renderInterfaces(interfaces) {
  elements.interfaceList.textContent = "";
  if (!interfaces.length) {
    const item = document.createElement("li");
    item.textContent = "No interfaces detected.";
    elements.interfaceList.appendChild(item);
    return;
  }

  interfaces.forEach((iface) => {
    const item = document.createElement("li");
    const status = iface.status || "unknown";
    const ip = iface.ip_address || "no IP";
    item.textContent = `${iface.name || iface.id} (${status}, ${ip})`;
    elements.interfaceList.appendChild(item);
  });
}

function renderServices(services) {
  elements.serviceList.textContent = "";
  if (!services || Object.keys(services).length === 0) {
    const item = document.createElement("li");
    item.textContent = "No service data.";
    elements.serviceList.appendChild(item);
    return;
  }

  Object.entries(services).forEach(([name, status]) => {
    const item = document.createElement("li");
    item.textContent = `${name}: ${status}`;
    elements.serviceList.appendChild(item);
  });
}

function updateNetworkSummary(interfaces) {
  const wan = interfaces.find(
    (iface) => iface.role === "wan" && iface.status === "up"
  );
  if (wan) {
    elements.networkSummary.textContent = `WAN Connected via ${wan.name}`;
  } else {
    elements.networkSummary.textContent = "No WAN Connection detected.";
  }

  const hasInterfaces = interfaces.length > 0;
  elements.quick.capture.textContent = hasInterfaces
    ? "Ready to capture"
    : "No interfaces available";
}

const REMOTE_TOOL_DISPLAY = {
  anydesk: "AnyDesk",
  teamviewer: "TeamViewer",
  vnc: "VNC",
  rpi_connect: "Raspberry Pi Connect",
};

/** Show only tools that are enabled/available (have connection info or are running). */
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

function updateRemoteStatus(tools) {
  const listEl = elements.remote.list;
  if (!listEl) {
    return;
  }

  const enabled = getEnabledRemoteTools(tools);

  if (enabled.length === 0) {
    elements.remote.status.textContent = "None configured";
    elements.remote.status.className = "status-pill status-pill-warning";
    listEl.textContent = "";
    const msg = document.createElement("p");
    msg.className = "remote-tools-empty";
    msg.textContent = "No remote access tools enabled. Configure in Advanced Mode.";
    listEl.appendChild(msg);
    return;
  }

  elements.remote.status.textContent =
    enabled.length === 1 ? "1 tool" : `${enabled.length} tools`;
  elements.remote.status.className = "status-pill status-pill-success";
  listEl.textContent = "";

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
      <div class="connection-row">
        <span class="connection-label">Connection</span>
        <span class="connection-value" id="${idAttr}">${escapeHtml(connectionId)}</span>
        <button class="btn btn-ghost btn-copy" type="button" data-copy-target="${idAttr}">Copy</button>
      </div>
    `;
    listEl.appendChild(entry);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function updateWifiInfo(interfaces) {
  const wifi = interfaces.find((iface) => iface.type === "wifi");
  if (!wifi) {
    elements.wifi.status.textContent = "Unavailable";
    elements.wifi.status.className = "status-pill status-pill-warning";
    elements.wifi.ssid.textContent = "Not available";
    wifiPasswordCache = null;
    elements.wifi.password.textContent = "Hidden";
    return;
  }

  elements.wifi.status.textContent = wifi.status === "up" ? "Active" : "Down";
  elements.wifi.status.className =
    wifi.status === "up"
      ? "status-pill status-pill-success"
      : "status-pill status-pill-warning";
  elements.wifi.ssid.textContent = wifi.ssid || "Unknown SSID";
  wifiPasswordCache = wifi.password || "Not available";
  elements.wifi.password.textContent = "Hidden";
}

function updateQuickActions(serialCount) {
  elements.quick.serial.textContent = `Devices: ${serialCount}`;
}

function renderAlerts(alerts) {
  if (!elements.alertList) {
    return;
  }
  elements.alertList.textContent = "";
  const list = alerts && Array.isArray(alerts) ? alerts : [];
  if (list.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No alerts yet.";
    elements.alertList.appendChild(item);
    return;
  }
  list.slice(0, 5).forEach((alert) => {
    const item = document.createElement("li");
    const msg = alert.message || alert.summary || "Alert";
    const ts = alert.timestamp;
    let timeStr = "";
    if (ts && typeof ts === "string") {
      try {
        const d = new Date(ts);
        if (!Number.isNaN(d.getTime())) {
          timeStr = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
        }
      } catch {
        // ignore
      }
    }
    item.textContent = timeStr ? `${timeStr} — ${msg}` : msg;
    elements.alertList.appendChild(item);
  });
}

function updateFooter(systemInfo) {
  if (elements.footer.version) {
    elements.footer.version.textContent = systemInfo?.version ?? "--";
  }
  if (elements.footer.lastUpdate) {
    elements.footer.lastUpdate.textContent = systemInfo?.last_update
      ? new Date(systemInfo.last_update).toLocaleString()
      : "—";
  }
}

function showToast(message, variant = "info") {
  const toastRegion = document.getElementById("toast-region");
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

async function loadSystemStatus() {
  return loadSystemStatusWithOptions({});
}

async function loadSystemStatusWithOptions(options) {
  try {
    const [statusPayload, infoPayload] = await Promise.all([
      apiGet("/api/v1/system/status"),
      apiGet("/api/v1/system/info"),
    ]);
    const data = extractData(statusPayload) || {};
    const info = extractData(infoPayload) || {};
    clearApiConnectionError();
    setStatusIndicator(data.health ?? data.status);
    setMetric("cpu", data.resources?.cpu_percent, "%", elements.meters.cpu);
    setMetric(
      "memory",
      data.resources?.memory_percent,
      "%",
      elements.meters.memory
    );
    setMetric(
      "temp",
      data.resources?.temperature_c,
      " C",
      elements.meters.temp
    );
    setMetric(
      "storage",
      data.resources?.disk_percent,
      "%",
      elements.meters.storage
    );
    renderServices(data.services);
    renderAlerts(data.alerts ?? data.monitor?.alerts);
    updateFooter(info);
  } catch (error) {
    setStatusIndicator("Unknown");
    if (!options.suppressError) {
      showToast("Unable to load system status.", "error");
      showApiConnectionError();
    }
  }
}

async function loadNetworkInfo() {
  return loadNetworkInfoWithOptions({});
}

async function loadNetworkInfoWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/network/interfaces");
    const data = extractData(payload) || {};
    clearApiConnectionError();
    const interfaces = data.interfaces || [];
    renderInterfaces(interfaces);
    updateNetworkSummary(interfaces);
    updateWifiInfo(interfaces);
  } catch (error) {
    elements.interfaceList.textContent = "";
    const item = document.createElement("li");
    item.textContent = "Unable to load interfaces.";
    elements.interfaceList.appendChild(item);
    elements.networkSummary.textContent = "Network status unavailable.";
    if (!options.suppressError) {
      showToast("Unable to load network interfaces.", "error");
      showApiConnectionError();
    }
  }
}

async function loadSerialDevices() {
  return loadSerialDevicesWithOptions({});
}

async function loadSerialDevicesWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/serial/devices");
    const data = extractData(payload) || {};
    clearApiConnectionError();
    const devices = data.devices || [];
    updateQuickActions(devices.length);
  } catch (error) {
    elements.quick.serial.textContent = "Devices: --";
    if (!options.suppressError) {
      showToast("Unable to load serial devices.", "error");
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
    clearApiConnectionError();
    updateRemoteStatus(data.tools);
  } catch (error) {
    updateRemoteStatus([]);
    if (!options.suppressError) {
      showToast("Unable to load remote access status.", "error");
      showApiConnectionError();
    }
  }
}

function setupModeSwitch() {
  const buttons = [
    document.getElementById("switch-advanced"),
    document.getElementById("switch-advanced-cta"),
  ];

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const confirmed = await confirmModeSwitch("advanced");
      if (!confirmed) {
        return;
      }
      setMode("advanced");
      window.location.assign("/advanced/");
    });
  });
}

function setupConnectionPrivacy() {
  const button = document.getElementById("toggle-connection-privacy");
  const card = document.getElementById("connection-card");

  button.addEventListener("click", () => {
    const isHidden = card.classList.toggle("is-hidden");
    button.textContent = isHidden ? "Show" : "Hide";
  });
}

function setupWifiPasswordToggle() {
  const button = document.getElementById("toggle-wifi-password");
  const password = elements.wifi.password;

  button.addEventListener("click", () => {
    const isRevealed = password.dataset.reveal === "true";
    password.dataset.reveal = isRevealed ? "false" : "true";
    password.textContent = isRevealed
      ? "Hidden"
      : wifiPasswordCache || "--";
    button.textContent = isRevealed ? "Show" : "Hide";
  });
}

function setupCopyButtons() {
  document.body.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-copy-target]");
    if (!button) {
      return;
    }
    const targetId = button.dataset.copyTarget;
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }
    const ok = await copyTextToClipboard(target.textContent.trim());
    showToast(ok ? "Copied to clipboard." : "Copy failed. Select and copy manually.", ok ? "success" : "error");
  });
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) {
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

let apiErrorBannerShown = false;

function showApiConnectionError() {
  if (!elements.banner || apiErrorBannerShown) {
    return;
  }
  apiErrorBannerShown = true;
  elements.banner.textContent = "";
  elements.banner.classList.add("is-visible", "api-error");
  const msg = document.createElement("span");
  msg.textContent = "Cannot connect to the API. Check that the API service (rpi-engineer-api) and nginx are running. ";
  elements.banner.appendChild(msg);
  const link = document.createElement("a");
  link.href = "/docs/troubleshooting/install-issues.html#dashboard-not-loading";
  link.textContent = "Troubleshooting";
  link.className = "link-inline";
  elements.banner.appendChild(link);
  elements.banner.appendChild(document.createTextNode(" "));
  const retryBtn = document.createElement("button");
  retryBtn.className = "btn btn-secondary btn-sm";
  retryBtn.textContent = "Retry";
  retryBtn.type = "button";
  retryBtn.addEventListener("click", () => {
    clearApiConnectionError();
    loadSystemStatus();
    loadNetworkInfo();
    loadRemoteStatus();
    loadSerialDevices();
  });
  elements.banner.appendChild(retryBtn);
}

function clearApiConnectionError() {
  apiErrorBannerShown = false;
  if (elements.banner) {
    elements.banner.textContent = "";
    elements.banner.classList.remove("is-visible", "api-error");
  }
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
    loadNetworkInfoWithOptions({ suppressError: true });
    loadRemoteStatusWithOptions({ suppressError: true });
    loadSerialDevicesWithOptions({ suppressError: true });
  }, MAX_POLL_INTERVAL);
}

function stopPolling() {
  if (pollId) {
    window.clearInterval(pollId);
    pollId = null;
  }
}

function initStatusWebSocket() {
  statusWs = createWebSocketClient("/ws/status", { autoReconnect: false });
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
    setStatusIndicator(data.status);
    setMetric("cpu", data.resources?.cpu_percent, "%", elements.meters.cpu);
    setMetric("memory", data.resources?.memory_percent, "%", elements.meters.memory);
    setMetric("temp", data.resources?.temperature_c, " C", elements.meters.temp);
    setMetric(
      "storage",
      data.resources?.disk_percent,
      "%",
      elements.meters.storage
    );
    renderServices(data.services);
  });
  statusWs.on("network_status", (message) => {
    const data = message.data || {};
    if (data.wan_status === "connected" && data.wan_interface) {
      elements.networkSummary.textContent = `WAN Connected via ${data.wan_interface}`;
    } else {
      elements.networkSummary.textContent = "No WAN Connection detected.";
    }
  });
  statusWs.on("network_interfaces", (message) => {
    const data = message.data || {};
    const interfaces = data.interfaces || [];
    renderInterfaces(interfaces);
    updateNetworkSummary(interfaces);
    updateWifiInfo(interfaces);
  });
  statusWs.connect();
}

function init() {
  ensureSimpleMode();
  applyStoredTheme();
  initThemeSelector(document.getElementById("theme-select"));
  setupModeSwitch();
  setupConnectionPrivacy();
  setupWifiPasswordToggle();
  setupCopyButtons();
  loadSystemStatus();
  loadNetworkInfo();
  loadRemoteStatus();
  loadSerialDevices();
  initStatusWebSocket();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (statusWs) {
    statusWs.close();
  }
  stopPolling();
});

import { apiGet, extractData } from "../api.js";
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
    tool: document.getElementById("remote-tool"),
    id: document.getElementById("remote-id"),
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

function updateRemoteStatus(tools) {
  if (!tools || tools.length === 0) {
    elements.remote.status.textContent = "Unavailable";
    elements.remote.status.className = "status-pill status-pill-warning";
    elements.remote.tool.textContent = "Not configured";
    elements.remote.id.textContent = "--";
    return;
  }

  const tool =
    tools.find((t) => t.ready) || tools.find((t) => t.status === "running") || tools[0];
  elements.remote.tool.textContent =
    REMOTE_TOOL_DISPLAY[tool.name] || tool.name || "remote";
  elements.remote.id.textContent = tool.connection_id || "--";
  elements.remote.status.textContent =
    tool.status === "running" ? "Running" : "Stopped";
  elements.remote.status.className =
    tool.status === "running"
      ? "status-pill status-pill-success"
      : "status-pill status-pill-warning";
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

function updateFooter(systemInfo) {
  elements.footer.version.textContent = systemInfo?.version || "--";
  elements.footer.lastUpdate.textContent = new Date().toLocaleString();
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
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    setStatusIndicator(data.status);
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
    updateFooter(data);
  } catch (error) {
    setStatusIndicator("Unknown");
    if (!options.suppressError) {
      showToast("Unable to load system status.", "error");
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
    updateRemoteStatus(data.tools);
  } catch (error) {
    updateRemoteStatus([]);
    if (!options.suppressError) {
      showToast("Unable to load remote access status.", "error");
    }
  }
}

function setupModeSwitch() {
  const buttons = [
    document.getElementById("switch-advanced"),
    document.getElementById("switch-advanced-cta"),
  ];

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      if (!confirmModeSwitch("advanced")) {
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
  const buttons = document.querySelectorAll("[data-copy-target]");
  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const targetId = button.dataset.copyTarget;
      const target = document.getElementById(targetId);
      if (!target) {
        return;
      }
      try {
        await navigator.clipboard.writeText(target.textContent.trim());
        showToast("Copied to clipboard.", "success");
      } catch (error) {
        showToast("Copy failed. Select and copy manually.", "error");
      }
    });
  });
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

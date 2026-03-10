import { apiGet, apiPost, extractData } from "../api.js";
import { copyTextToClipboard } from "../components.js";
import { modalPrompt } from "../modal.js";
import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureSimpleMode, setMode } from "../mode.js";
import { createWebSocketClient } from "../websocket.js";

const elements = {
  health: document.getElementById("system-health"),
  networkSummary: document.getElementById("network-summary"),
  interfaceList: document.getElementById("interface-list"),
  networkInterfaceList: document.getElementById("network-interface-list"),
  wanSummary: document.getElementById("wan-summary"),
  wanStatusBadge: document.getElementById("wan-status-badge"),
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
let lastNetworkInterfaces = [];
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
    item.className = "detail-empty";
    item.textContent = "No interfaces detected.";
    elements.interfaceList.appendChild(item);
    return;
  }

  interfaces.forEach((iface) => {
    const item = document.createElement("li");
    item.className = "detail-iface-row";
    const name = iface.name || iface.id || "—";
    const status = (iface.status || "unknown").toLowerCase();
    const ip = iface.ip_address || "no IP";
    const statusClass =
      status === "up"
        ? "detail-status detail-status-up"
        : status === "down"
          ? "detail-status detail-status-down"
          : "detail-status detail-status-unknown";
    item.innerHTML = `<span class="detail-iface-name">${escapeHtml(name)}</span> <span class="${statusClass}" aria-label="status ${status}">${status}</span> <span class="detail-iface-ip">${escapeHtml(ip)}</span>`;
    elements.interfaceList.appendChild(item);
  });
}

function renderServices(services) {
  elements.serviceList.textContent = "";
  if (!services || Object.keys(services).length === 0) {
    const item = document.createElement("li");
    item.className = "detail-empty";
    item.textContent = "No service data.";
    elements.serviceList.appendChild(item);
    return;
  }

  Object.entries(services).forEach(([name, status]) => {
    const item = document.createElement("li");
    item.className = "detail-svc-row";
    const raw = (status || "").toLowerCase();
    const statusClass =
      raw === "running"
        ? "detail-status detail-status-running"
        : raw === "stopped"
          ? "detail-status detail-status-stopped"
          : raw === "starting" || raw === "stopping"
            ? "detail-status detail-status-transition"
            : "detail-status detail-status-unknown";
    item.innerHTML = `<span class="detail-svc-name">${escapeHtml(name)}</span> <span class="${statusClass}" aria-label="service ${raw}">${status}</span>`;
    elements.serviceList.appendChild(item);
  });
}

function getInterfaceDescription(iface) {
  const id = (iface.id || iface.name || "").toLowerCase();
  if (id.startsWith("eth")) return "Wired";
  if (id.startsWith("usb")) return "USB";
  if (id.startsWith("wlan")) return "Hotspot";
  return iface.friendly_name || id || "Interface";
}

function isHotspotInterface(iface) {
  const id = (iface.id || iface.name || "").toLowerCase();
  return id.startsWith("wlan");
}

function renderNetworkInterfacesCard(interfaces, networkStatus) {
  const listEl = elements.networkInterfaceList;
  const summaryEl = elements.wanSummary;
  const badgeEl = elements.wanStatusBadge;

  if (!listEl || !summaryEl || !badgeEl) return;

  const wanInterface = networkStatus?.wan_interface || "";
  const wanStatus = (networkStatus?.wan_status || "unknown").toLowerCase();
  const hotspotStatus = (networkStatus?.hotspot_status || "inactive").toLowerCase();

  if (wanStatus === "connected" && wanInterface) {
    summaryEl.textContent = `WAN connected via ${wanInterface}`;
    badgeEl.textContent = "Connected";
    badgeEl.className = "status-pill status-pill-success";
  } else {
    summaryEl.textContent = wanInterface
      ? `WAN interface: ${wanInterface} (no internet)`
      : "No WAN connection";
    badgeEl.textContent = "Disconnected";
    badgeEl.className = "status-pill status-pill-warning";
  }

  listEl.textContent = "";
  if (!interfaces || interfaces.length === 0) {
    const li = document.createElement("li");
    li.className = "network-interface-empty";
    li.textContent = "No interfaces detected.";
    listEl.appendChild(li);
    return;
  }

  interfaces.forEach((iface) => {
    const li = document.createElement("li");
    li.className = "network-interface-item";
    const name = iface.name || iface.id || "—";
    const desc = getInterfaceDescription(iface);
    const ip = iface.ip_address || "—";
    const status = (iface.status || "unknown").toLowerCase();

    let label = desc;
    if (desc === "Wired" || desc === "USB") {
      label = `${desc} (${name})`;
    } else if (desc === "Hotspot") {
      label = `Hotspot (${name})`;
    }

    const statusClass =
      status === "up" ? "network-iface-up" : "network-iface-down";

    let content = `<span class="network-iface-label">${escapeHtml(label)}</span> <span class="network-iface-status ${statusClass}">${status}</span> — <span class="network-iface-ip">${escapeHtml(ip)}</span>`;
    if (isHotspotInterface(iface) && hotspotStatus === "active") {
      content += `<p class="network-iface-note">The wireless hotspot runs on this interface.</p>`;
    }
    li.innerHTML = content;
    listEl.appendChild(li);
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
const REMOTE_PASSWORD_TOOLS = ["anydesk", "teamviewer"];
let remotePasswordCache = {};

/** Show tools that are enabled/available. AnyDesk and TeamViewer always shown so credentials/connection are visible. */
function getEnabledRemoteTools(tools) {
  if (!tools || !Array.isArray(tools)) {
    return [];
  }
  return tools.filter((t) => {
    const hasId = t.connection_id && String(t.connection_id).trim() !== "";
    const running = t.status === "running";
    if (t.name === "anydesk" || t.name === "teamviewer") {
      return true;
    }
    return hasId || running;
  });
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
  remotePasswordCache = {};

  enabled.forEach((tool) => {
    const label = REMOTE_TOOL_DISPLAY[tool.name] || tool.name || "Remote";
    const connectionId = tool.connection_id || "--";
    const idAttr = `remote-id-${tool.name}`;
    const hasPassword = REMOTE_PASSWORD_TOOLS.includes(tool.name);
    const password = hasPassword && tool.password ? String(tool.password) : "";
    if (hasPassword) remotePasswordCache[tool.name] = password;
    const passwordRow = hasPassword
      ? `
      <div class="connection-row">
        <span class="connection-label">Password</span>
        <span class="connection-value" id="remote-pw-value-${tool.name}" data-reveal="false">${password ? "••••••••" : "—"}</span>
        <span class="remote-pw-actions">
          ${password ? `<button class="btn btn-ghost btn-copy" type="button" data-remote-reveal="${tool.name}">Show</button>` : ""}
          ${password ? `<button class="btn btn-ghost btn-copy" type="button" data-copy-password="${tool.name}">Copy</button>` : ""}
          <button class="btn btn-ghost btn-copy" type="button" data-remote-reset-password="${tool.name}">Reset</button>
        </span>
      </div>`
      : "";
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
      ${passwordRow}
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
  elements.alertList.classList.remove("detail-alerts-empty");
  const list = alerts && Array.isArray(alerts) ? alerts : [];
  if (list.length === 0) {
    elements.alertList.classList.add("detail-alerts-empty");
    const item = document.createElement("li");
    item.className = "detail-empty";
    item.textContent = "No alerts yet.";
    elements.alertList.appendChild(item);
    return;
  }
  list.slice(0, 5).forEach((alert) => {
    const item = document.createElement("li");
    item.className = "detail-alert-item";
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
    const severity = (alert.severity || alert.level || "").toLowerCase();
    if (severity) {
      item.classList.add(`detail-alert-${severity}`);
    }
    if (timeStr) {
      item.innerHTML = `<span class="detail-alert-time">${escapeHtml(timeStr)}</span> <span class="detail-alert-msg">${escapeHtml(msg)}</span>`;
    } else {
      item.textContent = msg;
    }
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
    const [ifacesPayload, statusPayload] = await Promise.all([
      apiGet("/api/v1/network/interfaces"),
      apiGet("/api/v1/network/status"),
    ]);
    const data = extractData(ifacesPayload) || {};
    const networkStatus = extractData(statusPayload) || {};
    clearApiConnectionError();
    const interfaces = data.interfaces || [];
    lastNetworkInterfaces = interfaces;
    renderInterfaces(interfaces);
    renderNetworkInterfacesCard(interfaces, networkStatus);
    updateNetworkSummary(interfaces);
    updateWifiInfo(interfaces);
  } catch (error) {
    elements.interfaceList.textContent = "";
    const item = document.createElement("li");
    item.textContent = "Unable to load interfaces.";
    elements.interfaceList.appendChild(item);
    elements.networkSummary.textContent = "Network status unavailable.";
    if (elements.networkInterfaceList && elements.wanSummary && elements.wanStatusBadge) {
      elements.wanSummary.textContent = "Network status unavailable.";
      elements.wanStatusBadge.textContent = "Unavailable";
      elements.wanStatusBadge.className = "status-pill status-pill-warning";
      elements.networkInterfaceList.textContent = "";
      const errLi = document.createElement("li");
      errLi.className = "network-interface-empty";
      errLi.textContent = "Unable to load interfaces.";
      elements.networkInterfaceList.appendChild(errLi);
    }
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

function setupRemotePasswordDelegation() {
  document.body.addEventListener("click", async (e) => {
    const revealBtn = e.target.closest("[data-remote-reveal]");
    const copyPwBtn = e.target.closest("[data-copy-password]");
    const resetBtn = e.target.closest("[data-remote-reset-password]");
    const button = revealBtn || copyPwBtn || resetBtn;
    if (!button || !elements.remote.list?.contains(button)) return;
    e.preventDefault();
    e.stopPropagation();
    const tool = button.dataset.remoteReveal || button.dataset.copyPassword || button.dataset.remoteResetPassword;
    if (!tool) return;

    if (revealBtn) {
      const valueEl = document.getElementById(`remote-pw-value-${tool}`);
      if (!valueEl) return;
      const revealed = valueEl.dataset.reveal === "true";
      valueEl.dataset.reveal = revealed ? "false" : "true";
      valueEl.textContent = revealed ? "••••••••" : (remotePasswordCache[tool] || "—");
      revealBtn.textContent = revealed ? "Show" : "Hide";
    } else if (copyPwBtn) {
      const pw = remotePasswordCache[tool] || "";
      const ok = pw ? await copyTextToClipboard(pw) : false;
      showToast(ok ? "Password copied." : "Nothing to copy.", ok ? "success" : "error");
    } else if (resetBtn) {
      const label = tool === "anydesk" ? "AnyDesk" : "TeamViewer";
      const newPassword = await modalPrompt(`Set new unattended access password for ${label}`, "", {
        label: "New password",
        inputType: "password",
      });
      if (newPassword == null) return;
      if (!newPassword.trim()) {
        showToast("Password cannot be empty.", "error");
        return;
      }
      resetBtn.disabled = true;
      resetBtn.textContent = "…";
      try {
        await apiPost("/api/v1/remote/password", { tool, password: newPassword });
        showToast("Password updated. Reloading…", "success");
        loadRemoteStatusWithOptions({ suppressError: true });
      } catch (err) {
        showToast(err?.message || "Failed to set password.", "error");
      } finally {
        resetBtn.disabled = false;
        resetBtn.textContent = "Reset";
      }
    }
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
    if (elements.networkInterfaceList) {
      renderNetworkInterfacesCard(lastNetworkInterfaces, data);
    }
  });
  statusWs.on("network_interfaces", (message) => {
    const data = message.data || {};
    const interfaces = data.interfaces || [];
    lastNetworkInterfaces = interfaces;
    renderInterfaces(interfaces);
    const derivedStatus = {
      wan_interface: interfaces.find((i) => i.role === "wan" && i.status === "up")?.name || "",
      wan_status: interfaces.some((i) => i.role === "wan" && i.status === "up") ? "connected" : "disconnected",
      hotspot_status: interfaces.some((i) => (i.id || i.name || "").startsWith("wlan") && i.status === "up")
        ? "active"
        : "inactive",
    };
    renderNetworkInterfacesCard(interfaces, derivedStatus);
    updateNetworkSummary(interfaces);
    updateWifiInfo(interfaces);
  });
  statusWs.connect();
}

function setupQuickActionLinks() {
  const grid = document.querySelector(".action-grid");
  if (!grid) {
    return;
  }
  grid.addEventListener("click", (e) => {
    const link = e.target.closest("a.action-card");
    if (!link || !link.href) {
      return;
    }
    try {
      const path = new URL(link.href).pathname;
      if (path.startsWith("/advanced/")) {
        setMode("advanced");
      }
    } catch {
      // ignore
    }
  });
}

function init() {
  ensureSimpleMode();
  applyStoredTheme();
  initThemeSelector(document.getElementById("theme-select"));
  setupModeSwitch();
  setupQuickActionLinks();
  setupConnectionPrivacy();
  setupWifiPasswordToggle();
  setupCopyButtons();
  setupRemotePasswordDelegation();
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

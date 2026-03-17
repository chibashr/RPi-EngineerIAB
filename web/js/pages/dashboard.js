import { apiGet, apiPost, extractData } from "../api.js";
import { copyTextToClipboard } from "../components.js";
import { modalForm, modalPrompt } from "../modal.js";
import { registerStatusHandler, onStatusConnection } from "../websocket.js";
import { setAlerts, formatAlertTimestamp } from "../notifications.js";

const DASHBOARD_WIDGETS_STORAGE_KEY = "rpi-dashboard-widgets";

const DASHBOARD_WIDGET_LIST = [
  { id: "metrics-cpu", label: "CPU" },
  { id: "metrics-memory", label: "Memory" },
  { id: "metrics-temp", label: "Temperature" },
  { id: "metrics-storage", label: "Storage" },
  { id: "panel-network", label: "Network Status" },
  { id: "panel-services", label: "Service Status" },
  { id: "panel-captures", label: "Active Captures" },
  { id: "panel-logs", label: "Logs" },
  { id: "panel-serial", label: "Serial Devices" },
  { id: "panel-remote", label: "Remote Access" },
];

function getWidgetVisibility() {
  try {
    const raw = localStorage.getItem(DASHBOARD_WIDGETS_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === "object") {
      const out = {};
      DASHBOARD_WIDGET_LIST.forEach((w) => {
        out[w.id] = parsed[w.id] !== false;
      });
      return out;
    }
  } catch (_) {
    // Ignore
  }
  return Object.fromEntries(DASHBOARD_WIDGET_LIST.map((w) => [w.id, true]));
}

function setWidgetVisibility(prefs) {
  try {
    localStorage.setItem(DASHBOARD_WIDGETS_STORAGE_KEY, JSON.stringify(prefs));
  } catch (_) {
    // Ignore
  }
}

function applyWidgetVisibility() {
  const prefs = getWidgetVisibility();
  DASHBOARD_WIDGET_LIST.forEach((w) => {
    const el = document.querySelector(`[data-widget-id="${w.id}"]`);
    if (el) {
      el.classList.toggle("dashboard-widget-hidden", !prefs[w.id]);
    }
  });
}

function setupDashboardWidgetPrefs() {
  const prefsPanel = document.getElementById("dashboard-widget-prefs");
  const prefsGrid = document.getElementById("dashboard-widget-prefs-grid");
  const customizeBtn = document.getElementById("dashboard-customize-btn");
  if (!prefsPanel || !prefsGrid || !customizeBtn) {
    return;
  }
  const prefs = getWidgetVisibility();
  DASHBOARD_WIDGET_LIST.forEach((w) => {
    const label = document.createElement("label");
    label.className = "dashboard-widget-prefs-label";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = prefs[w.id];
    input.dataset.widgetId = w.id;
    input.addEventListener("change", () => {
      const next = getWidgetVisibility();
      next[w.id] = input.checked;
      setWidgetVisibility(next);
      applyWidgetVisibility();
    });
    label.appendChild(input);
    label.appendChild(document.createTextNode(" " + w.label));
    prefsGrid.appendChild(label);
  });
  customizeBtn.addEventListener("click", () => {
    const isOpen = !prefsPanel.hidden;
    prefsPanel.hidden = isOpen;
    customizeBtn.setAttribute("aria-expanded", String(!isOpen));
  });
}

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
  serial: {
    summary: document.getElementById("serial-summary"),
    list: document.getElementById("serial-device-list"),
  },
  remote: {
    summary: document.getElementById("remote-summary"),
    list: document.getElementById("remote-tools-list"),
  },
  banner: document.getElementById("dashboard-connection-banner"),
};

let pollId = null;
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
    const captureId = capture.capture_id || capture.id;
    const item = document.createElement("li");
    item.className = "status-item status-item-with-actions";
    const left = document.createElement("div");
    left.className = "status-item-main";
    const label = document.createElement("span");
    label.className = "status-label";
    label.textContent = capture.name || captureId || "Capture";
    const value = document.createElement("span");
    value.className = "status-value";
    value.textContent = capture.status || "running";
    left.appendChild(label);
    left.appendChild(value);
    item.appendChild(left);
    const actions = document.createElement("div");
    actions.className = "status-item-actions";
    const stopBtn = document.createElement("button");
    stopBtn.className = "btn btn-secondary btn-sm";
    stopBtn.type = "button";
    stopBtn.textContent = "Stop";
    stopBtn.dataset.captureId = captureId;
    stopBtn.dataset.action = "stop";
    actions.appendChild(stopBtn);
    const viewLink = document.createElement("a");
    viewLink.className = "btn btn-secondary btn-sm";
    viewLink.href = "/advanced/capture.html";
    viewLink.textContent = "View";
    actions.appendChild(viewLink);
    item.appendChild(actions);
    elements.captures.list.appendChild(item);
  });
}

function renderSerialDevices(devices) {
  if (!elements.serial.list || !elements.serial.summary) {
    return;
  }
  elements.serial.list.textContent = "";
  if (!devices || devices.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No serial devices detected.";
    elements.serial.list.appendChild(item);
    elements.serial.summary.textContent = "No devices";
    return;
  }

  elements.serial.summary.textContent =
    devices.length === 1 ? "1 device" : `${devices.length} devices`;
  devices.forEach((device) => {
    const item = document.createElement("li");
    item.className = "status-item";
    const label = document.createElement("span");
    label.className = "status-label";
    const name = device.friendly_name || device.path || device.id || "Device";
    const path = device.path || device.id || "";
    label.textContent = path && path !== name ? `${name} (${path})` : name;
    const value = document.createElement("span");
    value.className = "status-value";
    value.textContent = `${device.status || "unknown"} • ${device.chipset || "—"}`;
    item.appendChild(label);
    item.appendChild(value);
    elements.serial.list.appendChild(item);
  });
}

function renderAlerts(alerts) {
  if (!alerts?.length) {
    return;
  }
  setAlerts(alerts);
}

const REMOTE_TOOL_DISPLAY = {
  anydesk: "AnyDesk",
  teamviewer: "TeamViewer",
  vnc: "VNC",
  rpi_connect: "Raspberry Pi Connect",
};

const REMOTE_PASSWORD_TOOLS = ["anydesk", "teamviewer"];
let remotePasswordCache = {};

function getEnabledRemoteTools(tools) {
  if (!tools || !Array.isArray(tools)) {
    return [];
  }
  return tools.filter((t) => {
    const hasId = t.connection_id && String(t.connection_id).trim() !== "";
    const running = t.status === "running";
    // Always show AnyDesk and TeamViewer so credentials/connection are visible even when ID not yet available or daemon stopped
    if (t.name === "anydesk" || t.name === "teamviewer") {
      return true;
    }
    return hasId || running;
  });
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
  remotePasswordCache = {};
  enabled.forEach((tool) => {
    const label = REMOTE_TOOL_DISPLAY[tool.name] || tool.name || "Remote";
    const connectionId = tool.connection_id || "--";
    const idAttr = `remote-id-${tool.name}`;
    const hasPassword = REMOTE_PASSWORD_TOOLS.includes(tool.name);
    const password = hasPassword && tool.password ? String(tool.password) : "";
    if (hasPassword) remotePasswordCache[tool.name] = password;
    const isTeamViewer = tool.name === "teamviewer";
    const generateBtn = isTeamViewer
      ? `<button class="btn btn-ghost btn-sm" type="button" data-teamviewer-generate>Generate</button>`
      : "";
    const passwordRow = hasPassword
      ? `
      <div class="remote-connection-row">
        <span class="connection-label">Password</span>
        <span class="connection-value" id="remote-pw-value-${tool.name}" data-reveal="false">${password ? "••••••••" : "—"}</span>
        <span class="remote-pw-actions">
          ${generateBtn}
          ${password ? `<button class="btn btn-ghost btn-sm" type="button" data-remote-reveal="${tool.name}">Show</button>` : ""}
          ${password ? `<button class="btn btn-secondary btn-sm" type="button" data-copy-password="${tool.name}">Copy</button>` : ""}
          <button class="btn btn-secondary btn-sm" type="button" data-remote-reset-password="${tool.name}">Reset</button>
        </span>
      </div>`
      : "";
    const accountRow = isTeamViewer
      ? `
      <div class="remote-connection-row">
        <span class="connection-label">Account</span>
        <span class="connection-value" id="remote-account-teamviewer">${tool.account_email ? escapeHtml(tool.account_email) : "Not connected"}</span>
        <button class="btn btn-secondary btn-sm" type="button" data-teamviewer-setup>Connect</button>
      </div>`
      : "";
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
        <button class="btn btn-secondary btn-sm" type="button" data-copy-target="${idAttr}">Copy</button>
      </div>
      ${passwordRow}
      ${accountRow}
    `;
    elements.remote.list.appendChild(entry);
  });
}

function setupPanelButtonDelegation() {
  document.body.addEventListener("click", (e) => {
    const panelLink = e.target.closest(".panel-link");
    const button = e.target.closest("button, .btn");
    if (panelLink && button && panelLink.contains(button)) {
      e.stopPropagation();
    }
  });
}

function setupRemoteCopyDelegation() {
  document.body.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-copy-target]");
    if (!button || !elements.remote.list?.contains(button)) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    const targetId = button.dataset.copyTarget;
    const target = document.getElementById(targetId);
    if (!target) return;
    const ok = await copyTextToClipboard(target.textContent.trim());
    showToast(ok ? "Copied to clipboard." : "Copy failed. Select and copy manually.", ok ? "success" : "error");
  });
}

function setupRemotePasswordDelegation() {
  document.body.addEventListener("click", async (e) => {
    const revealBtn = e.target.closest("[data-remote-reveal]");
    const copyPwBtn = e.target.closest("[data-copy-password]");
    const resetBtn = e.target.closest("[data-remote-reset-password]");
    const generateBtn = e.target.closest("[data-teamviewer-generate]");
    const setupBtn = e.target.closest("[data-teamviewer-setup]");
    const button = revealBtn || copyPwBtn || resetBtn || generateBtn || setupBtn;
    if (!button || !elements.remote.list?.contains(button)) return;
    e.preventDefault();
    e.stopPropagation();
    const tool = button.dataset.remoteReveal || button.dataset.copyPassword || button.dataset.remoteResetPassword;

    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.textContent = "...";
      try {
        const resp = await apiPost("/api/v1/remote/teamviewer/generate-password");
        const data = extractData(resp);
        showToast(`Password set: ${data.password}`, "success");
        loadDashboard({ suppressError: true });
      } catch (err) {
        showToast(err?.message || "Failed to generate password.", "error");
      } finally {
        generateBtn.disabled = false;
        generateBtn.textContent = "Generate";
      }
      return;
    }

    if (setupBtn) {
      const result = await modalForm(
        [
          { name: "email", label: "TeamViewer Account Email", type: "email", placeholder: "your@email.com" },
          { name: "password", label: "TeamViewer Account Password", type: "password" },
        ],
        "Connect to TeamViewer Account"
      );
      if (!result) return;
      if (!result.email || !result.password) {
        showToast("Email and password are required.", "error");
        return;
      }
      setupBtn.disabled = true;
      setupBtn.textContent = "...";
      try {
        await apiPost("/api/v1/remote/teamviewer/setup-account", {
          email: result.email,
          password: result.password,
        });
        showToast("Device connected to TeamViewer account.", "success");
        loadDashboard({ suppressError: true });
      } catch (err) {
        showToast(err?.message || "Failed to connect account.", "error");
      } finally {
        setupBtn.disabled = false;
        setupBtn.textContent = "Connect";
      }
      return;
    }

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
      const minLen = tool === "teamviewer" ? 6 : 1;
      const maxLen = tool === "teamviewer" ? 8 : 64;
      const hint = tool === "teamviewer" ? " (6-8 characters)" : "";
      const newPassword = await modalPrompt(`Set new unattended access password for ${label}${hint}`, "", {
        label: "New password",
        inputType: "password",
      });
      if (newPassword == null) return;
      if (!newPassword.trim()) {
        showToast("Password cannot be empty.", "error");
        return;
      }
      if (newPassword.length < minLen || newPassword.length > maxLen) {
        showToast(`Password must be ${minLen}-${maxLen} characters.`, "error");
        return;
      }
      resetBtn.disabled = true;
      resetBtn.textContent = "…";
      try {
        if (tool === "teamviewer") {
          await apiPost("/api/v1/remote/teamviewer/reset-password", { password: newPassword });
        } else {
          await apiPost("/api/v1/remote/password", { tool, password: newPassword });
        }
        showToast("Password updated. Reloading…", "success");
        loadDashboard({ suppressError: true });
      } catch (err) {
        showToast(err?.message || "Failed to set password.", "error");
      } finally {
        resetBtn.disabled = false;
        resetBtn.textContent = "Reset";
      }
    }
  });
}

function setupCaptureStopDelegation() {
  document.body.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-action='stop'][data-capture-id]");
    if (!button || !elements.captures.list?.contains(button)) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    const captureId = button.dataset.captureId;
    if (!captureId) return;
    button.disabled = true;
    button.textContent = "Stopping…";
    try {
      await apiPost(`/api/v1/capture/active/${encodeURIComponent(captureId)}/stop`);
      showToast("Capture stopped.", "success");
      loadDashboard({ suppressError: true });
    } catch (error) {
      showToast("Unable to stop capture.", "error");
      button.disabled = false;
      button.textContent = "Stop";
    }
  });
}

function applyDashboardData(data) {
  const d = data || {};
  setMetric(elements.metrics.cpu, d.resources?.cpu_percent, "%");
  setMetric(elements.metrics.memory, d.resources?.memory_percent, "%");
  setMetric(elements.metrics.temp, d.resources?.temperature_c, " C", 100);
  setMetric(elements.metrics.storage, d.resources?.disk_percent, "%");
  renderServices(d.services);
  renderNetwork(d.interfaces || []);
  renderCaptures(d.captures || []);
  renderSerialDevices(d.devices || []);
  renderAlerts(d.alerts || []);
  renderRemoteTools(d.tools || []);
}

async function loadDashboard(options = {}) {
  try {
    const payload = await apiGet("/api/v1/dashboard");
    const root = extractData(payload) || {};
    const system = root.system || {};
    const network = root.network || {};
    const modules = root.modules || [];
    const captureModule = modules.find((m) => m.id === "capture") || {};
    const serialModule = modules.find((m) => m.id === "serial") || {};
    const data = {
      resources: system.resources || {},
      services: system.services || {},
      interfaces: network.interfaces || [],
      captures:
        captureModule.data?.captures ||
        captureModule.data?.active_captures ||
        [],
      devices:
        serialModule.data?.devices ||
        serialModule.data?.active_sessions ||
        [],
      alerts: system.alerts || [],
      tools: system.tools || [],
    };
    applyDashboardData(data);
  } catch (error) {
    if (!options.suppressError) {
      showToast("Unable to load dashboard.", "error");
    }
    await loadDashboardFallback(options);
  }
}

async function loadDashboardFallback(options) {
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    setMetric(elements.metrics.cpu, data.resources?.cpu_percent, "%");
    setMetric(elements.metrics.memory, data.resources?.memory_percent, "%");
    setMetric(elements.metrics.temp, data.resources?.temperature_c, " C", 100);
    setMetric(elements.metrics.storage, data.resources?.disk_percent, "%");
    renderServices(data.services);
    renderAlerts(data.alerts || data.monitor?.alerts || []);
  } catch (e) {
    if (!options.suppressError) showToast("Unable to load system status.", "error");
  }
  try {
    const payload = await apiGet("/api/v1/network/interfaces");
    const data = extractData(payload) || {};
    renderNetwork(data.interfaces || []);
  } catch (e) {
    if (elements.network.summary) elements.network.summary.textContent = "Unavailable";
  }
  try {
    const payload = await apiGet("/api/v1/capture/active");
    const data = extractData(payload) || {};
    renderCaptures(data.captures || []);
  } catch (e) {
    if (elements.captures.summary) elements.captures.summary.textContent = "Unavailable";
  }
  try {
    const payload = await apiGet("/api/v1/serial/devices");
    const data = extractData(payload) || {};
    renderSerialDevices(data.devices || []);
  } catch (e) {
    if (elements.serial.summary) elements.serial.summary.textContent = "Unavailable";
  }
  try {
    const payload = await apiGet("/api/v1/remote/status");
    const data = extractData(payload) || {};
    renderRemoteTools(data.tools || []);
  } catch (e) {
    if (elements.remote.summary) elements.remote.summary.textContent = "Unavailable";
  }
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

async function loadNetworkStatusWithOptions(options) {
  try {
    const payload = await apiGet("/api/v1/network/interfaces");
    const data = extractData(payload) || {};
    renderNetwork(data.interfaces || []);
  } catch (error) {
    if (elements.network.summary) elements.network.summary.textContent = "Network status unavailable.";
    if (!options.suppressError) {
      showToast("Unable to load network interfaces.", "error");
    }
  }
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
    loadDashboard({ suppressError: true });
  }, MAX_POLL_INTERVAL);
}

function stopPolling() {
  if (pollId) {
    window.clearInterval(pollId);
    pollId = null;
  }
}

function initStatusWebSocket() {
  onStatusConnection((status) => {
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

  registerStatusHandler("system", "metrics", (data) => {
    const d = data || {};
    setMetric(elements.metrics.cpu, d.resources?.cpu_percent, "%");
    setMetric(elements.metrics.memory, d.resources?.memory_percent, "%");
    setMetric(elements.metrics.temp, d.resources?.temperature_c, " C", 100);
    setMetric(elements.metrics.storage, d.resources?.disk_percent, "%");
    renderServices(d.services);
  });

  registerStatusHandler("network", "interfaces", (data) => {
    const d = data || {};
    renderNetwork(d.interfaces || []);
  });
}

function init() {
  applyWidgetVisibility();
  setupDashboardWidgetPrefs();
  setupPanelButtonDelegation();
  setupRemoteCopyDelegation();
  setupRemotePasswordDelegation();
  setupCaptureStopDelegation();
  loadDashboard();
  initStatusWebSocket();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  stopPolling();
});

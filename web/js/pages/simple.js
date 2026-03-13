import { apiGet, apiPost, apiPut, extractData } from "../api.js";
import { copyTextToClipboard } from "../components.js";
import { modalHelp, modalHelpSections, modalPrompt } from "../modal.js";
import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureSimpleMode, setMode } from "../mode.js";
import { createWebSocketClient } from "../websocket.js";

const elements = {
  health: document.getElementById("system-health"),
  networkInterfaceList: document.getElementById("network-interface-list"),
  wanSummary: document.getElementById("wan-summary"),
  wanStatusBadge: document.getElementById("wan-status-badge"),
  alertsList: document.getElementById("alerts-list"),
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

async function toggleShareWithHotspot(checkbox) {
  const interfaceId = checkbox.dataset.interfaceId;
  if (!interfaceId) return;
  const enabled = checkbox.checked;
  const wrap = checkbox.closest(".network-iface-share-toggle-wrap");
  const loadingEl = wrap?.querySelector(".network-iface-share-loading");
  const allToggles = document.querySelectorAll(".share-with-hotspot-toggle");
  allToggles.forEach((t) => {
    t.disabled = true;
  });
  if (wrap) wrap.classList.add("is-loading");
  if (loadingEl) loadingEl.hidden = false;
  try {
    await apiPut(`/api/v1/network/interfaces/${encodeURIComponent(interfaceId)}/share-with-hotspot`, {
      enabled,
    });
    showToast(enabled ? `Sharing ${interfaceId} with hotspot.` : `Stopped sharing ${interfaceId}.`, "success");
    await loadNetworkInfo();
  } catch (error) {
    checkbox.checked = !enabled;
    showToast("Unable to update connection share.", "error");
  } finally {
    allToggles.forEach((t) => {
      t.disabled = false;
    });
    document.querySelectorAll(".network-iface-share-toggle-wrap.is-loading").forEach((w) => {
      w.classList.remove("is-loading");
    });
    document.querySelectorAll(".network-iface-share-loading").forEach((el) => {
      el.hidden = true;
    });
  }
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
     const role = (iface.role || "").toLowerCase();

    let label = desc;
    if (desc === "Wired" || desc === "USB") {
      label = `${desc} (${name})`;
    } else if (desc === "Hotspot") {
      label = `Hotspot (${name})`;
    }

    const statusClass =
      status === "up" ? "network-iface-up" : "network-iface-down";

    const header = document.createElement("div");
    header.className = "network-iface-header";
    const roleLabel = role || "--";
    const roleClass =
      role === "lan" || role === "wan"
        ? `network-iface-role-badge-${role}`
        : "network-iface-role-badge-neutral";
    header.innerHTML = `
      <div class="network-iface-main">
        <span class="network-iface-dot ${status === "up" ? "is-up" : ""}" aria-hidden="true"></span>
        <div class="network-iface-text">
          <span class="network-iface-label">${escapeHtml(label)}</span>
          <span class="network-iface-ip">${escapeHtml(ip)}</span>
        </div>
      </div>
      <div class="network-iface-meta">
        <span class="network-iface-status ${statusClass}">${status}</span>
        <span class="network-iface-role-badge ${roleClass}">${escapeHtml(
          roleLabel.toUpperCase()
        )}</span>
      </div>
    `;
    li.appendChild(header);

    if (isHotspotInterface(iface) && hotspotStatus === "active") {
      const note = document.createElement("p");
      note.className = "network-iface-note";
      note.textContent = "The wireless hotspot runs on this interface.";
      li.appendChild(note);
    } else if (!isHotspotInterface(iface)) {
      const shareRow = document.createElement("div");
      shareRow.className = "network-iface-share-row";
      const shareWrap = document.createElement("div");
      shareWrap.className = "network-iface-share-toggle-wrap";
      const shareLabel = document.createElement("label");
      shareLabel.className = "toggle network-iface-share-toggle";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "share-with-hotspot-toggle";
      checkbox.checked = iface.share_with_hotspot === true;
      checkbox.setAttribute("aria-label", `Share ${name} with hotspot`);
      checkbox.dataset.interfaceId = name;
      checkbox.addEventListener("change", () => toggleShareWithHotspot(checkbox));
      shareLabel.appendChild(checkbox);
      const shareText = document.createElement("span");
      shareText.className = "network-iface-share-label";
      shareText.textContent = "Share with Hotspot";
      shareLabel.appendChild(shareText);
      shareWrap.appendChild(shareLabel);
      const loadingSpan = document.createElement("span");
      loadingSpan.className = "spinner network-iface-share-loading";
      loadingSpan.setAttribute("aria-hidden", "true");
      loadingSpan.hidden = true;
      shareWrap.appendChild(loadingSpan);
      shareRow.appendChild(shareWrap);
      li.appendChild(shareRow);
    }

    listEl.appendChild(li);
  });
}

function updateNetworkSummary(interfaces) {
  const hasInterfaces = interfaces.length > 0;
  if (elements.quick.capture) {
    elements.quick.capture.textContent = hasInterfaces
      ? "Ready to capture"
      : "No interfaces available";
  }
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
  if (!elements.alertsList) return;
  elements.alertsList.textContent = "";
  elements.alertsList.classList.remove("alerts-empty-state");
  const list = alerts && Array.isArray(alerts) ? alerts : [];
  if (list.length === 0) {
    elements.alertsList.classList.add("alerts-empty-state");
    const item = document.createElement("li");
    item.className = "alerts-empty";
    item.textContent = "No alerts yet.";
    elements.alertsList.appendChild(item);
    return;
  }
  list.slice(0, 5).forEach((alert) => {
    const item = document.createElement("li");
    item.className = "alerts-item";
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
    if (severity) item.classList.add(`alerts-item--${severity}`);
    if (timeStr) {
      item.innerHTML = `<span class="alerts-time">${escapeHtml(timeStr)}</span> <span class="alerts-msg">${escapeHtml(msg)}</span>`;
    } else {
      item.textContent = msg;
    }
    elements.alertsList.appendChild(item);
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
    const healthStatus = typeof data.health === "object" ? data.health?.status : data.health;
    setStatusIndicator(healthStatus ?? data.status);
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
    renderNetworkInterfacesCard(interfaces, networkStatus);
    updateNetworkSummary(interfaces);
    updateWifiInfo(interfaces);
  } catch (error) {
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

function setupCaptureHelp() {
  const btn = document.getElementById("help-capture-btn");
  if (!btn) return;
  const steps = [
    "Go to the Capture section on this page.",
    "Select the network interface you want to capture traffic on from the dropdown.",
    "Press Start Capture. The status will change to show the capture is running.",
    "When you are done, press Stop Capture.",
    "Your capture will appear in the completed captures list.",
    "Press Export to download the capture file.",
  ];
  btn.addEventListener("click", () => {
    modalHelp("How to Run a Packet Capture", steps);
  });
}

function setupAnyDeskHelp() {
  const btn = document.getElementById("help-anydesk-btn");
  if (!btn) return;
  const steps = [
    "Go to the Remote Access section on this page.",
    "Find the AnyDesk ID displayed on the page. It will be a 9-digit number.",
    "If a password is shown or you need to reset it, use the Reset Password button in that section. Note the new password.",
    "Share the AnyDesk ID and password with the person who needs to connect remotely.",
    "When they connect, you may see a prompt to accept the connection — press Accept.",
    "The remote user now has access to this device's desktop.",
  ];
  btn.addEventListener("click", () => {
    modalHelp("How to Share AnyDesk Access", steps);
  });
}

function setupTeamViewerHelp() {
  const btn = document.getElementById("help-teamviewer-btn");
  if (!btn) return;
  const steps = [
    "Go to the Remote Access section on this page.",
    "Find the TeamViewer ID displayed on the page.",
    "If a password is shown or you need to reset it, use the Reset Password button in that section. Note the new password.",
    "Share the TeamViewer ID and password with the person who needs to connect remotely.",
    "The remote user opens TeamViewer, enters your ID, and uses the password to connect.",
    "The remote session will begin automatically.",
  ];
  btn.addEventListener("click", () => {
    modalHelp("How to Share TeamViewer Access", steps);
  });
}

function setupNetworkProfileHelp() {
  const btn = document.getElementById("help-network-profile-btn");
  if (!btn) return;
  const sections = [
    {
      title: "Saving a profile",
      steps: [
        "Go to the Network section and configure your interfaces as needed.",
        "When the settings are correct, find the Profiles area and press Save Profile.",
        "Give the profile a name that describes the site or network (e.g. \"Site A - VLAN10\").",
        "Press Confirm. The profile is now saved and will appear in your profiles list.",
      ],
    },
    {
      title: "Loading a profile",
      steps: [
        "In the Profiles area, find the profile you want to use in the list.",
        "Press Load next to that profile.",
        "The network settings will update to match the saved profile. Confirm any prompt that appears.",
        "Check the interface list to verify the settings are now active.",
      ],
    },
  ];
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    modalHelpSections("How to Save and Load a Network Profile", sections);
  });
}

function setupSerialHelp() {
  const btn = document.getElementById("help-serial-btn");
  if (!btn) return;
  const steps = [
    "Plug your serial device into the Raspberry Pi via USB.",
    "Go to the Serial section. Your device should appear in the device list.",
    "Select the device and choose the correct baud rate and port settings for your device. If unsure, 9600 8N1 is a common default.",
    "Press Connect. A terminal window will open.",
    "You are now in a live serial session. Type commands and press Enter to send them.",
  ];
  const recovery = {
    recoveryTitle: "Device not showing up?",
    recoveryItems: [
      "Unplug the USB cable and plug it back in.",
      "Wait a few seconds, then press the Refresh Devices button.",
      "If the device still does not appear, try a different USB port or cable.",
    ],
  };
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    modalHelp("How to Start a Serial Console Session", steps, recovery);
  });
}

function setupHotspotHelp() {
  const btn = document.getElementById("help-hotspot-btn");
  if (!btn) return;
  const steps = [
    "Take the Jetpack device and connect it to the Raspberry Pi using a USB cable.",
    "On the Jetpack itself, go to its settings menu and enable \"Share Internet via USB\" (sometimes labeled USB Tethering). This tells the Jetpack to pass its internet connection to the Raspberry Pi.",
    "Wait 10–15 seconds. The Raspberry Pi should detect the Jetpack as a new WAN interface.",
    "Go to the Network section and check the interfaces list. You should see a new interface (typically usb0 or similar) with an active connection. This is your WAN (internet) source.",
    "Your LAN interface is the one connected to your local network or devices (typically eth0 or wlan0 and will not show a cellular or USB origin).",
    "Go to the Hotspot section and select the LAN interface to share.",
    "Press Enable Hotspot. Nearby devices can now connect to the hotspot and reach the network through the Raspberry Pi.",
  ];
  const recovery = {
    recoveryTitle: "Not seeing the Jetpack interface?",
    recoveryItems: [
      "Make sure USB Tethering is enabled on the Jetpack (not just Wi-Fi hotspot mode).",
      "Unplug and replug the USB cable.",
      "Wait 15 seconds and refresh the interface list.",
    ],
  };
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    modalHelp("How to Set Up the Hotspot and Connect a Jetpack", steps, recovery);
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
      const maxLen = tool === "teamviewer" ? 8 : 64;
      const hint = tool === "teamviewer" ? " (max 8 characters)" : "";
      const newPassword = await modalPrompt(`Set new unattended access password for ${label}${hint}`, "", {
        label: "New password",
        inputType: "password",
      });
      if (newPassword == null) return;
      if (!newPassword.trim()) {
        showToast("Password cannot be empty.", "error");
        return;
      }
      if (newPassword.length > maxLen) {
        showToast(`Password must be 1-${maxLen} characters.`, "error");
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
    const healthStatus = typeof data.health === "object" ? data.health?.status : data.health;
    setStatusIndicator(healthStatus ?? data.status);
    setMetric("cpu", data.resources?.cpu_percent, "%", elements.meters.cpu);
    setMetric("memory", data.resources?.memory_percent, "%", elements.meters.memory);
    setMetric("temp", data.resources?.temperature_c, " C", elements.meters.temp);
    setMetric(
      "storage",
      data.resources?.disk_percent,
      "%",
      elements.meters.storage
    );
    renderAlerts(data.alerts ?? data.monitor?.alerts);
  });
  statusWs.on("network_status", (message) => {
    const data = message.data || {};
    if (elements.networkInterfaceList) {
      renderNetworkInterfacesCard(lastNetworkInterfaces, data);
    }
  });
  statusWs.on("network_interfaces", (message) => {
    const data = message.data || {};
    const interfaces = data.interfaces || [];
    lastNetworkInterfaces = interfaces;
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

function setupNetworkCardLink() {
  const card = document.getElementById("network-interfaces-card");
  if (!card) {
    return;
  }
  card.addEventListener("click", (e) => {
    const interactive = e.target.closest("button, a, input, label");
    if (interactive) {
      return;
    }
    setMode("advanced");
    window.location.assign("/advanced/network.html");
  });
}

function init() {
  ensureSimpleMode();
  applyStoredTheme();
  initThemeSelector(document.getElementById("theme-select"));
  setupModeSwitch();
  setupCaptureHelp();
  setupAnyDeskHelp();
  setupTeamViewerHelp();
  setupNetworkProfileHelp();
  setupSerialHelp();
  setupHotspotHelp();
  setupQuickActionLinks();
  setupNetworkCardLink();
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

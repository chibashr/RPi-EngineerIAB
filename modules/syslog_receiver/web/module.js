const statusEls = {
  state: document.getElementById("syslog-status-state"),
  bind: document.getElementById("syslog-status-bind"),
  udp: document.getElementById("syslog-status-udp"),
  tcp: document.getElementById("syslog-status-tcp"),
  received: document.getElementById("syslog-status-received"),
  stored: document.getElementById("syslog-status-stored"),
  last: document.getElementById("syslog-status-last"),
};

const configIds = {
  bind_address: "syslog-config-bind",
  port_udp: "syslog-config-port-udp",
  port_tcp: "syslog-config-port-tcp",
  persist: "syslog-config-persist",
  max_live: "syslog-config-max-live",
  max_stored: "syslog-config-max-stored",
};

function getConfigFormValues() {
  return {
    bind_address: document.getElementById(configIds.bind_address)?.value?.trim() || "0.0.0.0",
    port_udp: parseInt(document.getElementById(configIds.port_udp)?.value || "1514", 10),
    port_tcp: parseInt(document.getElementById(configIds.port_tcp)?.value || "1514", 10),
    persist: document.getElementById(configIds.persist)?.checked ?? true,
    max_live: parseInt(document.getElementById(configIds.max_live)?.value || "1000", 10),
    max_stored: parseInt(document.getElementById(configIds.max_stored)?.value || "10000", 10),
  };
}

function setConfigFormValues(config) {
  const el = (id) => document.getElementById(id);
  if (el(configIds.bind_address)) el(configIds.bind_address).value = config.bind_address ?? "0.0.0.0";
  if (el(configIds.port_udp)) el(configIds.port_udp).value = String(config.port_udp ?? 1514);
  if (el(configIds.port_tcp)) el(configIds.port_tcp).value = String(config.port_tcp ?? 1514);
  if (el(configIds.persist)) el(configIds.persist).checked = !!config.persist;
  if (el(configIds.max_live)) el(configIds.max_live).value = String(config.max_live ?? 1000);
  if (el(configIds.max_stored)) el(configIds.max_stored).value = String(config.max_stored ?? 10000);
}

async function loadConfig() {
  try {
    const config = await fetchJson("/api/v1/syslog/config");
    setConfigFormValues(config);
  } catch (error) {
    showToast("Failed to load configuration.", "error");
  }
}

async function saveConfig() {
  const formValues = getConfigFormValues();
  if (formValues.port_udp < 1 || formValues.port_udp > 65535 || formValues.port_tcp < 1 || formValues.port_tcp > 65535) {
    showToast("Ports must be between 1 and 65535.", "error");
    return;
  }
  try {
    const current = await fetchJson("/api/v1/syslog/config");
    const payload = { ...current, ...formValues };
    payload.enabled = !!current.enabled;
    await fetch("/api/v1/syslog/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast("Configuration saved. Receiver will restart if needed.", "success");
    loadConfig();
    refresh();
  } catch (error) {
    showToast("Failed to save configuration.", "error");
  }
}

const recentTable = document.querySelector("#syslog-recent-table tbody");
const storedTable = document.querySelector("#syslog-stored-table tbody");

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  const payload = await response.json();
  return payload?.data ?? payload;
}

function renderRows(tableBody, items) {
  if (!tableBody) {
    return;
  }
  tableBody.textContent = "";
  if (!items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "No messages received.";
    row.appendChild(cell);
    tableBody.appendChild(row);
    return;
  }
  items.forEach((entry) => {
    const row = document.createElement("tr");
    const received = document.createElement("td");
    received.textContent = entry.received_at || "--";
    const source = document.createElement("td");
    source.textContent = entry.source_ip || "--";
    const host = document.createElement("td");
    host.textContent = entry.hostname || "--";
    const facility = document.createElement("td");
    facility.textContent = entry.facility ?? "--";
    const severity = document.createElement("td");
    severity.textContent = entry.severity ?? "--";
    const app = document.createElement("td");
    app.textContent = entry.app_name || "--";
    const message = document.createElement("td");
    message.textContent = entry.message || "--";
    row.append(received, source, host, facility, severity, app, message);
    tableBody.appendChild(row);
  });
}

function updateControlButtons(running) {
  const startBtn = document.getElementById("syslog-start");
  const stopBtn = document.getElementById("syslog-stop");
  const restartBtn = document.getElementById("syslog-restart");
  if (startBtn) startBtn.disabled = !!running;
  if (stopBtn) stopBtn.disabled = !running;
  if (restartBtn) {
    restartBtn.disabled = !running;
    restartBtn.style.display = running ? "" : "none";
  }
}

async function refresh() {
  try {
    const status = await fetchJson("/api/v1/syslog/status");
    if (statusEls.state) {
      statusEls.state.textContent = status.running
        ? "Running"
        : status.enabled
        ? "Stopped"
        : "Stopped";
    }
    updateControlButtons(!!status.running);
    if (statusEls.bind) {
      statusEls.bind.textContent = status.bind_address || "--";
    }
    if (statusEls.udp) {
      statusEls.udp.textContent = status.port_udp ?? "--";
    }
    if (statusEls.tcp) {
      statusEls.tcp.textContent = status.port_tcp ?? "--";
    }
    if (statusEls.received) {
      statusEls.received.textContent = status.received_count ?? "--";
    }
    if (statusEls.stored) {
      statusEls.stored.textContent = status.stored_count ?? "--";
    }
    if (statusEls.last) {
      statusEls.last.textContent = status.last_received ?? "--";
    }
  } catch (error) {
    if (statusEls.state) {
      statusEls.state.textContent = "Error";
    }
  }

  try {
    const recent = await fetchJson("/api/v1/syslog/recent?limit=50");
    renderRows(recentTable, recent.items || []);
  } catch (error) {
    renderRows(recentTable, []);
  }

  try {
    const stored = await fetchJson("/api/v1/syslog/stored?limit=50");
    renderRows(storedTable, stored.items || []);
  } catch (error) {
    renderRows(storedTable, []);
  }
}

function showToast(message, variant) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const toast = document.createElement("div");
  toast.className = `toast ${variant || "info"}`;
  toast.textContent = message;
  region.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

async function clearBuffers() {
  try {
    const res = await fetch("/api/v1/syslog/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: "all" }),
    });
    if (!res.ok) throw new Error("Clear failed");
    showToast("Buffers cleared.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to clear buffers.", "error");
  }
}

async function startReceiver() {
  try {
    await fetch("/api/v1/syslog/start", { method: "POST" });
    showToast("Receiver started.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to start receiver.", "error");
  }
}

async function stopReceiver() {
  try {
    await fetch("/api/v1/syslog/stop", { method: "POST" });
    showToast("Receiver stopped.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to stop receiver.", "error");
  }
}

async function restartReceiver() {
  try {
    await fetch("/api/v1/syslog/restart", { method: "POST" });
    showToast("Receiver restarted.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to restart receiver.", "error");
  }
}

function formatBytes(n) {
  if (n >= 1073741824) return (n / 1073741824).toFixed(1) + " GB";
  if (n >= 1048576) return (n / 1048576).toFixed(1) + " MB";
  if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
  return String(n);
}

async function loadStorage() {
  const pathEl = document.getElementById("syslog-storage-path");
  const tbody = document.querySelector("#syslog-storage-files tbody");
  if (!pathEl || !tbody) return;
  try {
    const data = await fetchJson("/api/v1/syslog/storage");
    pathEl.textContent = data.path || "--";
    const summaryEl = document.getElementById("syslog-storage-summary");
    if (summaryEl) summaryEl.textContent = `Stored messages: ${data.stored_count ?? "--"} (see Stored Messages table above)`;
    tbody.textContent = "";
    const files = data.files || [];
    if (!files.length) {
      const row = document.createElement("tr");
      row.innerHTML = "<td colspan=\"3\">No files</td>";
      tbody.appendChild(row);
      return;
    }
    files.forEach((f) => {
      const row = document.createElement("tr");
      const name = document.createElement("td");
      name.textContent = f.name || "--";
      const size = document.createElement("td");
      size.textContent = formatBytes(f.size ?? 0);
      const mod = document.createElement("td");
      mod.textContent = f.modified ? new Date(f.modified).toLocaleString() : "--";
      row.append(name, size, mod);
      tbody.appendChild(row);
    });
  } catch (err) {
    pathEl.textContent = "Failed to load";
    tbody.textContent = "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadConfig();
  refresh();
  loadStorage();
  setInterval(refresh, 5000);

  const refreshBtn = document.getElementById("refresh-syslog");
  if (refreshBtn) refreshBtn.addEventListener("click", () => refresh());

  const clearBtn = document.getElementById("clear-syslog");
  if (clearBtn) clearBtn.addEventListener("click", clearBuffers);

  const saveConfigBtn = document.getElementById("syslog-save-config");
  if (saveConfigBtn) saveConfigBtn.addEventListener("click", saveConfig);

  const startBtn = document.getElementById("syslog-start");
  if (startBtn) startBtn.addEventListener("click", startReceiver);
  const stopBtn = document.getElementById("syslog-stop");
  if (stopBtn) stopBtn.addEventListener("click", stopReceiver);
  const restartBtn = document.getElementById("syslog-restart");
  if (restartBtn) restartBtn.addEventListener("click", restartReceiver);

  const refreshStorageBtn = document.getElementById("syslog-refresh-storage");
  if (refreshStorageBtn) refreshStorageBtn.addEventListener("click", loadStorage);
});

const statusEls = {
  state: document.getElementById("snmp-status-state"),
  bind: document.getElementById("snmp-status-bind"),
  received: document.getElementById("snmp-status-received"),
  stored: document.getElementById("snmp-status-stored"),
  last: document.getElementById("snmp-status-last"),
};

const recentTable = document.querySelector("#snmp-recent-table tbody");
const storedTable = document.querySelector("#snmp-stored-table tbody");

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  const payload = await response.json();
  return payload?.data ?? payload;
}

function formatVarbinds(varbinds) {
  if (!Array.isArray(varbinds) || !varbinds.length) {
    return "--";
  }
  return varbinds
    .map((item) => `${item.oid}: ${item.value}`)
    .join(" | ");
}

function renderRows(tableBody, items) {
  if (!tableBody) {
    return;
  }
  tableBody.textContent = "";
  if (!items.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No traps received.";
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
    const oid = document.createElement("td");
    oid.textContent = entry.trap_oid || "--";
    const varbinds = document.createElement("td");
    varbinds.textContent = formatVarbinds(entry.varbinds);
    row.append(received, source, oid, varbinds);
    tableBody.appendChild(row);
  });
}

const configIds = {
  bind_address: "snmp-config-bind",
  port: "snmp-config-port",
  persist: "snmp-config-persist",
  max_live: "snmp-config-max-live",
  max_stored: "snmp-config-max-stored",
};

function getConfigFormValues() {
  return {
    bind_address: document.getElementById(configIds.bind_address)?.value?.trim() || "0.0.0.0",
    port: parseInt(document.getElementById(configIds.port)?.value || "1162", 10),
    persist: document.getElementById(configIds.persist)?.checked ?? true,
    max_live: parseInt(document.getElementById(configIds.max_live)?.value || "500", 10),
    max_stored: parseInt(document.getElementById(configIds.max_stored)?.value || "10000", 10),
  };
}

function setConfigFormValues(config) {
  const el = (id) => document.getElementById(id);
  if (el(configIds.bind_address)) el(configIds.bind_address).value = config.bind_address ?? "0.0.0.0";
  if (el(configIds.port)) el(configIds.port).value = String(config.port ?? 1162);
  if (el(configIds.persist)) el(configIds.persist).checked = !!config.persist;
  if (el(configIds.max_live)) el(configIds.max_live).value = String(config.max_live ?? 500);
  if (el(configIds.max_stored)) el(configIds.max_stored).value = String(config.max_stored ?? 10000);
}

async function loadConfig() {
  try {
    const config = await fetchJson("/api/v1/snmp_traps/config");
    setConfigFormValues(config);
  } catch (error) {
    showToast("Failed to load configuration.", "error");
  }
}

async function saveConfig() {
  const formValues = getConfigFormValues();
  if (formValues.port < 1 || formValues.port > 65535) {
    showToast("Port must be between 1 and 65535.", "error");
    return;
  }
  try {
    const current = await fetchJson("/api/v1/snmp_traps/config");
    const payload = { ...current, ...formValues };
    payload.enabled = !!current.enabled;
    await fetch("/api/v1/snmp_traps/config", {
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

const PLAY_ICON = '<path fill-rule="evenodd" d="M4.5 5.653c0-1.427 1.529-2.33 2.779-1.643l11.54 6.347c1.295.712 1.295 2.573 0 3.286L7.28 19.99c-1.25.687-2.779-.217-2.779-1.643V5.653Z" clip-rule="evenodd"/>';
const STOP_ICON = '<path fill-rule="evenodd" d="M4.5 7.5a3 3 0 0 1 3-3h9a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3h-9a3 3 0 0 1-3-3v-9Z" clip-rule="evenodd"/>';

function updateControlButtons(running) {
  const toggleBtn = document.getElementById("snmp-toggle");
  const toggleIcon = document.getElementById("snmp-toggle-icon");
  const toggleLabel = document.getElementById("snmp-toggle-label");
  const restartBtn = document.getElementById("snmp-restart");

  if (toggleBtn && toggleIcon && toggleLabel) {
    if (running) {
      toggleBtn.dataset.state = "running";
      toggleIcon.innerHTML = STOP_ICON;
      toggleLabel.textContent = "Stop";
    } else {
      toggleBtn.dataset.state = "stopped";
      toggleIcon.innerHTML = PLAY_ICON;
      toggleLabel.textContent = "Start";
    }
  }

  if (restartBtn) {
    restartBtn.disabled = !running;
  }
}

async function refresh() {
  try {
    const status = await fetchJson("/api/v1/snmp_traps/status");
    if (statusEls.state) {
      statusEls.state.textContent = status.running
        ? "Running"
        : status.enabled
        ? "Stopped"
        : "Stopped";
    }
    updateControlButtons(!!status.running);
    if (statusEls.bind) {
      const bind = status.bind_address && status.port ? `${status.bind_address}:${status.port}` : "--";
      statusEls.bind.textContent = bind;
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
    const recent = await fetchJson("/api/v1/snmp_traps/recent?limit=50");
    renderRows(recentTable, recent.items || []);
  } catch (error) {
    renderRows(recentTable, []);
  }

  try {
    const stored = await fetchJson("/api/v1/snmp_traps/stored?limit=50");
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
    const res = await fetch("/api/v1/snmp_traps/clear", {
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
    await fetch("/api/v1/snmp_traps/start", { method: "POST" });
    showToast("Receiver started.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to start receiver.", "error");
  }
}

async function stopReceiver() {
  try {
    await fetch("/api/v1/snmp_traps/stop", { method: "POST" });
    showToast("Receiver stopped.", "success");
    refresh();
  } catch (err) {
    showToast("Failed to stop receiver.", "error");
  }
}

async function restartReceiver() {
  try {
    await fetch("/api/v1/snmp_traps/restart", { method: "POST" });
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
  const pathEl = document.getElementById("snmp-storage-path");
  const tbody = document.querySelector("#snmp-storage-files tbody");
  if (!pathEl || !tbody) return;
  try {
    const data = await fetchJson("/api/v1/snmp_traps/storage");
    pathEl.textContent = data.path || "--";
    const summaryEl = document.getElementById("snmp-storage-summary");
    if (summaryEl) summaryEl.textContent = `Stored traps: ${data.stored_count ?? "--"} (see Stored Traps table above)`;
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

  const clearBtn = document.getElementById("clear-snmp");
  if (clearBtn) clearBtn.addEventListener("click", clearBuffers);

  const saveConfigBtn = document.getElementById("snmp-save-config");
  if (saveConfigBtn) saveConfigBtn.addEventListener("click", saveConfig);

  const toggleBtn = document.getElementById("snmp-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      const isRunning = toggleBtn.dataset.state === "running";
      if (isRunning) {
        stopReceiver();
      } else {
        startReceiver();
      }
    });
  }

  const restartBtn = document.getElementById("snmp-restart");
  if (restartBtn) restartBtn.addEventListener("click", restartReceiver);

  const refreshStorageBtn = document.getElementById("snmp-refresh-storage");
  if (refreshStorageBtn) refreshStorageBtn.addEventListener("click", loadStorage);
});

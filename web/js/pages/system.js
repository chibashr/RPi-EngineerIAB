import { apiGet, apiPost, extractData } from "../api.js";
import { initTabs } from "../components.js";
import { modalConfirm } from "../modal.js";

const elements = {
  serviceTable: document.getElementById("service-table-body"),
  info: {
    hostname: document.getElementById("info-hostname"),
    version: document.getElementById("info-version"),
    model: document.getElementById("info-model"),
    os: document.getElementById("info-os"),
  },
  inputs: {
    hostname: document.getElementById("hostname-input"),
    timezone: document.getElementById("timezone-input"),
    preferredMode: document.getElementById("preferred-mode"),
  },
};

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

function categoryLabel(category) {
  if (category === "core") return "Core app";
  if (category === "system") return "System";
  if (category === "optional") return "Optional";
  return category || "--";
}

/** CSS class for status cell (e.g. status-running, status-failed). */
function statusClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "running") return "status-running";
  if (s === "stopped") return "status-stopped";
  if (s === "starting" || s === "stopping") return "status-transitioning";
  if (s === "failed") return "status-failed";
  return "status-unknown";
}

/** True if service is considered running (show Stop). */
function isRunning(status) {
  const s = (status || "").toLowerCase();
  return s === "running";
}

/** True if service is in a transition (disable Start/Stop). */
function isTransitioning(status) {
  const s = (status || "").toLowerCase();
  return s === "starting" || s === "stopping";
}

function renderServices(servicesList) {
  if (!elements.serviceTable) {
    return;
  }
  elements.serviceTable.textContent = "";
  if (!servicesList || !Array.isArray(servicesList) || servicesList.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No services reported.";
    row.appendChild(cell);
    elements.serviceTable.appendChild(row);
    return;
  }

  servicesList.forEach(({ name, status, category }) => {
    const row = document.createElement("tr");
    row.dataset.serviceName = name;

    const checkCell = document.createElement("td");
    checkCell.className = "col-check";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.className = "service-checkbox";
    check.dataset.serviceName = name;
    check.setAttribute("aria-label", `Select ${name}`);
    checkCell.appendChild(check);
    row.appendChild(checkCell);

    const nameCell = document.createElement("td");
    nameCell.textContent = name || "--";
    row.appendChild(nameCell);

    const catCell = document.createElement("td");
    catCell.textContent = categoryLabel(category);
    row.appendChild(catCell);

    const statusCell = document.createElement("td");
    statusCell.textContent = status || "unknown";
    statusCell.className = `service-status ${statusClass(status)}`;
    row.appendChild(statusCell);

    const actionsCell = document.createElement("td");
    actionsCell.className = "col-actions service-actions";
    const run = isRunning(status);
    const transitioning = isTransitioning(status);
    const toggleBtn = document.createElement("button");
    toggleBtn.type = "button";
    toggleBtn.className = "btn btn-ghost btn-service-action btn-service-toggle";
    toggleBtn.textContent = run ? "Stop" : "Start";
    toggleBtn.dataset.serviceName = name;
    toggleBtn.dataset.action = run ? "stop" : "start";
    if (transitioning) {
      toggleBtn.disabled = true;
      toggleBtn.setAttribute("aria-label", `Service is ${status}`);
    }
    actionsCell.appendChild(toggleBtn);
    const restartBtn = document.createElement("button");
    restartBtn.type = "button";
    restartBtn.className = "btn btn-ghost btn-service-action";
    restartBtn.textContent = "Restart";
    restartBtn.dataset.serviceName = name;
    restartBtn.dataset.action = "restart";
    if (transitioning) restartBtn.disabled = true;
    actionsCell.appendChild(restartBtn);
    row.appendChild(actionsCell);

    elements.serviceTable.appendChild(row);
  });
}

function getSelectedServiceNames() {
  const checkboxes = document.querySelectorAll(".service-checkbox:checked");
  return Array.from(checkboxes).map((cb) => cb.dataset.serviceName).filter(Boolean);
}

function setAllServiceCheckboxes(checked) {
  document.querySelectorAll(".service-checkbox").forEach((cb) => {
    cb.checked = !!checked;
  });
}

function runBulkAction(action) {
  const services = getSelectedServiceNames();
  if (services.length === 0) {
    showToast("Select one or more services first.", "error");
    return;
  }
  apiPost("/api/v1/system/services/bulk", { services, action })
    .then((payload) => {
      const data = extractData(payload) || {};
      const results = data.results || [];
      const failed = results.filter((r) => r.status === "error");
      if (failed.length > 0) {
        const msg = failed.map((r) => `${r.service}: ${r.error || "failed"}`).join("; ");
        showToast(msg, "error");
      } else {
        showToast(`${action} completed for ${services.length} service(s).`, "success");
      }
      loadServices();
    })
    .catch(() => showToast(`Unable to ${action} selected services.`, "error"));
}

function runSingleAction(serviceName, action) {
  apiPost("/api/v1/system/services", { service: serviceName, action })
    .then(() => {
      showToast(`${action} completed for ${serviceName}.`, "success");
      loadServices();
    })
    .catch(() => showToast(`Unable to ${action} ${serviceName}.`, "error"));
}

function loadServices() {
  apiGet("/api/v1/system/services")
    .then((payload) => {
      const data = extractData(payload) || {};
      renderServices(data.services);
      setupServiceActionListeners();
    })
    .catch(() => {
      showToast("Unable to load services.", "error");
      if (elements.serviceTable) {
        elements.serviceTable.innerHTML = "";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 5;
        cell.textContent = "Unable to load services.";
        row.appendChild(cell);
        elements.serviceTable.appendChild(row);
      }
    });
}

function setupServiceActionListeners() {
  document.querySelectorAll(".btn-service-action").forEach((btn) => {
    btn.replaceWith(btn.cloneNode(true));
  });
  document.querySelectorAll(".btn-service-action").forEach((btn) => {
    const name = btn.dataset.serviceName;
    const action = btn.dataset.action;
    if (!name || !action) return;
    btn.addEventListener("click", () => runSingleAction(name, action));
  });
}

function renderInfo(info) {
  if (!elements.info.hostname) {
    return;
  }
  elements.info.hostname.textContent = info?.hostname || "--";
  elements.info.version.textContent = info?.version || "--";
  elements.info.model.textContent = info?.model || "--";
  elements.info.os.textContent = info?.os || "--";
}

async function loadSystemData() {
  loadServices();
  try {
    const payload = await apiGet("/api/v1/system/info");
    const data = extractData(payload) || {};
    renderInfo(data);
  } catch (error) {
    showToast("Unable to load system info.", "error");
  }
}

function setupActions() {
  const startSelected = document.getElementById("service-start-selected");
  if (startSelected) {
    startSelected.addEventListener("click", () => runBulkAction("start"));
  }
  const stopSelected = document.getElementById("service-stop-selected");
  if (stopSelected) {
    stopSelected.addEventListener("click", () => runBulkAction("stop"));
  }
  const restartSelected = document.getElementById("service-restart-selected");
  if (restartSelected) {
    restartSelected.addEventListener("click", () => runBulkAction("restart"));
  }
  const selectAll = document.getElementById("service-select-all");
  if (selectAll) {
    selectAll.addEventListener("click", () => setAllServiceCheckboxes(true));
  }
  const selectNone = document.getElementById("service-select-none");
  if (selectNone) {
    selectNone.addEventListener("click", () => setAllServiceCheckboxes(false));
  }

  const restartSystem = document.getElementById("restart-system");
  if (restartSystem) {
    restartSystem.addEventListener("click", async () => {
      const confirmed = await modalConfirm("Restart the system now?");
      if (!confirmed) {
        return;
      }
      apiPost("/api/v1/system/power", { action: "reboot" })
        .then(() => showToast("System reboot scheduled.", "success"))
        .catch(() => showToast("Unable to reboot system.", "error"));
    });
  }

  const shutdownSystem = document.getElementById("shutdown-system");
  if (shutdownSystem) {
    shutdownSystem.addEventListener("click", async () => {
      const confirmed = await modalConfirm("Shut down the system now?");
      if (!confirmed) {
        return;
      }
      apiPost("/api/v1/system/power", { action: "shutdown" })
        .then(() => showToast("System shutdown scheduled.", "success"))
        .catch(() => showToast("Unable to shut down system.", "error"));
    });
  }

  const saveSettings = document.getElementById("save-settings");
  if (saveSettings) {
    saveSettings.addEventListener("click", () => {
      const hostname = elements.inputs.hostname?.value?.trim() || "";
      const timezone = elements.inputs.timezone?.value?.trim() || "";
      const preferredMode = elements.inputs.preferredMode?.value || "simple";
      if (!hostname) {
        showToast("Hostname is required.", "error");
        return;
      }
      if (!timezone) {
        showToast("Timezone is required.", "error");
        return;
      }
      apiPost("/api/v1/system/settings", {
        hostname,
        timezone,
        preferred_mode: preferredMode,
      })
        .then(() => {
          showToast("Settings saved.", "success");
          loadSystemData();
        })
        .catch(() => showToast("Unable to save settings.", "error"));
    });
  }
}

function init() {
  initTabs(document.querySelector("[data-tabs]"));
  const refresh = document.getElementById("refresh-system");
  if (refresh) {
    refresh.addEventListener("click", loadSystemData);
  }
  setupActions();
  loadSystemData();
}

document.addEventListener("DOMContentLoaded", init);

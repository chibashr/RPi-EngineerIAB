import { apiGet, apiPost, extractData } from "../api.js";
import { initTabs } from "../components.js";

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
let serviceNames = [];

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

function renderServices(services) {
  if (!elements.serviceTable) {
    return;
  }
  serviceNames = services ? Object.keys(services) : [];
  elements.serviceTable.textContent = "";
  if (!services || Object.keys(services).length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "No services reported.";
    row.appendChild(cell);
    elements.serviceTable.appendChild(row);
    return;
  }

  Object.entries(services).forEach(([name, status]) => {
    const row = document.createElement("tr");
    [name, status, "--"].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });
    elements.serviceTable.appendChild(row);
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
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    renderServices(data.services);
  } catch (error) {
    showToast("Unable to load services.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/system/info");
    const data = extractData(payload) || {};
    renderInfo(data);
  } catch (error) {
    showToast("Unable to load system info.", "error");
  }
}

function setupActions() {
  const restartSelected = document.getElementById("restart-selected");
  if (restartSelected) {
    restartSelected.addEventListener("click", () => {
      const service = window.prompt(
        "Enter the service to restart:",
        serviceNames[0] || ""
      );
      if (!service) {
        return;
      }
      apiPost("/api/v1/system/services", { service, action: "restart" })
        .then(() => {
          showToast(`Restarted ${service}.`, "success");
          loadSystemData();
        })
        .catch(() => showToast("Unable to restart service.", "error"));
    });
  }

  const restartSystem = document.getElementById("restart-system");
  if (restartSystem) {
    restartSystem.addEventListener("click", () => {
      const confirmed = window.confirm("Restart the system now?");
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
    shutdownSystem.addEventListener("click", () => {
      const confirmed = window.confirm("Shut down the system now?");
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

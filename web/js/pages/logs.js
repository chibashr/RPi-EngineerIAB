import { apiGet, extractData } from "../api.js";
import { initTabs, createStatusItem } from "../components.js";
import { setAlerts, formatAlertTimestamp } from "../notifications.js";

const elements = {
  logList: document.getElementById("log-file-list"),
  logSelect: document.getElementById("log-file-select"),
  logTail: document.getElementById("log-tail"),
  logLevel: document.getElementById("log-level"),
  logService: document.getElementById("log-service"),
  logSearch: document.getElementById("log-search"),
  logContent: document.getElementById("log-content"),
  metricsList: document.getElementById("metrics-list"),
  alertsList: document.getElementById("alerts-list"),
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

function renderLogs(files) {
  if (!elements.logList) {
    return;
  }
  elements.logList.textContent = "";
  if (elements.logSelect) {
    const current = elements.logSelect.value;
    elements.logSelect.textContent = "";
    if (files.length) {
      files.forEach((file) => {
        const option = document.createElement("option");
        option.value = file.name;
        option.textContent = file.name;
        elements.logSelect.appendChild(option);
      });
      if (current) {
        elements.logSelect.value = current;
      }
    } else {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No logs available";
      elements.logSelect.appendChild(option);
    }
  }
  if (!files.length) {
    const item = document.createElement("li");
    item.textContent = "No log files available.";
    elements.logList.appendChild(item);
    return;
  }

  files.forEach((file) => {
    const label = file.name || "Log file";
    const value = file.modified || "Unknown";
    elements.logList.appendChild(createStatusItem(label, value));
  });
}

function renderMetrics(metrics) {
  if (!elements.metricsList) {
    return;
  }
  elements.metricsList.textContent = "";
  if (!metrics || Object.keys(metrics).length === 0) {
    const item = document.createElement("li");
    item.textContent = "No metrics available.";
    elements.metricsList.appendChild(item);
    return;
  }
  elements.metricsList.appendChild(
    createStatusItem("CPU Usage", `${metrics.cpu_percent ?? "--"}%`)
  );
  elements.metricsList.appendChild(
    createStatusItem("Memory Usage", `${metrics.memory_percent ?? "--"}%`)
  );
  elements.metricsList.appendChild(
    createStatusItem("Disk Usage", `${metrics.disk_percent ?? "--"}%`)
  );
  if (metrics.temperature_c !== null && metrics.temperature_c !== undefined) {
    elements.metricsList.appendChild(
      createStatusItem("Temperature", `${metrics.temperature_c} C`)
    );
  }
}

function renderAlerts(alerts) {
  if (!elements.alertsList) {
    return;
  }
  elements.alertsList.textContent = "";
  if (!alerts?.length) {
    const item = document.createElement("li");
    item.textContent = "No alerts reported.";
    elements.alertsList.appendChild(item);
    return;
  }
  alerts.forEach((alert) => {
    const label = `${alert.severity || "info"}`.toUpperCase();
    const timeStr = formatAlertTimestamp(alert.timestamp);
    const value = timeStr ? `${timeStr} — ${alert.message || "Alert"}` : (alert.message || "Alert");
    elements.alertsList.appendChild(createStatusItem(label, value));
  });
}

function renderLogContent(lines) {
  if (!elements.logContent) {
    return;
  }
  if (!lines?.length) {
    elements.logContent.textContent = "No log entries returned.";
    return;
  }
  elements.logContent.textContent = lines.join("\n");
}

async function loadLogs() {
  try {
    const payload = await apiGet("/api/v1/logs/system");
    const data = extractData(payload) || {};
    renderLogs(data.files || []);
    if (elements.logSelect?.value) {
      loadLogContent();
    }
  } catch (error) {
    showToast("Unable to load logs.", "error");
  }
}

async function loadLogContent() {
  if (!elements.logSelect || !elements.logSelect.value) {
    renderLogContent([]);
    return;
  }
  const params = new URLSearchParams();
  params.set("file", elements.logSelect.value);
  if (elements.logTail?.value) {
    params.set("tail", elements.logTail.value);
  }
  if (elements.logLevel?.value) {
    params.set("level", elements.logLevel.value);
  }
  if (elements.logService?.value) {
    params.set("service", elements.logService.value);
  }
  if (elements.logSearch?.value) {
    params.set("search", elements.logSearch.value);
  }
  try {
    const payload = await apiGet(`/api/v1/logs/system?${params.toString()}`);
    const data = extractData(payload) || {};
    renderLogContent(data.lines || []);
  } catch (error) {
    showToast("Unable to load log content.", "error");
  }
}

async function loadMonitor() {
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    const monitor = data.monitor || {};
    const alerts = data.alerts || monitor.alerts || [];
    renderMetrics(monitor.metrics || data.resources);
    renderAlerts(alerts);
    setAlerts(alerts);
  } catch (error) {
    showToast("Unable to load monitoring data.", "error");
  }
}

function setupActions() {
  const exportButton = document.getElementById("export-logs");
  if (exportButton) {
    exportButton.addEventListener("click", () => {
      window.location.assign("/api/v1/logs/export");
    });
  }
  const loadButton = document.getElementById("load-log");
  if (loadButton) {
    loadButton.addEventListener("click", loadLogContent);
  }
  if (elements.logSelect) {
    elements.logSelect.addEventListener("change", loadLogContent);
  }
}

function init() {
  initTabs(document.querySelector("[data-tabs]"), { useHash: true });
  const refresh = document.getElementById("refresh-logs");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadLogs();
      loadMonitor();
    });
  }
  setupActions();
  loadLogs();
  loadMonitor();
}

document.addEventListener("DOMContentLoaded", init);

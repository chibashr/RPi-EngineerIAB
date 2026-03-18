import { apiGet, extractData } from "../api.js";
import { initTabs } from "../components.js";
import { setAlerts, formatAlertTimestamp } from "../notifications.js";

const elements = {
  logSelect: document.getElementById("log-file-select"),
  logTail: document.getElementById("log-tail"),
  logLevel: document.getElementById("log-level"),
  logService: document.getElementById("log-service"),
  logSearch: document.getElementById("log-search"),
  logContent: document.getElementById("log-content"),
  metricsRow: document.getElementById("metrics-row"),
  alertsTableBody: document.getElementById("alerts-table-body"),
  alertsSearch: document.getElementById("alerts-search"),
  alertsPerPage: document.getElementById("alerts-per-page"),
  alertsPagination: document.getElementById("alerts-pagination"),
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
  if (elements.logSelect) {
    const current = elements.logSelect.value;
    elements.logSelect.textContent = "";

    // Add "All" option first
    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = "All";
    elements.logSelect.appendChild(allOption);

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
}

function setMetric(element, value, unit, maxValue = 100) {
  if (!element) return;
  const valueEl = element.querySelector(".metric-value");
  const meterEl = element.querySelector(".meter-fill");
  if (!valueEl || !meterEl) return;

  const safeValue = Number.isFinite(value) ? value : null;
  const percentValue =
    safeValue === null
      ? null
      : Math.min(Math.max((safeValue / maxValue) * 100, 0), 100);

  valueEl.textContent = safeValue === null ? `--${unit}` : `${safeValue}${unit}`;
  meterEl.style.width = percentValue === null ? "0%" : `${percentValue}%`;
}

function formatUptime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "--";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function renderMetrics(metrics, uptimeSeconds) {
  if (!elements.metricsRow) {
    return;
  }
  elements.metricsRow.textContent = "";
  if (!metrics || Object.keys(metrics).length === 0) {
    const msg = document.createElement("p");
    msg.textContent = "No metrics available.";
    msg.className = "empty-state";
    elements.metricsRow.appendChild(msg);
    return;
  }

  // CPU
  const cpuCard = document.createElement("div");
  cpuCard.className = "metric-card";
  cpuCard.innerHTML = `
    <div class="metric-label">CPU</div>
    <div class="metric-value">--%</div>
    <div class="meter">
      <div class="meter-fill"></div>
    </div>
  `;
  elements.metricsRow.appendChild(cpuCard);
  setMetric(cpuCard, metrics.cpu_percent, "%");

  // Memory
  const memoryCard = document.createElement("div");
  memoryCard.className = "metric-card";
  memoryCard.innerHTML = `
    <div class="metric-label">Memory</div>
    <div class="metric-value">--%</div>
    <div class="meter">
      <div class="meter-fill"></div>
    </div>
  `;
  elements.metricsRow.appendChild(memoryCard);
  setMetric(memoryCard, metrics.memory_percent, "%");

  // Temperature
  if (metrics.temperature_c !== null && metrics.temperature_c !== undefined) {
    const tempCard = document.createElement("div");
    tempCard.className = "metric-card";
    tempCard.innerHTML = `
      <div class="metric-label">Temperature</div>
      <div class="metric-value">-- C</div>
      <div class="meter">
        <div class="meter-fill"></div>
      </div>
    `;
    elements.metricsRow.appendChild(tempCard);
    setMetric(tempCard, metrics.temperature_c, " C", 100);
  }

  // Storage
  const storageCard = document.createElement("div");
  storageCard.className = "metric-card";
  storageCard.innerHTML = `
    <div class="metric-label">Storage</div>
    <div class="metric-value">--%</div>
    <div class="meter">
      <div class="meter-fill"></div>
    </div>
  `;
  elements.metricsRow.appendChild(storageCard);
  setMetric(storageCard, metrics.disk_percent, "%");

  // Uptime
  if (uptimeSeconds !== null && uptimeSeconds !== undefined) {
    const uptimeCard = document.createElement("div");
    uptimeCard.className = "metric-card";
    uptimeCard.innerHTML = `
      <div class="metric-label">Uptime</div>
      <div class="metric-value">--</div>
      <div class="meter">
        <div class="meter-fill" style="width: 100%; opacity: 0.3;"></div>
      </div>
    `;
    const uptimeValue = uptimeCard.querySelector(".metric-value");
    if (uptimeValue) {
      uptimeValue.textContent = formatUptime(uptimeSeconds);
    }
    elements.metricsRow.appendChild(uptimeCard);
  }
}

function alertKey(alert) {
  const ts = alert.timestamp || "";
  const msg = (alert.message || "").slice(0, 80);
  return `${ts}|${msg}`;
}

function loadDismissed() {
  try {
    const raw = localStorage.getItem("rpi-alerts-dismissed");
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr.slice(-200) : []);
  } catch {
    return new Set();
  }
}

function renderAlerts(alerts, searchTerm = "", pageSize = 20, page = 1) {
  if (!elements.alertsTableBody) {
    return;
  }
  elements.alertsTableBody.textContent = "";
  if (!alerts?.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No alerts reported.";
    cell.className = "empty-state";
    row.appendChild(cell);
    elements.alertsTableBody.appendChild(row);
    return;
  }

  const dismissed = loadDismissed();
  const searchLower = searchTerm.toLowerCase();
  const filteredAlerts = alerts.filter((alert) => {
    if (searchTerm) {
      const message = (alert.message || "").toLowerCase();
      const severity = (alert.severity || "").toLowerCase();
      return message.includes(searchLower) || severity.includes(searchLower);
    }
    return true;
  });

  if (filteredAlerts.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No alerts match your search.";
    cell.className = "empty-state";
    row.appendChild(cell);
    elements.alertsTableBody.appendChild(row);
    return;
  }

  const total = filteredAlerts.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.max(1, Math.min(page, pageCount));
  const start = (safePage - 1) * pageSize;
  const pageAlerts = filteredAlerts.slice(start, start + pageSize);

  pageAlerts.forEach((alert) => {
    const row = document.createElement("tr");
    const isDismissed = dismissed.has(alertKey(alert));
    const severity = (alert.severity || "info").toLowerCase();

    // Severity cell with badge
    const severityCell = document.createElement("td");
    const severityBadge = document.createElement("span");
    severityBadge.className = `status-pill status-pill-${severity === "critical" ? "danger" : severity === "warning" ? "warning" : "info"}`;
    severityBadge.textContent = severity.toUpperCase();
    severityCell.appendChild(severityBadge);
    row.appendChild(severityCell);

    // Message cell
    const messageCell = document.createElement("td");
    messageCell.textContent = alert.message || "Alert";
    row.appendChild(messageCell);

    // Time cell
    const timeCell = document.createElement("td");
    timeCell.textContent = formatAlertTimestamp(alert.timestamp) || "--";
    row.appendChild(timeCell);

    // Status cell (dismissed/active)
    const statusCell = document.createElement("td");
    const statusBadge = document.createElement("span");
    statusBadge.className = `status-pill ${isDismissed ? "status-pill-muted" : "status-pill-success"}`;
    statusBadge.textContent = isDismissed ? "Dismissed" : "Active";
    statusCell.appendChild(statusBadge);
    row.appendChild(statusCell);

    if (isDismissed) {
      row.style.opacity = "0.6";
    }
    elements.alertsTableBody.appendChild(row);
  });

  renderAlertsPagination(total, pageSize, safePage);
}

function renderAlertsPagination(total, pageSize, page) {
  if (!elements.alertsPagination) return;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const info = document.createElement("span");
  info.className = "alerts-pagination-info";
  info.textContent = `${start}-${end} of ${total}`;
  elements.alertsPagination.textContent = "";
  elements.alertsPagination.appendChild(info);
  if (pageCount > 1) {
    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "btn btn-secondary btn-sm";
    prevBtn.textContent = "Previous";
    prevBtn.disabled = page <= 1;
    prevBtn.addEventListener("click", () => {
      alertsCurrentPage = Math.max(1, page - 1);
      renderAlerts(currentAlerts, elements.alertsSearch?.value || "", alertsPageSize, alertsCurrentPage);
    });
    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "btn btn-secondary btn-sm";
    nextBtn.textContent = "Next";
    nextBtn.disabled = page >= pageCount;
    nextBtn.addEventListener("click", () => {
      alertsCurrentPage = Math.min(pageCount, page + 1);
      renderAlerts(currentAlerts, elements.alertsSearch?.value || "", alertsPageSize, alertsCurrentPage);
    });
    elements.alertsPagination.insertBefore(prevBtn, info);
    elements.alertsPagination.appendChild(nextBtn);
  }
}

function renderLogContent(lines) {
  if (!elements.logContent) {
    return;
  }
  if (!lines?.length) {
    elements.logContent.textContent = "No log entries returned.";
    elements.logContent.scrollTop = 0;
    return;
  }
  const escapeHtml = (text) =>
    String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const getSeverityClass = (line) => {
    // Basic heuristic: detect common level tokens in either plain-text or JSON-ish lines.
    const upper = String(line).toUpperCase();
    if (/\b(ERROR|CRITICAL|FATAL)\b/.test(upper)) return "log-line-error";
    if (/\b(WARNING|WARN)\b/.test(upper)) return "log-line-warning";
    return "";
  };

  const html = lines
    .map((line) => {
      const safe = escapeHtml(line);
      const cls = getSeverityClass(line);
      if (!cls) return `<span class="log-line">${safe}</span>`;
      return `<span class="log-line ${cls}">${safe}</span>`;
    })
    .join("<br/>");

  elements.logContent.innerHTML = html;
  // Always show the most recent part of the log on page load / filter change.
  requestAnimationFrame(() => {
    if (!elements.logContent) return;
    elements.logContent.scrollTop = elements.logContent.scrollHeight;
  });
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

let currentAlerts = [];
let alertsPageSize = 20;
let alertsCurrentPage = 1;

async function loadMonitor() {
  try {
    const payload = await apiGet("/api/v1/system/status");
    const data = extractData(payload) || {};
    const monitor = data.monitor || {};
    const alerts = data.alerts || monitor.alerts || [];
    currentAlerts = alerts;
    renderMetrics(monitor.metrics || data.resources, data.uptime_seconds);
    const searchTerm = elements.alertsSearch?.value || "";
    renderAlerts(alerts, searchTerm, alertsPageSize, alertsCurrentPage);
    setAlerts(alerts);
  } catch (error) {
    showToast("Unable to load monitoring data.", "error");
  }
}

function setupActions() {
  const exportButton = document.getElementById("export-logs");
  if (exportButton) {
    exportButton.addEventListener("click", () => {
      const selectedFile = elements.logSelect?.value;
      if (selectedFile && selectedFile !== "all" && selectedFile !== "") {
        // Export individual file
        window.location.assign(`/api/v1/logs/export?files=${encodeURIComponent(selectedFile)}`);
      } else {
        // Export all logs
        window.location.assign("/api/v1/logs/export");
      }
    });
  }
  const loadButton = document.getElementById("load-log");
  if (loadButton) {
    loadButton.addEventListener("click", loadLogContent);
  }
  if (elements.logSelect) {
    elements.logSelect.addEventListener("change", loadLogContent);
  }
  // Auto-load when filters change
  if (elements.logTail) {
    elements.logTail.addEventListener("change", loadLogContent);
  }
  if (elements.logLevel) {
    elements.logLevel.addEventListener("change", loadLogContent);
  }
  if (elements.logService) {
    elements.logService.addEventListener("input", () => {
      // Debounce search input
      clearTimeout(elements.logService._debounceTimer);
      elements.logService._debounceTimer = setTimeout(loadLogContent, 500);
    });
  }
  if (elements.logSearch) {
    elements.logSearch.addEventListener("input", () => {
      // Debounce search input
      clearTimeout(elements.logSearch._debounceTimer);
      elements.logSearch._debounceTimer = setTimeout(loadLogContent, 500);
    });
  }
  if (elements.alertsSearch) {
    elements.alertsSearch.addEventListener("input", () => {
      alertsCurrentPage = 1;
      const searchTerm = elements.alertsSearch.value || "";
      renderAlerts(currentAlerts, searchTerm, alertsPageSize, alertsCurrentPage);
    });
  }
  if (elements.alertsPerPage) {
    elements.alertsPerPage.addEventListener("change", () => {
      alertsPageSize = parseInt(elements.alertsPerPage.value, 10) || 20;
      alertsCurrentPage = 1;
      const searchTerm = elements.alertsSearch?.value || "";
      renderAlerts(currentAlerts, searchTerm, alertsPageSize, alertsCurrentPage);
    });
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

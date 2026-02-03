const statusEls = {
  state: document.getElementById("syslog-status-state"),
  bind: document.getElementById("syslog-status-bind"),
  udp: document.getElementById("syslog-status-udp"),
  tcp: document.getElementById("syslog-status-tcp"),
  received: document.getElementById("syslog-status-received"),
  stored: document.getElementById("syslog-status-stored"),
  last: document.getElementById("syslog-status-last"),
};

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

async function refresh() {
  try {
    const status = await fetchJson("/api/v1/syslog/status");
    if (statusEls.state) {
      statusEls.state.textContent = status.running
        ? "Running"
        : status.enabled
        ? "Stopped"
        : "Disabled";
    }
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

document.addEventListener("DOMContentLoaded", () => {
  refresh();
  setInterval(refresh, 5000);

  const refreshBtn = document.getElementById("refresh-syslog");
  if (refreshBtn) refreshBtn.addEventListener("click", () => refresh());

  const clearBtn = document.getElementById("clear-syslog");
  if (clearBtn) clearBtn.addEventListener("click", clearBuffers);
});

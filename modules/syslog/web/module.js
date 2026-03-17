import { registerStatusHandler } from "/js/websocket.js";

const elements = {
  running: document.getElementById("syslog-module-running"),
  stored: document.getElementById("syslog-module-stored"),
};

function updateSyslogStatus(data) {
  if (!data) {
    return;
  }
  if (elements.running) {
    elements.running.textContent =
      data.running === true ? "Running" : "Stopped";
  }
  if (elements.stored) {
    elements.stored.textContent =
      typeof data.stored_count === "number"
        ? String(data.stored_count)
        : "--";
  }
}

registerStatusHandler("syslog", "status", updateSyslogStatus);

import { registerStatusHandler } from "/js/websocket.js";

const elements = {
  running: document.getElementById("snmp-traps-module-running"),
  stored: document.getElementById("snmp-traps-module-stored"),
};

function updateSnmpStatus(data) {
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

registerStatusHandler("snmp_traps", "status", updateSnmpStatus);

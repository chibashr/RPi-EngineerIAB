import { registerStatusHandler } from "/js/websocket.js";

const elements = {
  active: document.getElementById("remote-console-module-active"),
  ids: document.getElementById("remote-console-module-ids"),
};

function updateRemoteConsoleStatus(data) {
  if (!data) {
    return;
  }
  if (elements.active) {
    elements.active.textContent =
      typeof data.active_sessions === "number"
        ? String(data.active_sessions)
        : "--";
  }
  if (elements.ids) {
    const ids = Array.isArray(data.session_ids) ? data.session_ids : [];
    elements.ids.textContent = ids.length ? ids.join(", ") : "None";
  }
}

registerStatusHandler(
  "remote_console",
  "session_activity",
  updateRemoteConsoleStatus
);

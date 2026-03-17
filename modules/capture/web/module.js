import { registerStatusHandler } from "/js/websocket.js";

const elements = {
  active: document.getElementById("capture-module-active"),
  ids: document.getElementById("capture-module-ids"),
};

function updateCaptureStatus(data) {
  if (!data) {
    return;
  }
  if (elements.active) {
    elements.active.textContent =
      typeof data.active_captures === "number"
        ? String(data.active_captures)
        : "--";
  }
  if (elements.ids) {
    const ids = Array.isArray(data.capture_ids) ? data.capture_ids : [];
    elements.ids.textContent = ids.length ? ids.join(", ") : "None";
  }
}

registerStatusHandler("capture", "capture_activity", updateCaptureStatus);

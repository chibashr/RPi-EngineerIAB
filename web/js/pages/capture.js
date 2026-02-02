import { apiGet, apiPost, extractData } from "../api.js";
import { createStatusItem } from "../components.js";
import { createWebSocketClient } from "../websocket.js";

const elements = {
  interfaceSelect: document.getElementById("capture-interface"),
  nameInput: document.getElementById("capture-name"),
  filterInput: document.getElementById("capture-filter"),
  activeList: document.getElementById("active-capture-list"),
  completedList: document.getElementById("completed-capture-list"),
  liveView: document.getElementById("live-view"),
  banner: document.getElementById("capture-connection-banner"),
};

let activeCaptures = [];
let wsClient = null;
const MAX_CAPTURE_LINES = 500;
let captureBuffer = [];

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

function renderInterfaces(interfaces) {
  if (!elements.interfaceSelect) {
    return;
  }
  elements.interfaceSelect.textContent = "";
  if (!interfaces.length) {
    const option = document.createElement("option");
    option.textContent = "No interfaces available";
    option.value = "";
    elements.interfaceSelect.appendChild(option);
    return;
  }

  interfaces.forEach((iface) => {
    const normalized =
      typeof iface === "string" ? { id: iface, name: iface } : iface;
    const option = document.createElement("option");
    option.value = normalized.id || normalized.name || "";
    option.textContent =
      normalized.friendly_name || normalized.name || normalized.id || "iface";
    elements.interfaceSelect.appendChild(option);
  });
}

function renderCaptures(listEl, captures, emptyText) {
  if (!listEl) {
    return;
  }
  if (listEl === elements.activeList) {
    activeCaptures = captures;
  }
  listEl.textContent = "";
  if (!captures.length) {
    const item = document.createElement("li");
    item.textContent = emptyText;
    listEl.appendChild(item);
    return;
  }

  captures.forEach((capture) => {
    const label = capture.name || capture.capture_id || "Capture";
    const value = capture.status || capture.state || "active";
    listEl.appendChild(createStatusItem(label, value));
  });
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) {
    return;
  }
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function updateLiveView(text) {
  if (!elements.liveView) {
    return;
  }
  const lines = String(text).split("\n");
  captureBuffer = captureBuffer.concat(lines);
  if (captureBuffer.length > MAX_CAPTURE_LINES) {
    captureBuffer = captureBuffer.slice(-MAX_CAPTURE_LINES);
  }
  elements.liveView.textContent = captureBuffer.join("\n");
  elements.liveView.scrollTop = elements.liveView.scrollHeight;
}

function connectLiveView() {
  if (!activeCaptures.length) {
    showToast("No active capture available for live view.", "error");
    return;
  }
  const captureId = activeCaptures[0].capture_id;
  if (!captureId) {
    showToast("Capture ID unavailable.", "error");
    return;
  }
  if (wsClient) {
    wsClient.close();
  }
  captureBuffer = [];
  if (elements.liveView) {
    elements.liveView.textContent = "Connecting...";
  }
  wsClient = createWebSocketClient(`/ws/capture/${captureId}`);
  wsClient.onStatus((status) => {
    if (status === "connected") {
      updateBanner("Live capture connected.", false);
    } else if (status === "disconnected") {
      updateBanner("Live capture disconnected. Reconnecting...");
    } else if (status === "connecting") {
      updateBanner("Connecting to live capture...");
    } else if (status === "error") {
      updateBanner("Live capture connection error.");
    }
  });
  wsClient.on("packet", (message) => {
    updateLiveView(message.summary || "");
  });
  wsClient.connect();
}

function setupActions() {
  const newButton = document.getElementById("new-capture");
  if (newButton) {
    newButton.addEventListener("click", () => {
      const interfaceValue = window.prompt(
        "Interface to capture (e.g., eth0):",
        elements.interfaceSelect?.value || ""
      );
      if (!interfaceValue) {
        return;
      }
      const nameValue = window.prompt("Capture name:", "Field run") || "";
      const filterValue = window.prompt("BPF filter (optional):", "") || "";
      startCapture(interfaceValue, nameValue, filterValue);
    });
  }

  const startButton = document.getElementById("start-capture");
  if (startButton) {
    startButton.addEventListener("click", () => {
      const interfaceValue = elements.interfaceSelect?.value || "";
      const nameValue = elements.nameInput?.value?.trim() || "";
      const filterValue = elements.filterInput?.value?.trim() || "";
      startCapture(interfaceValue, nameValue, filterValue);
    });
  }

  const liveView = document.getElementById("live-view");
  if (liveView) {
    liveView.addEventListener("click", connectLiveView);
  }
}

async function startCapture(interfaceValue, nameValue, filterValue) {
  if (!interfaceValue) {
    showToast("Select an interface before starting a capture.", "error");
    return;
  }
  if (!nameValue) {
    showToast("Provide a capture name.", "error");
    return;
  }
  if (filterValue && filterValue.length > 120) {
    showToast("BPF filter is too long.", "error");
    return;
  }
  try {
    await apiPost("/api/v1/capture/start", {
      interface: interfaceValue,
      name: nameValue,
      filter: filterValue || undefined,
    });
    showToast("Capture started.", "success");
    loadCaptureData();
  } catch (error) {
    showToast("Unable to start capture.", "error");
  }
}

async function loadCaptureData() {
  try {
    const payload = await apiGet("/api/v1/capture/interfaces");
    const data = extractData(payload) || {};
    renderInterfaces(data.interfaces || []);
  } catch (error) {
    showToast("Unable to load capture interfaces.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/capture/active");
    const data = extractData(payload) || {};
    renderCaptures(elements.activeList, data.captures || [], "No active captures.");
  } catch (error) {
    showToast("Unable to load active captures.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/capture/completed");
    const data = extractData(payload) || {};
    renderCaptures(
      elements.completedList,
      data.captures || [],
      "No completed captures."
    );
  } catch (error) {
    showToast("Unable to load completed captures.", "error");
  }
}

function init() {
  const refresh = document.getElementById("refresh-capture");
  if (refresh) {
    refresh.addEventListener("click", loadCaptureData);
  }
  setupActions();
  loadCaptureData();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  if (wsClient) {
    wsClient.close();
  }
});

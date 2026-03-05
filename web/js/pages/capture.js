import { apiGet, apiPost, extractData } from "../api.js";
import { createStatusItem } from "../components.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm } from "../modal.js";

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
let selectedActiveCaptureId = null;
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

function createActiveCaptureItem(capture, isSelected) {
  const item = document.createElement("li");
  item.className = "status-item capture-active-item" + (isSelected ? " is-selected" : "");
  item.dataset.captureId = capture.capture_id;
  const label = capture.name || capture.capture_id || "Capture";
  const labelEl = document.createElement("span");
  labelEl.className = "status-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("span");
  valueEl.className = "status-value";
  valueEl.textContent = "active";
  const actions = document.createElement("span");
  actions.className = "capture-active-actions";
  const stopBtn = document.createElement("button");
  stopBtn.type = "button";
  stopBtn.className = "btn btn-secondary btn-sm";
  stopBtn.textContent = "Stop";
  stopBtn.setAttribute("aria-label", `Stop ${label}`);
  stopBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    stopCapture(capture.capture_id);
  });
  actions.appendChild(stopBtn);
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  item.appendChild(actions);
  item.addEventListener("click", (e) => {
    if (e.target.closest(".capture-active-actions")) return;
    selectAndViewActiveCapture(capture.capture_id);
  });
  return item;
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

  if (listEl === elements.activeList) {
    captures.forEach((capture) => {
      const isSelected = capture.capture_id === selectedActiveCaptureId;
      listEl.appendChild(createActiveCaptureItem(capture, isSelected));
    });
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

function selectAndViewActiveCapture(captureId) {
  const capture = activeCaptures.find((c) => c.capture_id === captureId);
  if (!capture) {
    showToast("Capture not found.", "error");
    return;
  }
  selectedActiveCaptureId = captureId;
  renderCaptures(elements.activeList, activeCaptures, "No active captures.");
  connectLiveViewTo(captureId);
}

function connectLiveView() {
  const captureId = selectedActiveCaptureId || activeCaptures[0]?.capture_id;
  if (!captureId) {
    showToast("No active capture available. Select one or start a capture.", "error");
    return;
  }
  if (!activeCaptures.some((c) => c.capture_id === captureId)) {
    showToast("Selected capture is no longer active.", "error");
    selectedActiveCaptureId = null;
    return;
  }
  selectedActiveCaptureId = captureId;
  renderCaptures(elements.activeList, activeCaptures, "No active captures.");
  connectLiveViewTo(captureId);
}

function connectLiveViewTo(captureId) {
  if (!captureId) {
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

async function stopCapture(captureId) {
  try {
    await apiPost(`/api/v1/capture/active/${captureId}/stop`, {});
    showToast("Capture stopped.", "success");
    if (selectedActiveCaptureId === captureId) {
      selectedActiveCaptureId = null;
      if (wsClient) {
        wsClient.close();
        wsClient = null;
      }
      if (elements.liveView) {
        elements.liveView.textContent = "Select an active capture to view live, or click here to connect to the first.";
      }
    }
    loadCaptureData();
  } catch (error) {
    showToast("Unable to stop capture.", "error");
  }
}

function setupActions() {
  const newButton = document.getElementById("new-capture");
  if (newButton) {
    newButton.addEventListener("click", async () => {
      const form = await modalForm(
        [
          {
            name: "interface",
            label: "Interface to capture (e.g., eth0)",
            default: elements.interfaceSelect?.value || "",
          },
          { name: "name", label: "Capture name", default: "Field run" },
          { name: "filter", label: "BPF filter (optional)", default: "" },
        ],
        "New capture"
      );
      if (!form) {
        return;
      }
      const { interface: interfaceValue, name: nameValue, filter: filterValue } = form;
      startCapture(interfaceValue, nameValue || "", filterValue || "");
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
    const active = data.captures || [];
    if (selectedActiveCaptureId && !active.some((c) => c.capture_id === selectedActiveCaptureId)) {
      selectedActiveCaptureId = null;
      if (wsClient) {
        wsClient.close();
        wsClient = null;
      }
      if (elements.liveView) {
        elements.liveView.textContent = "Select an active capture to view live, or click here to connect to the first.";
      }
    }
    renderCaptures(elements.activeList, active, "No active captures.");
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

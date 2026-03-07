import { apiDelete, apiGet, apiPost, extractData } from "../api.js";
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
  valueEl.textContent = capture.filter ? `active · ${capture.filter}` : "active";
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

function formatBytes(n) {
  if (n == null || n === undefined) return "";
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`;
}

function createCompletedCaptureItem(capture) {
  const item = document.createElement("li");
  item.className = "status-item capture-completed-item";
  const label = capture.name || capture.capture_id || "Capture";
  const metaParts = [capture.interface, capture.filter, capture.stopped_at];
  if (capture.packet_count != null) metaParts.push(`${capture.packet_count} packets`);
  if (capture.byte_count != null) metaParts.push(formatBytes(capture.byte_count));
  const meta = metaParts.filter(Boolean).join(" · ") || "completed";
  const labelEl = document.createElement("span");
  labelEl.className = "status-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("span");
  valueEl.className = "status-value";
  valueEl.textContent = meta;
  const actions = document.createElement("span");
  actions.className = "capture-completed-actions";
  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.className = "btn btn-secondary btn-sm";
  viewBtn.textContent = "View";
  viewBtn.setAttribute("aria-label", `View ${label}`);
  viewBtn.addEventListener("click", () => showCompletedCaptureView(capture));
  const exportBtn = document.createElement("button");
  exportBtn.type = "button";
  exportBtn.className = "btn btn-secondary btn-sm";
  exportBtn.textContent = "Export";
  exportBtn.setAttribute("aria-label", `Export ${label}`);
  exportBtn.addEventListener("click", () => exportCapture(capture));
  const newSimilarBtn = document.createElement("button");
  newSimilarBtn.type = "button";
  newSimilarBtn.className = "btn btn-primary btn-sm";
  newSimilarBtn.textContent = "New similar";
  newSimilarBtn.setAttribute("aria-label", `Start new capture like ${label}`);
  newSimilarBtn.addEventListener("click", () => newSimilarCapture(capture));
  actions.appendChild(viewBtn);
  actions.appendChild(exportBtn);
  actions.appendChild(newSimilarBtn);
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  item.appendChild(actions);
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

  if (listEl === elements.completedList) {
    captures.forEach((capture) => {
      listEl.appendChild(createCompletedCaptureItem(capture));
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
    elements.liveView.classList.remove("live-view-error");
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
  wsClient.on("live_started", () => {
    setLiveViewError(null);
    if (elements.liveView) {
      elements.liveView.textContent = "Listening for packets…";
    }
  });
  wsClient.on("packet", (message) => {
    setLiveViewError(null);
    updateLiveView(message.summary || "");
  });
  wsClient.on("error", (message) => {
    const msg = message.message || "Live capture connection error.";
    setLiveViewError(msg);
    updateBanner(msg);
  });
  wsClient.connect();
}

function setLiveViewError(message) {
  if (!elements.liveView) return;
  elements.liveView.classList.toggle("live-view-error", !!message);
  if (message) {
    elements.liveView.textContent = message;
  }
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
        elements.liveView.classList.remove("live-view-error");
        elements.liveView.textContent = "Start a capture, then select it above or click here to view live packets.";
      }
    }
    try {
      await loadCaptureData();
    } catch (_) {
      showToast("Capture stopped; list could not be refreshed.", "error");
    }
  } catch (error) {
    showToast("Unable to stop capture.", "error");
  }
}

function getModalContainer() {
  let el = document.getElementById("rpi-modal-container");
  if (!el) {
    el = document.createElement("div");
    el.id = "rpi-modal-container";
    el.className = "modal-container";
    el.setAttribute("aria-hidden", "true");
    document.body.appendChild(el);
  }
  return el;
}

async function showCompletedCaptureView(capture) {
  let stats = {
    packet_count: capture.packet_count ?? 0,
    byte_count: capture.byte_count ?? 0,
  };
  try {
    const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/stats`);
    const data = extractData(payload) || {};
    stats = { packet_count: data.packet_count ?? stats.packet_count, byte_count: data.byte_count ?? stats.byte_count };
  } catch (_) {
    // keep defaults from capture
  }
  const container = getModalContainer();
  container.setAttribute("aria-hidden", "false");
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "capture-view-title");

  const title = capture.name || capture.capture_id || "Capture";
  const dialog = document.createElement("div");
  dialog.className = "modal-dialog modal-dialog-form capture-view-modal";
  dialog.innerHTML = `
    <h2 id="capture-view-title" class="modal-title">${title.replace(/</g, "&lt;")}</h2>
    <div class="capture-view-details">
      <p><strong>Interface</strong> ${(capture.interface || "--").replace(/</g, "&lt;")}</p>
      <p><strong>Filter</strong> ${(capture.filter || "none").replace(/</g, "&lt;")}</p>
      <p><strong>Started</strong> ${(capture.started_at || "--").replace(/</g, "&lt;")} · <strong>Stopped</strong> ${(capture.stopped_at || "--").replace(/</g, "&lt;")}</p>
      <p><strong>Packets</strong> ${stats.packet_count} · <strong>Size</strong> ${formatBytes(stats.byte_count)}</p>
    </div>
    <div class="capture-view-tabs">
      <button type="button" class="capture-view-tab is-active" data-tab="packets">Packets</button>
      <button type="button" class="capture-view-tab" data-tab="conversations">Conversations</button>
      <button type="button" class="capture-view-tab" data-tab="protocols">Protocols</button>
    </div>
    <div class="capture-view-tab-panels">
      <div class="capture-view-tab-panel is-active" data-panel="packets"><div class="capture-view-loading">Loading…</div></div>
      <div class="capture-view-tab-panel" data-panel="conversations"><div class="capture-view-loading">Loading…</div></div>
      <div class="capture-view-tab-panel" data-panel="protocols"><div class="capture-view-loading">Loading…</div></div>
    </div>
    <div class="modal-actions">
      <button type="button" class="btn btn-secondary capture-view-export">Export</button>
      <button type="button" class="btn btn-secondary capture-view-delete">Delete</button>
      <button type="button" class="btn btn-primary capture-view-new-similar">New similar</button>
      <button type="button" class="btn btn-secondary modal-close">Close</button>
    </div>
  `;
  overlay.appendChild(dialog);

  const close = () => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
  };

  const loadTab = async (tab) => {
    const panel = dialog.querySelector(`[data-panel="${tab}"]`);
    if (!panel || panel.dataset.loaded === "true") return;
    try {
      if (tab === "packets") {
        const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/packets`);
        const data = extractData(payload) || {};
        const packets = data.packets || [];
        const list = Array.isArray(packets) ? packets : [];
        panel.innerHTML = list.length
          ? `<ul class="capture-packet-list">${list.slice(0, 100).map((p) => {
              let summary = "";
              if (p && typeof p === "object" && p._source?.layers && typeof p._source.layers === "object") {
                const info = p._source.layers.frame?.["frame.info"] || p._source.layers.frame?.["frame.time"];
                summary = info ? String(info) : Object.keys(p._source.layers).filter((k) => k !== "frame").join(", ");
              } else {
                summary = (p && (p.summary || p.info)) ? String(p.summary || p.info) : JSON.stringify(p).slice(0, 80);
              }
              const time = (p && p._source?.layers?.frame?.["frame.time"]) ? String(p._source.layers.frame["frame.time"]) : "";
              return `<li class="capture-packet-item"><span class="capture-packet-time">${(time || "").replace(/</g, "&lt;")}</span> <span class="capture-packet-summary">${String(summary).slice(0, 120).replace(/</g, "&lt;")}</span></li>`;
            }).join("")}</ul>${list.length > 100 ? `<p class="capture-view-more">First 100 of ${list.length} packets shown.</p>` : ""}`
          : "<p class=\"capture-view-empty\">No packets.</p>";
      } else if (tab === "conversations") {
        const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/conversations`);
        const data = extractData(payload) || {};
        const lines = data.conversations || [];
        const list = Array.isArray(lines) ? lines : (typeof lines === "string" ? lines.split("\n") : []);
        panel.innerHTML = list.length
          ? `<pre class="capture-conversations">${list.map((l) => String(l).replace(/</g, "&lt;")).join("\n")}</pre>`
          : "<p class=\"capture-view-empty\">No conversations.</p>";
      } else if (tab === "protocols") {
        const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/protocols`);
        const data = extractData(payload) || {};
        const protocols = data.protocols || {};
        const entries = Object.entries(protocols).sort((a, b) => (b[1] || 0) - (a[1] || 0));
        panel.innerHTML = entries.length
          ? `<ul class="capture-protocol-list">${entries.map(([name, count]) => `<li><span class="capture-protocol-name">${String(name).replace(/</g, "&lt;")}</span> <span class="capture-protocol-count">${Number(count)}</span></li>`).join("")}</ul>`
          : "<p class=\"capture-view-empty\">No protocol stats.</p>";
      }
    } catch (_) {
      panel.innerHTML = "<p class=\"capture-view-empty\">Failed to load.</p>";
    }
    panel.dataset.loaded = "true";
  };

  dialog.querySelectorAll(".capture-view-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      dialog.querySelectorAll(".capture-view-tab").forEach((b) => b.classList.remove("is-active"));
      dialog.querySelectorAll(".capture-view-tab-panel").forEach((p) => p.classList.remove("is-active"));
      btn.classList.add("is-active");
      const panel = dialog.querySelector(`[data-panel="${tab}"]`);
      if (panel) panel.classList.add("is-active");
      loadTab(tab);
    });
  });
  loadTab("packets");

  dialog.querySelector(".capture-view-export").addEventListener("click", () => {
    exportCapture(capture);
    close();
  });
  dialog.querySelector(".capture-view-delete").addEventListener("click", async () => {
    try {
      await apiDelete(`/api/v1/capture/completed/${capture.capture_id}`);
      showToast("Capture deleted.", "success");
      close();
      await loadCaptureData();
    } catch (_) {
      showToast("Unable to delete capture.", "error");
    }
  });
  dialog.querySelector(".capture-view-new-similar").addEventListener("click", () => {
    close();
    newSimilarCapture(capture);
  });
  dialog.querySelector(".modal-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", function esc(e) {
    if (e.key === "Escape") {
      close();
      document.removeEventListener("keydown", esc);
    }
  });

  container.appendChild(overlay);
}

function exportCapture(capture) {
  const name = (capture.name || capture.capture_id || "capture").replace(/[^\w.-]/g, "_");
  const filename = name.endsWith(".pcap") ? name : `${name}.pcap`;
  const url = `/api/v1/capture/completed/${capture.capture_id}/download`;
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast("Export started.", "success");
}

function newSimilarCapture(capture) {
  if (elements.interfaceSelect) {
    elements.interfaceSelect.value = capture.interface || elements.interfaceSelect.value;
  }
  if (elements.nameInput) {
    const base = capture.name || "Capture";
    const match = base.match(/^(.+?)\s*\((\d+)\)\s*$/);
    const stem = match ? match[1].trim() : base;
    const n = match ? parseInt(match[2], 10) + 1 : 2;
    elements.nameInput.value = `${stem} (${n})`;
  }
  if (elements.filterInput) {
    elements.filterInput.value = capture.filter || "";
  }
  const form = document.querySelector(".capture-form");
  if (form) {
    form.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  showToast("Form filled. Click Start Capture to begin.", "info");
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
    const payload = await apiPost("/api/v1/capture/start", {
      interface: interfaceValue,
      name: nameValue,
      filter: filterValue || undefined,
    });
    const newCapture = extractData(payload);
    if (newCapture && newCapture.capture_id) {
      activeCaptures = [...activeCaptures, newCapture];
      selectedActiveCaptureId = newCapture.capture_id;
      renderCaptures(elements.activeList, activeCaptures, "No active captures.");
      connectLiveViewTo(newCapture.capture_id);
    }
    showToast("Capture started.", "success");
    try {
      await loadCaptureData();
    } catch (_) {
      showToast("Capture started; list could not be refreshed.", "error");
    }
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
        elements.liveView.classList.remove("live-view-error");
        elements.liveView.textContent = "Start a capture, then select it above or click here to view live packets.";
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

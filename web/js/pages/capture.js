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
  banner: document.getElementById("capture-connection-banner"),
};

let activeCaptures = [];
const MAX_CAPTURE_LINES = 500;

function showToast(message, variant = "info") {
  const toastRegion = document.getElementById("toast-region");
  if (!toastRegion) return;
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function renderInterfaces(interfaces) {
  if (!elements.interfaceSelect) return;
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

function createActiveCaptureItem(capture) {
  const item = document.createElement("li");
  item.className = "status-item capture-active-item";
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
  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.className = "btn btn-secondary btn-sm";
  viewBtn.textContent = "View";
  viewBtn.setAttribute("aria-label", `View live ${label}`);
  viewBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    openCaptureViewModal(capture, { isLive: true });
  });
  const stopBtn = document.createElement("button");
  stopBtn.type = "button";
  stopBtn.className = "btn btn-secondary btn-sm";
  stopBtn.textContent = "Stop";
  stopBtn.setAttribute("aria-label", `Stop ${label}`);
  stopBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    stopCapture(capture.capture_id);
  });
  actions.appendChild(viewBtn);
  actions.appendChild(stopBtn);
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  item.appendChild(actions);
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
  viewBtn.addEventListener("click", () => openCaptureViewModal(capture, { isLive: false }));
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
  if (!listEl) return;
  if (listEl === elements.activeList) activeCaptures = captures;
  listEl.textContent = "";
  if (!captures.length) {
    const item = document.createElement("li");
    item.textContent = emptyText;
    listEl.appendChild(item);
    return;
  }
  if (listEl === elements.activeList) {
    captures.forEach((c) => listEl.appendChild(createActiveCaptureItem(c)));
    return;
  }
  if (listEl === elements.completedList) {
    captures.forEach((c) => listEl.appendChild(createCompletedCaptureItem(c)));
    return;
  }
  captures.forEach((capture) => {
    const label = capture.name || capture.capture_id || "Capture";
    const value = capture.status || capture.state || "active";
    listEl.appendChild(createStatusItem(label, value));
  });
}

function updateBanner(message, isVisible = true) {
  if (!elements.banner) return;
  elements.banner.textContent = message;
  elements.banner.classList.toggle("is-visible", isVisible);
}

function parseTsharkLine(line) {
  const s = String(line).trim();
  if (!s) return null;
  const m = s.match(/^\s*(\d+)\s+([\d.]+)\s+(\S+)\s+(?:→|->)\s+(\S+)\s+(\S+)\s+(\d+)\s*(.*)$/);
  if (m) {
    return { no: m[1], time: m[2], source: m[3], dest: m[4], protocol: m[5], length: m[6], info: m[7] || "" };
  }
  return { no: "", time: "", source: "", dest: "", protocol: "", length: "", info: s };
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function packetToTableRow(p) {
  const layers = p?._source?.layers || {};
  const frame = layers.frame || {};
  const ip = layers.ip || {};
  const eth = layers.eth || {};
  const val = (obj, key) => {
    const v = obj[key];
    return Array.isArray(v) ? (v[0] ?? "") : (v ?? "");
  };
  const no = val(frame, "frame.number") || (p._index ?? "");
  const time = val(frame, "frame.time_relative") || val(frame, "frame.time") || "";
  const src = val(ip, "ip.src") || val(eth, "eth.src") || "";
  const dst = val(ip, "ip.dst") || val(eth, "eth.dst") || "";
  const protocols = val(frame, "frame.protocols") || "";
  const protocol = protocols.split(":").pop() || "";
  const len = val(frame, "frame.len") || "";
  let info = val(frame, "frame.info") || "";
  if (!info && (layers.tcp || layers.udp)) {
    const tcp = layers.tcp || layers.udp || {};
    const sp = val(tcp, "tcp.srcport") || val(tcp, "udp.srcport");
    const dp = val(tcp, "tcp.dstport") || val(tcp, "udp.dstport");
    if (sp || dp) info = [sp, "→", dp].filter(Boolean).join(" ");
  }
  if (!info && layers.arp) info = "ARP";
  if (!info && (p.summary || p.info)) info = String(p.summary || p.info);
  return `<tr><td>${escapeHtml(no)}</td><td>${escapeHtml(time)}</td><td>${escapeHtml(src)}</td><td>${escapeHtml(dst)}</td><td>${escapeHtml(protocol)}</td><td>${escapeHtml(len)}</td><td class="capture-info">${escapeHtml(info)}</td></tr>`;
}

function matchesPacketFilter(parsedOrRow, filterText) {
  if (!filterText || !filterText.trim()) return true;
  const q = filterText.trim().toLowerCase();
  let s;
  if (typeof parsedOrRow === "object" && parsedOrRow !== null && "info" in parsedOrRow) {
    s = [parsedOrRow.no, parsedOrRow.time, parsedOrRow.source, parsedOrRow.dest, parsedOrRow.protocol, parsedOrRow.length, parsedOrRow.info]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  } else {
    s = String(parsedOrRow).toLowerCase();
  }
  return s.includes(q);
}

function packetSearchable(p) {
  const layers = p?._source?.layers || {};
  const frame = layers.frame || {};
  const ip = layers.ip || {};
  const eth = layers.eth || {};
  const val = (obj, key) => {
    const v = obj?.[key];
    return Array.isArray(v) ? (v[0] ?? "") : (v ?? "");
  };
  const parts = [
    val(frame, "frame.number"),
    val(frame, "frame.time_relative") || val(frame, "frame.time"),
    val(ip, "ip.src") || val(eth, "eth.src"),
    val(ip, "ip.dst") || val(eth, "eth.dst"),
    (val(frame, "frame.protocols") || "").split(":").pop(),
    val(frame, "frame.len"),
    val(frame, "frame.info") || p?.summary || p?.info,
  ];
  return parts.filter(Boolean).join(" ").toLowerCase();
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

function openCaptureViewModal(capture, { isLive }) {
  const container = getModalContainer();
  container.setAttribute("aria-hidden", "false");

  let stats = { packet_count: capture.packet_count ?? 0, byte_count: capture.byte_count ?? 0 };
  let wsClient = null;
  let captureBuffer = [];
  let loadedPackets = [];
  let wrapEnabled = false;

  const fetchStats = async () => {
    try {
      const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/stats`);
      const data = extractData(payload) || {};
      stats = { packet_count: data.packet_count ?? stats.packet_count, byte_count: data.byte_count ?? stats.byte_count };
    } catch (_) {}
  };

  if (!isLive) fetchStats();

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "capture-view-title");

  const title = (capture.name || capture.capture_id || "Capture") + (isLive ? " (Live)" : "");
  const dialog = document.createElement("div");
  dialog.className = "modal-dialog modal-dialog-form capture-view-modal";

  const packetsPanelHtml = `
    <div class="capture-view-toolbar" data-toolbar="packets">
      <label class="field capture-view-filter-field">
        <span class="field-label sr-only">Filter packets</span>
        <input class="input capture-view-filter-input" type="text" placeholder="Filter by protocol, IP, or info (e.g. DNS, 192.168)" />
      </label>
      <label class="capture-view-wrap-toggle">
        <input type="checkbox" class="capture-view-wrap-checkbox" ${wrapEnabled ? "checked" : ""} />
        <span>Wrap text</span>
      </label>
    </div>
    <div class="capture-packets-scroll">
      <div class="capture-packets-table-wrap">
        <table class="capture-table capture-view-packets-table">
          <thead><tr><th>No.</th><th>Time</th><th>Source</th><th>Destination</th><th>Protocol</th><th>Length</th><th>Info</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  `;

  if (isLive) {
    dialog.innerHTML = `
      <h2 id="capture-view-title" class="modal-title">${title.replace(/</g, "&lt;")}</h2>
      <div class="capture-view-details">
        <p><strong>Interface</strong> ${(capture.interface || "--").replace(/</g, "&lt;")} · <strong>Filter</strong> ${(capture.filter || "none").replace(/</g, "&lt;")}</p>
      </div>
      <div class="capture-view-packets-panel">${packetsPanelHtml}</div>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary modal-close">Close</button>
      </div>
    `;
  } else {
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
        <div class="capture-view-tab-panel is-active" data-panel="packets">${packetsPanelHtml}</div>
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
  }

  overlay.appendChild(dialog);

  const packetsTbody = dialog.querySelector(".capture-view-packets-table tbody");
  const filterInput = dialog.querySelector(".capture-view-filter-input");
  const wrapCheckbox = dialog.querySelector(".capture-view-wrap-checkbox");
  const packetsTable = dialog.querySelector(".capture-view-packets-table");

  const renderPacketsFromBuffer = () => {
    if (!packetsTbody) return;
    const filterText = filterInput?.value ?? "";
    packetsTbody.innerHTML = "";
    captureBuffer.forEach((line) => {
      const p = parseTsharkLine(line);
      if (!p || !matchesPacketFilter(p, filterText)) return;
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${escapeHtml(p.no)}</td><td>${escapeHtml(p.time)}</td><td>${escapeHtml(p.source)}</td><td>${escapeHtml(p.dest)}</td><td>${escapeHtml(p.protocol)}</td><td>${escapeHtml(p.length)}</td><td class="capture-info">${escapeHtml(p.info)}</td>`;
      packetsTbody.appendChild(tr);
    });
    const scrollEl = dialog.querySelector(".capture-packets-scroll");
    if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
  };

  const applyWrap = () => {
    wrapEnabled = wrapCheckbox?.checked ?? false;
    if (packetsTable) {
      packetsTable.classList.toggle("capture-view-wrap", wrapEnabled);
    }
  };

  if (filterInput) {
    filterInput.addEventListener("input", renderPacketsFromBuffer);
  }
  if (wrapCheckbox) {
    wrapCheckbox.addEventListener("change", applyWrap);
  }

  const close = () => {
    if (wsClient) {
      wsClient.close();
      wsClient = null;
    }
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
  };

  if (isLive) {
    wsClient = createWebSocketClient(`/ws/capture/${capture.capture_id}`);
    wsClient.onStatus((status) => {
      if (status === "connected") updateBanner("Live capture connected.", false);
      else if (status === "disconnected") updateBanner("Live capture disconnected. Reconnecting…");
      else if (status === "connecting") updateBanner("Connecting to live capture…");
      else if (status === "error") updateBanner("Live capture connection error.");
    });
    wsClient.on("live_started", () => {
      captureBuffer = [];
      renderPacketsFromBuffer();
    });
    wsClient.on("packet", (message) => {
      const lines = String(message.summary || "").split("\n").filter((l) => l.trim());
      captureBuffer = captureBuffer.concat(lines);
      if (captureBuffer.length > MAX_CAPTURE_LINES) {
        captureBuffer = captureBuffer.slice(-MAX_CAPTURE_LINES);
      }
      renderPacketsFromBuffer();
    });
    wsClient.on("error", (message) => {
      updateBanner(message.message || "Live capture connection error.");
    });
    wsClient.connect();
  } else {
    const loadTab = async (tab) => {
      const panel = dialog.querySelector(`[data-panel="${tab}"]`);
      if (!panel || panel.dataset.loaded === "true") return;
      try {
        if (tab === "packets") {
          const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/packets`);
          const data = extractData(payload) || {};
          const packets = data.packets || [];
          const list = Array.isArray(packets) ? packets : [];
          loadedPackets = list;
          const filterText = filterInput?.value ?? "";
          const filtered = list.filter((p) => matchesPacketFilter(packetSearchable(p), filterText));
          if (!filtered.length && list.length) {
            packetsTbody.innerHTML = "<tr><td colspan=\"7\" class=\"capture-view-empty\">No packets match the filter.</td></tr>";
          } else if (!list.length) {
            packetsTbody.innerHTML = "<tr><td colspan=\"7\" class=\"capture-view-empty\">No packets.</td></tr>";
          } else {
            packetsTbody.innerHTML = filtered.slice(0, 500).map((p) => packetToTableRow(p)).join("");
          }
          let moreEl = panel.querySelector(".capture-view-more");
          if (moreEl) moreEl.remove();
          if (list.length > 500) {
            const more = document.createElement("p");
            more.className = "capture-view-more";
            more.textContent = `First 500 of ${list.length} packets shown.`;
            panel.querySelector(".capture-packets-scroll")?.appendChild(more);
          }
        } else if (tab === "conversations") {
          const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/conversations`);
          const data = extractData(payload) || {};
          const lines = data.conversations || [];
          const list = Array.isArray(lines) ? lines : (typeof lines === "string" ? lines.split("\n") : []);
          const convPanel = dialog.querySelector(`[data-panel="conversations"]`);
          convPanel.innerHTML = list.length
            ? `<pre class="capture-conversations">${list.map((l) => String(l).replace(/</g, "&lt;")).join("\n")}</pre>`
            : "<p class=\"capture-view-empty\">No conversations.</p>";
        } else if (tab === "protocols") {
          const payload = await apiGet(`/api/v1/capture/${capture.capture_id}/protocols`);
          const data = extractData(payload) || {};
          const protocols = data.protocols || {};
          const entries = Object.entries(protocols).sort((a, b) => (b[1] || 0) - (a[1] || 0));
          const protPanel = dialog.querySelector(`[data-panel="protocols"]`);
          protPanel.innerHTML = entries.length
            ? `<ul class="capture-protocol-list">${entries.map(([name, count]) => `<li><span class="capture-protocol-name">${String(name).replace(/</g, "&lt;")}</span> <span class="capture-protocol-count">${Number(count)}</span></li>`).join("")}</ul>`
            : "<p class=\"capture-view-empty\">No protocol stats.</p>";
        }
      } catch (_) {
        const p = dialog.querySelector(`[data-panel="${tab}"]`);
        if (p) p.innerHTML = "<p class=\"capture-view-empty\">Failed to load.</p>";
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

    const packetsPanel = dialog.querySelector("[data-panel=\"packets\"]");
    if (packetsPanel) {
      const pktsFilter = packetsPanel.querySelector(".capture-view-filter-input");
      const pktsTbody = packetsPanel.querySelector("tbody");
      if (pktsFilter && pktsTbody) {
        pktsFilter.addEventListener("input", () => {
          if (packetsPanel.dataset.loaded !== "true") return;
          const filterText = pktsFilter.value ?? "";
          const filtered = loadedPackets.filter((p) => matchesPacketFilter(packetSearchable(p), filterText));
          if (!filtered.length && loadedPackets.length) {
            pktsTbody.innerHTML = "<tr><td colspan=\"7\" class=\"capture-view-empty\">No packets match the filter.</td></tr>";
          } else if (!loadedPackets.length) {
            pktsTbody.innerHTML = "<tr><td colspan=\"7\" class=\"capture-view-empty\">No packets.</td></tr>";
          } else {
            pktsTbody.innerHTML = filtered.slice(0, 500).map((p) => packetToTableRow(p)).join("");
          }
        });
      }
      const pktsWrap = packetsPanel.querySelector(".capture-view-wrap-checkbox");
      const pktsTable = packetsPanel.querySelector(".capture-view-packets-table");
      if (pktsWrap && pktsTable) {
        pktsWrap.addEventListener("change", () => {
          pktsTable.classList.toggle("capture-view-wrap", pktsWrap.checked);
        });
      }
    }

    dialog.querySelector(".capture-view-export")?.addEventListener("click", () => {
      exportCapture(capture);
      close();
    });
    dialog.querySelector(".capture-view-delete")?.addEventListener("click", async () => {
      try {
        await apiDelete(`/api/v1/capture/completed/${capture.capture_id}`);
        showToast("Capture deleted.", "success");
        close();
        await loadCaptureData();
      } catch (_) {
        showToast("Unable to delete capture.", "error");
      }
    });
    dialog.querySelector(".capture-view-new-similar")?.addEventListener("click", () => {
      close();
      newSimilarCapture(capture);
    });
  }

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
  if (elements.interfaceSelect) elements.interfaceSelect.value = capture.interface || elements.interfaceSelect.value;
  if (elements.nameInput) {
    const base = capture.name || "Capture";
    const match = base.match(/^(.+?)\s*\((\d+)\)\s*$/);
    const stem = match ? match[1].trim() : base;
    const n = match ? parseInt(match[2], 10) + 1 : 2;
    elements.nameInput.value = `${stem} (${n})`;
  }
  if (elements.filterInput) elements.filterInput.value = capture.filter || "";
  document.querySelector(".capture-form")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  showToast("Form filled. Click Start Capture to begin.", "info");
}

async function stopCapture(captureId) {
  try {
    await apiPost(`/api/v1/capture/active/${captureId}/stop`, {});
    showToast("Capture stopped.", "success");
    try {
      await loadCaptureData();
    } catch (_) {
      showToast("Capture stopped; list could not be refreshed.", "error");
    }
  } catch (_) {
    showToast("Unable to stop capture.", "error");
  }
}

function setupActions() {
  const newButton = document.getElementById("new-capture");
  if (newButton) {
    newButton.addEventListener("click", async () => {
      const form = await modalForm(
        [
          { name: "interface", label: "Interface to capture (e.g., eth0)", default: elements.interfaceSelect?.value || "" },
          { name: "name", label: "Capture name", default: "Field run" },
          { name: "filter", label: "BPF filter (optional)", default: "" },
        ],
        "New capture"
      );
      if (!form) return;
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
    if (newCapture?.capture_id) {
      showToast("Capture started.", "success");
      try {
        await loadCaptureData();
      } catch (_) {
        showToast("Capture started; list could not be refreshed.", "error");
      }
      openCaptureViewModal(newCapture, { isLive: true });
    } else {
      showToast("Capture started.", "success");
    }
  } catch (_) {
    showToast("Unable to start capture.", "error");
  }
}

async function loadCaptureData() {
  try {
    const payload = await apiGet("/api/v1/capture/interfaces");
    const data = extractData(payload) || {};
    renderInterfaces(data.interfaces || []);
  } catch (_) {
    showToast("Unable to load capture interfaces.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/capture/active");
    const data = extractData(payload) || {};
    renderCaptures(elements.activeList, data.captures || [], "No active captures.");
  } catch (_) {
    showToast("Unable to load active captures.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/capture/completed");
    const data = extractData(payload) || {};
    renderCaptures(elements.completedList, data.captures || [], "No completed captures.");
  } catch (_) {
    showToast("Unable to load completed captures.", "error");
  }
}

function init() {
  const refresh = document.getElementById("refresh-capture");
  if (refresh) refresh.addEventListener("click", loadCaptureData);
  setupActions();
  loadCaptureData();
}

document.addEventListener("DOMContentLoaded", init);

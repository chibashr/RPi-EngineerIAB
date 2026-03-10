import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { createWebSocketClient } from "../websocket.js";
import { modalForm, modalPrompt, modalConfirm } from "../modal.js";

const SERIAL_API_TIMEOUT_MS = 60000;

const HIGHLIGHT_STORAGE_KEY = "rpi-serial-highlight";
const HIGHLIGHT_ENABLED_KEY = "rpi-serial-highlight-enabled";
const WRAP_STORAGE_KEY = "rpi-serial-wrap-enabled";

const ANSI_SWATCH_MAP = {
  "38;5;75": "#5fafff",
  "38;5;203": "#ff5f5f",
  "38;5;117": "#87d7ff",
  "38;5;150": "#afd787",
  "38;5;244": "#808080",
  "32": "#00af00",
  "33": "#afaf00",
  "31": "#af0000",
  "1;33": "#ffff00",
  "1;31": "#ff0000",
};

function genId() {
  return `h-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function getDefaultHighlightConfig() {
  const rules = [
    {
      id: genId(),
      pattern: "[^\\s]+(>|#|\\(config[^)]*\\)#)",
      flags: "gm",
      ansiCode: "38;5;75",
      label: "Prompt",
      enabled: true,
    },
    {
      id: genId(),
      pattern: "% (Invalid|Error|Incomplete|Ambiguous)[^\\n]*",
      flags: "g",
      ansiCode: "38;5;203",
      label: "Error",
      enabled: true,
    },
    {
      id: genId(),
      pattern: "\\b(show|configure|interface|enable|disable|exit|end|no|copy|ping|traceroute|write|reload)\\b",
      flags: "g",
      ansiCode: "38;5;117",
      label: "Command",
      enabled: true,
    },
    {
      id: genId(),
      pattern: "\\b(ip |ipv6 |access-list|router |vlan |line |hostname |logging )",
      flags: "g",
      ansiCode: "38;5;150",
      label: "Config keyword",
      enabled: true,
    },
    {
      id: genId(),
      pattern: "(up|down|administratively down)",
      flags: "g",
      ansiCode: "38;5;244",
      label: "Status",
      enabled: true,
    },
  ];
  return {
    rules,
    groups: [
      {
        id: genId(),
        label: "Cisco IOS",
        enabled: true,
        rules: rules.map((r) => r.id),
      },
    ],
  };
}

let highlightConfig = { rules: [], groups: [] };
let highlightingEnabled = true;

function loadHighlightConfig() {
  try {
    const raw = localStorage.getItem(HIGHLIGHT_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && Array.isArray(parsed.rules) && Array.isArray(parsed.groups)) {
        highlightConfig = parsed;
        return;
      }
    }
  } catch (_) {
    /* ignore */
  }
  highlightConfig = getDefaultHighlightConfig();
}

function saveHighlightConfig() {
  try {
    localStorage.setItem(HIGHLIGHT_STORAGE_KEY, JSON.stringify(highlightConfig));
  } catch (_) {
    /* ignore */
  }
}

function loadHighlightingEnabled() {
  try {
    const v = localStorage.getItem(HIGHLIGHT_ENABLED_KEY);
    highlightingEnabled = v !== "false";
  } catch (_) {
    highlightingEnabled = true;
  }
}

function saveHighlightingEnabled() {
  try {
    localStorage.setItem(HIGHLIGHT_ENABLED_KEY, highlightingEnabled ? "true" : "false");
  } catch (_) {
    /* ignore */
  }
}

function loadWrapEnabled() {
  try {
    const v = localStorage.getItem(WRAP_STORAGE_KEY);
    return v !== "false";
  } catch (_) {
    return true;
  }
}

function saveWrapEnabled(enabled) {
  try {
    localStorage.setItem(WRAP_STORAGE_KEY, enabled ? "true" : "false");
  } catch (_) {
    /* ignore */
  }
}

function compileRule(rule) {
  try {
    return new RegExp(rule.pattern, rule.flags || "g");
  } catch (e) {
    console.warn("Invalid highlight pattern:", rule.pattern, e);
    return null;
  }
}

function applyHighlighting(text) {
  if (!highlightingEnabled || !text) return text;
  const ruleIdsInGroups = new Set();
  highlightConfig.groups.forEach((g) => g.rules.forEach((rid) => ruleIdsInGroups.add(rid)));
  const ruleMap = new Map(highlightConfig.rules.map((r) => [r.id, r]));
  const enabledRules = [];
  for (const g of highlightConfig.groups) {
    if (!g.enabled) continue;
    for (const rid of g.rules) {
      const r = ruleMap.get(rid);
      if (r && r.enabled) enabledRules.push(r);
    }
  }
  for (const r of highlightConfig.rules) {
    if (!ruleIdsInGroups.has(r.id) && r.enabled) enabledRules.push(r);
  }
  if (!enabledRules.length) return text;
  let result = text;
  for (const rule of enabledRules) {
    const re = compileRule(rule);
    if (!re) continue;
    const code = rule.ansiCode || "0";
    result = result.replace(re, (match) => `\x1b[${code}m${match}\x1b[0m`);
  }
  return result;
}

function ansiSwatchHex(code) {
  return ANSI_SWATCH_MAP[code] || "#666666";
}

let expandedGroupIds = new Set();
let ungroupedExpanded = true;

function getUngroupedRules() {
  const inGroup = new Set();
  highlightConfig.groups.forEach((g) => g.rules.forEach((rid) => inGroup.add(rid)));
  return highlightConfig.rules.filter((r) => !inGroup.has(r.id));
}

async function openRuleModal(rule, groupId, onConfigChange) {
  const isNew = !rule;
  const fields = [
    { name: "label", label: "Label", default: rule?.label ?? "" },
    { name: "pattern", label: "Pattern", default: rule?.pattern ?? "" },
    { name: "flags", label: "Flags", default: rule?.flags ?? "g" },
    { name: "ansiCode", label: "ANSI SGR Code", default: rule?.ansiCode ?? "38;5;75" },
  ];
  const form = await modalForm(fields, isNew ? "Add Rule" : "Edit Rule");
  if (!form) return;
  if (compileRule({ pattern: form.pattern, flags: form.flags || "g" }) === null) {
    showToast("Invalid regex pattern.", "error");
    return openRuleModal(rule, groupId, onConfigChange);
  }
  if (isNew) {
    const newRule = {
      id: genId(),
      pattern: form.pattern,
      flags: form.flags || "g",
      ansiCode: form.ansiCode || "38;5;75",
      label: form.label || "Rule",
      enabled: true,
    };
    highlightConfig.rules.push(newRule);
    if (groupId) {
      const g = highlightConfig.groups.find((gr) => gr.id === groupId);
      if (g) g.rules.push(newRule.id);
    }
  } else {
    rule.pattern = form.pattern;
    rule.flags = form.flags || "g";
    rule.ansiCode = form.ansiCode || "38;5;75";
    rule.label = form.label || "Rule";
  }
  saveHighlightConfig();
  renderHighlightPanel(onConfigChange);
  onConfigChange?.();
}

function renderHighlightPanel(onConfigChange) {
  const container = document.getElementById("serial-highlight-groups");
  const enabledCheckbox = document.getElementById("highlight-enabled");
  if (!container) return;
  if (enabledCheckbox) {
    enabledCheckbox.checked = highlightingEnabled;
    enabledCheckbox.onchange = () => {
      highlightingEnabled = enabledCheckbox.checked;
      saveHighlightingEnabled();
      onConfigChange?.();
    };
  }
  container.textContent = "";
  const ruleMap = new Map(highlightConfig.rules.map((r) => [r.id, r]));
  for (const group of highlightConfig.groups) {
    const card = document.createElement("div");
    card.className = "highlight-group";
    card.dataset.groupId = group.id;
    const rulesInGroup = group.rules.map((rid) => ruleMap.get(rid)).filter(Boolean);
    const countText = rulesInGroup.length === 1 ? "1 rule" : `${rulesInGroup.length} rules`;
    const header = document.createElement("div");
    header.className = "highlight-group-header";
    const groupCheckbox = document.createElement("input");
    groupCheckbox.type = "checkbox";
    groupCheckbox.checked = group.enabled;
    groupCheckbox.setAttribute("aria-label", `Enable group ${group.label}`);
    groupCheckbox.onchange = () => {
      group.enabled = groupCheckbox.checked;
      saveHighlightConfig();
      onConfigChange?.();
    };
    const labelSpan = document.createElement("span");
    labelSpan.className = "group-label";
    labelSpan.textContent = group.label;
    labelSpan.title = "Double-click to edit";
    const setupLabelEdit = (g, el) => {
      el.ondblclick = () => {
        const input = document.createElement("input");
        input.type = "text";
        input.value = g.label;
        input.className = "group-label-input";
        el.replaceWith(input);
        input.focus();
        input.select();
        const finish = (save) => {
          if (save) {
            const val = input.value.trim();
            g.label = val || g.label;
            saveHighlightConfig();
            onConfigChange?.();
          }
          const span = document.createElement("span");
          span.className = "group-label";
          span.textContent = g.label;
          span.title = "Double-click to edit";
          setupLabelEdit(g, span);
          input.replaceWith(span);
        };
        input.onblur = () => finish(true);
        input.onkeydown = (e) => {
          if (e.key === "Enter") finish(true);
          if (e.key === "Escape") finish(false);
        };
      };
    };
    setupLabelEdit(group, labelSpan);
    const countSpan = document.createElement("span");
    countSpan.className = "group-count";
    countSpan.textContent = `(${countText})`;
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn btn-ghost btn-sm";
    editBtn.textContent = "Edit";
    editBtn.onclick = () => {
      expandedGroupIds.has(group.id) ? expandedGroupIds.delete(group.id) : expandedGroupIds.add(group.id);
      renderHighlightPanel(onConfigChange);
    };
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn btn-ghost btn-sm";
    deleteBtn.textContent = "Delete";
    deleteBtn.onclick = async () => {
      const ok = await modalConfirm(`Delete group "${group.label}"?`);
      if (!ok) return;
      highlightConfig.groups = highlightConfig.groups.filter((g) => g.id !== group.id);
      expandedGroupIds.delete(group.id);
      saveHighlightConfig();
      renderHighlightPanel(onConfigChange);
    };
    header.append(groupCheckbox, labelSpan, countSpan, editBtn, deleteBtn);
    card.appendChild(header);
    if (expandedGroupIds.has(group.id)) {
      const rulesList = document.createElement("div");
      rulesList.className = "highlight-rules-list";
      for (const rule of rulesInGroup) {
        const row = document.createElement("div");
        row.className = "highlight-rule-row";
        const ruleCheckbox = document.createElement("input");
        ruleCheckbox.type = "checkbox";
        ruleCheckbox.checked = rule.enabled;
        ruleCheckbox.onchange = () => {
          rule.enabled = ruleCheckbox.checked;
          saveHighlightConfig();
          onConfigChange?.();
        };
        const labelEl = document.createElement("span");
        labelEl.textContent = rule.label;
        const patternEl = document.createElement("span");
        patternEl.className = "highlight-rule-pattern";
        patternEl.textContent = rule.pattern;
        patternEl.title = rule.pattern;
        const swatch = document.createElement("span");
        swatch.className = "ansi-swatch";
        swatch.style.backgroundColor = ansiSwatchHex(rule.ansiCode);
        const ruleEditBtn = document.createElement("button");
        ruleEditBtn.type = "button";
        ruleEditBtn.className = "btn btn-ghost btn-sm";
        ruleEditBtn.textContent = "Edit";
        ruleEditBtn.onclick = () => openRuleModal(rule, null, onConfigChange);
        const ruleDeleteBtn = document.createElement("button");
        ruleDeleteBtn.type = "button";
        ruleDeleteBtn.className = "btn btn-ghost btn-sm";
        ruleDeleteBtn.textContent = "Delete";
        ruleDeleteBtn.onclick = async () => {
          const ok = await modalConfirm(`Delete rule "${rule.label}"?`);
          if (!ok) return;
          highlightConfig.rules = highlightConfig.rules.filter((r) => r.id !== rule.id);
          group.rules = group.rules.filter((rid) => rid !== rule.id);
          saveHighlightConfig();
          renderHighlightPanel(onConfigChange);
        };
        row.append(ruleCheckbox, labelEl, patternEl, swatch, ruleEditBtn, ruleDeleteBtn);
        rulesList.appendChild(row);
      }
      const addRuleBtn = document.createElement("button");
      addRuleBtn.type = "button";
      addRuleBtn.className = "btn btn-secondary btn-sm";
      addRuleBtn.textContent = "Add Rule";
      addRuleBtn.onclick = () => openRuleModal(null, group.id, onConfigChange);
      rulesList.appendChild(addRuleBtn);
      card.appendChild(rulesList);
    }
    container.appendChild(card);
  }
  const ungrouped = getUngroupedRules();
  if (ungrouped.length > 0) {
    const section = document.createElement("details");
    section.className = "highlight-ungrouped";
    section.open = ungroupedExpanded;
    section.addEventListener("toggle", () => {
      ungroupedExpanded = section.open;
    });
    const summary = document.createElement("summary");
    summary.textContent = "Ungrouped Rules";
    section.appendChild(summary);
    const rulesList = document.createElement("div");
    rulesList.className = "highlight-rules-list";
    for (const rule of ungrouped) {
      const row = document.createElement("div");
      row.className = "highlight-rule-row";
      const ruleCheckbox = document.createElement("input");
      ruleCheckbox.type = "checkbox";
      ruleCheckbox.checked = rule.enabled;
      ruleCheckbox.onchange = () => {
        rule.enabled = ruleCheckbox.checked;
        saveHighlightConfig();
        onConfigChange?.();
      };
      const labelEl = document.createElement("span");
      labelEl.textContent = rule.label;
      const patternEl = document.createElement("span");
      patternEl.className = "highlight-rule-pattern";
      patternEl.textContent = rule.pattern;
      patternEl.title = rule.pattern;
      const swatch = document.createElement("span");
      swatch.className = "ansi-swatch";
      swatch.style.backgroundColor = ansiSwatchHex(rule.ansiCode);
      const ruleEditBtn = document.createElement("button");
      ruleEditBtn.type = "button";
      ruleEditBtn.className = "btn btn-ghost btn-sm";
      ruleEditBtn.textContent = "Edit";
      ruleEditBtn.onclick = () => openRuleModal(rule, null, onConfigChange);
      const ruleDeleteBtn = document.createElement("button");
      ruleDeleteBtn.type = "button";
      ruleDeleteBtn.className = "btn btn-ghost btn-sm";
      ruleDeleteBtn.textContent = "Delete";
      ruleDeleteBtn.onclick = async () => {
        const ok = await modalConfirm(`Delete rule "${rule.label}"?`);
        if (!ok) return;
        highlightConfig.rules = highlightConfig.rules.filter((r) => r.id !== rule.id);
        highlightConfig.groups.forEach((g) => {
          g.rules = g.rules.filter((rid) => rid !== rule.id);
        });
        saveHighlightConfig();
        renderHighlightPanel(onConfigChange);
      };
      row.append(ruleCheckbox, labelEl, patternEl, swatch, ruleEditBtn, ruleDeleteBtn);
      rulesList.appendChild(row);
    }
    const addRuleBtn = document.createElement("button");
    addRuleBtn.type = "button";
    addRuleBtn.className = "btn btn-secondary btn-sm";
    addRuleBtn.textContent = "Add Rule";
    addRuleBtn.onclick = () => openRuleModal(null, null, onConfigChange);
    rulesList.appendChild(addRuleBtn);
    section.appendChild(rulesList);
    container.appendChild(section);
  }
}

const HIGHLIGHT_MODAL_CONTAINER_ID = "rpi-highlight-modal-container";

function getHighlightModalContainer() {
  let el = document.getElementById(HIGHLIGHT_MODAL_CONTAINER_ID);
  if (!el) {
    el = document.createElement("div");
    el.id = HIGHLIGHT_MODAL_CONTAINER_ID;
    el.className = "modal-container";
    el.setAttribute("aria-hidden", "true");
    const mainModal = document.getElementById("rpi-modal-container");
    if (mainModal) {
      mainModal.parentNode.insertBefore(el, mainModal);
    } else {
      document.body.appendChild(el);
    }
  }
  return el;
}

function openHighlightModal() {
  loadHighlightConfig();
  loadHighlightingEnabled();

  const container = getHighlightModalContainer();
  container.setAttribute("aria-hidden", "false");

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const dialog = document.createElement("div");
  dialog.className = "modal-dialog highlight-modal-dialog";

  const testAreaHtml = `
    <div class="highlight-test-section">
      <h3 class="highlight-test-title">Test</h3>
      <div class="highlight-test-row">
        <label class="field">
          <span class="field-label">Sample input</span>
          <textarea id="highlight-test-input" class="highlight-test-input" rows="4" placeholder="Paste or type text to preview highlighting..."></textarea>
        </label>
      </div>
      <div class="highlight-test-row">
        <span class="field-label">Output</span>
        <div id="highlight-test-output" class="highlight-test-output" aria-label="Highlighted output"></div>
      </div>
    </div>
  `;

  dialog.innerHTML = `
    <h2 class="modal-title">Syntax Highlighting</h2>
    <label class="field checkbox-field highlight-global-toggle">
      <input type="checkbox" id="highlight-enabled" ${highlightingEnabled ? "checked" : ""} />
      <span class="field-label">Enable syntax highlighting</span>
    </label>
    <div id="serial-highlight-groups"></div>
    <div class="highlight-actions">
      <button type="button" class="btn btn-secondary btn-sm" id="highlight-add-group">Add Group</button>
      <button type="button" class="btn btn-ghost btn-sm" id="highlight-reset-defaults">Reset to Defaults</button>
    </div>
    ${testAreaHtml}
    <div class="modal-actions" style="margin-top:1rem">
      <button type="button" class="btn btn-primary" id="highlight-modal-close">Close</button>
    </div>
  `;

  overlay.appendChild(dialog);
  container.appendChild(overlay);

  const testOutput = dialog.querySelector("#highlight-test-output");
  const testInput = dialog.querySelector("#highlight-test-input");
  let testTerm = null;

  const updateTestOutput = () => {
    const raw = testInput?.value ?? "";
    const display = applyHighlighting(raw);
    if (testTerm) {
      testTerm.write("\x1b[2J\x1b[H" + (display || ""));
    }
  };

  if (testOutput && window.Terminal) {
    testTerm = new window.Terminal({
      scrollback: 100,
      convertEol: true,
      fontFamily: '"Courier New", Consolas, monospace',
      fontSize: 12,
      lineHeight: 1.3,
      theme: {
        background: "#0d0e11",
        foreground: "#c8cdd4",
        cursor: "#c8cdd4",
      },
    });
    testTerm.open(testOutput);
    testInput?.addEventListener("input", updateTestOutput);
  }

  const onConfigChange = () => updateTestOutput();

  renderHighlightPanel(onConfigChange);
  updateTestOutput();

  const addGroupBtn = dialog.querySelector("#highlight-add-group");
  if (addGroupBtn) {
    addGroupBtn.onclick = async () => {
      const label = await modalPrompt("Add Group", "", { label: "Group label" });
      if (label === null || !label.trim()) return;
      highlightConfig.groups.push({
        id: genId(),
        label: label.trim(),
        enabled: true,
        rules: [],
      });
      saveHighlightConfig();
      renderHighlightPanel(onConfigChange);
      onConfigChange();
    };
  }

  const resetBtn = dialog.querySelector("#highlight-reset-defaults");
  if (resetBtn) {
    resetBtn.onclick = async () => {
      const ok = await modalConfirm("Reset syntax highlighting to defaults? This will replace your current rules.");
      if (!ok) return;
      highlightConfig = getDefaultHighlightConfig();
      saveHighlightConfig();
      expandedGroupIds.clear();
      renderHighlightPanel(onConfigChange);
      onConfigChange();
    };
  }

  const close = () => {
    overlay.remove();
    testTerm?.dispose();
    testTerm = null;
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
  };

  dialog.querySelector("#highlight-modal-close").onclick = close;
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  const escapeHandler = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      close();
      document.removeEventListener("keydown", escapeHandler);
    }
  };
  document.addEventListener("keydown", escapeHandler);
}

function initHighlightPanel() {
  loadHighlightConfig();
  loadHighlightingEnabled();
  const btn = document.getElementById("serial-highlight-btn");
  if (btn) btn.onclick = openHighlightModal;
}

// Resolve from document on each access so tests (or DOM changes) always see current nodes.
const elements = {
  get deviceList() {
    return document.getElementById("serial-device-list");
  },
  get listPlaceholder() {
    return document.getElementById("serial-list-placeholder");
  },
  get detailEmpty() {
    return document.getElementById("serial-detail-empty");
  },
  get detailContent() {
    return document.getElementById("serial-detail-content");
  },
  get emptyConnectBtn() {
    return document.getElementById("serial-empty-connect");
  },
  get emptyConfigureBtn() {
    return document.getElementById("serial-empty-configure");
  },
  get consoleTabs() {
    return document.getElementById("serial-console-tabs");
  },
  get consolePanels() {
    return document.getElementById("serial-console-panels");
  },
  get logsTable() {
    return document.getElementById("serial-logs-table-body");
  },
};

let activeSessions = [];
let deviceCache = [];
let serialLogsCache = [];
let logsPageSize = 10;
let logsPageIndex = 0;
const LOGS_PAGE_SIZES = [10, 25, 50];
let lastNotConnectedToast = 0;
let connectingDeviceId = null;

const sessionMap = new Map();
let activeTabSessionId = null;
let selectedDeviceId = null;

function showToast(message, variant = "info") {
  const toastRegion = document.getElementById("toast-region");
  if (!toastRegion) return;
  const toast = document.createElement("div");
  toast.className = `toast ${variant}`;
  toast.textContent = message;
  toastRegion.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function getSessionForDevice(deviceId) {
  return activeSessions.find((s) => s.device_id === deviceId);
}

function getSessionState(sessionId) {
  return sessionMap.get(sessionId);
}

function isSessionWsConnected(sessionId) {
  const state = sessionMap.get(sessionId);
  return state && state.wsStatus === "connected";
}

function deviceDisplayName(device) {
  const path = device.path || device.id || "";
  const name = device.friendly_name || path || "";
  if (!name || name.toLowerCase() === "n/a") {
    return path || "Serial Device";
  }
  return path && path !== name ? `${name} (${path})` : name;
}

function updateConsoleEmptyState() {
  const detailEmpty = elements.detailEmpty;
  const detailContent = elements.detailContent;
  const emptyConnectBtn = elements.emptyConnectBtn;
  const emptyConfigureBtn = elements.emptyConfigureBtn;

  const sessionForSelected = selectedDeviceId ? getSessionForDevice(selectedDeviceId) : null;
  const showContent = (selectedDeviceId && sessionForSelected) || (!selectedDeviceId && sessionMap.size > 0);
  const showEmptyState = !showContent;

  if (detailEmpty) {
    detailEmpty.hidden = !showEmptyState;
  }
  if (detailContent) {
    detailContent.hidden = !showContent;
  }
  if (emptyConnectBtn) {
    emptyConnectBtn.hidden = !(showEmptyState && selectedDeviceId);
  }
  if (emptyConfigureBtn) {
    emptyConfigureBtn.hidden = !(showEmptyState && selectedDeviceId);
  }
}

function selectDevice(deviceId) {
  selectedDeviceId = deviceId;
  updateListSelection();
  updateConsoleEmptyState();
  setupEmptyStateButtons();
  const session = deviceId ? getSessionForDevice(deviceId) : null;
  if (session) {
    switchTab(session.session_id);
  }
}

function updateListSelection() {
  const list = elements.deviceList;
  if (!list) return;
  list.querySelectorAll(".serial-list-item").forEach((li) => {
    const id = li.dataset.deviceId;
    li.classList.toggle("is-active", id === selectedDeviceId);
    li.setAttribute("aria-selected", id === selectedDeviceId ? "true" : "false");
  });
}

function setupEmptyStateButtons() {
  const connectBtn = elements.emptyConnectBtn;
  if (connectBtn) {
    connectBtn.onclick = () => {
      if (selectedDeviceId) connectDevice(selectedDeviceId);
    };
  }
  const configureBtn = elements.emptyConfigureBtn;
  if (configureBtn) {
    configureBtn.onclick = () => {
      if (selectedDeviceId) configureSerial(selectedDeviceId);
    };
  }
}

function renderDevices(devices) {
  const list = elements.deviceList;
  if (!list) return;
  const validDevices = (devices || []).filter(
    (d) => d && (d.id || d.path) && String(d.id || d.path).trim()
  );
  deviceCache = validDevices;

  list.innerHTML = "";

  if (!validDevices.length) {
    const li = document.createElement("li");
    li.className = "serial-list-placeholder";
    li.textContent = "No serial devices detected.";
    list.appendChild(li);
    return;
  }

  validDevices.forEach((device) => {
    const session = getSessionForDevice(device.id);
    const state = session ? sessionMap.get(session.session_id) : null;
    const isWsConnected = session && isSessionWsConnected(session.session_id);
    const isConnecting = state?.wsStatus === "connecting";
    const deviceStatus = device.status || "unknown";
    const item = document.createElement("li");
    item.className = "serial-list-item";
    item.dataset.deviceId = device.id;
    item.setAttribute("role", "option");
    item.setAttribute("aria-selected", device.id === selectedDeviceId ? "true" : "false");
    if (device.id === selectedDeviceId) item.classList.add("is-active");

    const dot = document.createElement("span");
    dot.className = "serial-list-item-dot";
    if (isWsConnected) dot.classList.add("is-connected");
    else if (isConnecting) dot.classList.add("is-connecting");
    item.appendChild(dot);

    const info = document.createElement("div");
    info.className = "serial-list-item-info";
    const nameEl = document.createElement("div");
    nameEl.className = "serial-list-item-name";
    nameEl.textContent = deviceDisplayName(device);
    const subtitleEl = document.createElement("div");
    subtitleEl.className = "serial-list-item-subtitle";
    const path = device.path || device.id || "";
    const pathPart = path ? ` · ${path}` : "";
    subtitleEl.textContent = `${device.chipset || "Unknown"}${pathPart} · ${statusLabel(deviceStatus, !!session, isWsConnected, state?.wsStatus || "")}`;
    info.append(nameEl, subtitleEl);
    item.appendChild(info);

    item.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      selectDevice(device.id);
    });

    list.appendChild(item);
  });
  setupEmptyStateButtons();
}

function statusLabel(deviceStatus, hasSession, isWsConnected, wsStatus) {
  if (isWsConnected) return "Connected";
  if (hasSession && wsStatus === "connecting") return "Connecting";
  if (hasSession) return "Disconnected";
  if (deviceStatus === "in_use") return "In use";
  if (deviceStatus === "available") return "Available";
  return "Disconnected";
}

function updateSessionsMeta() {
  const el = document.getElementById("serial-sessions-meta");
  if (!el) return;
  const n = sessionMap.size;
  el.textContent = n > 0 ? `${n} active` : "";
}

function createTabAndConnect(sessionId, deviceId, deviceName) {
  if (sessionMap.has(sessionId)) return sessionMap.get(sessionId);

  const state = {
    sessionId,
    deviceId,
    deviceName,
    wsClient: null,
    wsStatus: "",
    connectTimeoutId: null,
    localEcho: false,
    tabPanelEl: null,
    statusEl: null,
    xtermInstance: null,
    resizeObserver: null,
  };
  sessionMap.set(sessionId, state);

  const panel = document.createElement("div");
  panel.className = "console-tab-panel console-block";
  panel.dataset.sessionId = sessionId;
  panel.setAttribute("role", "tabpanel");
  state.tabPanelEl = panel;

  const toolbarRow = document.createElement("div");
  toolbarRow.className = "console-toolbar-row";

  const toolbar = document.createElement("div");
  toolbar.className = "console-toolbar";
  const clearBtn = document.createElement("button");
  clearBtn.className = "btn btn-secondary btn-sm";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", () => {
    state.xtermInstance?.clear();
  });
  const breakBtn = document.createElement("button");
  breakBtn.className = "btn btn-secondary btn-sm";
  breakBtn.textContent = "Break";
  breakBtn.title = "Send break signal";
  breakBtn.addEventListener("click", () => sendBreakForSession(sessionId));
  const saveBtn = document.createElement("button");
  saveBtn.className = "btn btn-secondary btn-sm";
  saveBtn.textContent = "Save Log";
  saveBtn.addEventListener("click", () => saveSerialLogForSession(sessionId));
  const disconnectBtn = document.createElement("button");
  disconnectBtn.className = "btn btn-ghost btn-danger-ghost btn-sm";
  disconnectBtn.textContent = "Disconnect";
  disconnectBtn.title = "Close this session";
  disconnectBtn.addEventListener("click", () => disconnectDevice(sessionId));
  toolbar.append(clearBtn, breakBtn, saveBtn, disconnectBtn);

  const wrapLabel = document.createElement("label");
  wrapLabel.className = "field console-wrap-toggle";
  const wrapCheckbox = document.createElement("input");
  wrapCheckbox.type = "checkbox";
  wrapCheckbox.checked = loadWrapEnabled();
  wrapCheckbox.setAttribute("aria-label", "Wrap long lines");
  wrapLabel.appendChild(wrapCheckbox);
  const wrapSpan = document.createElement("span");
  wrapSpan.className = "field-label";
  wrapSpan.textContent = "Wrap";
  wrapLabel.appendChild(wrapSpan);

  const applyWrapMode = (enabled) => {
    if (!state.xtermInstance) return;
    state.xtermInstance.write(enabled ? "\x1b[?7h" : "\x1b[?7l");
  };

  wrapCheckbox.addEventListener("change", () => {
    const enabled = wrapCheckbox.checked;
    saveWrapEnabled(enabled);
    applyWrapMode(enabled);
  });

  toolbar.append(wrapLabel);
  toolbarRow.append(toolbar);

  const status = document.createElement("div");
  status.className = "console-status status-disconnected";
  status.textContent = "Connecting...";
  state.statusEl = status;

  const body = document.createElement("div");
  body.className = "console-block-body";
  const wrapper = document.createElement("div");
  wrapper.className = "console-window-wrapper";
  const container = document.createElement("div");
  container.className = "console-window xterm-container";
  container.setAttribute("aria-label", "Serial console");
  wrapper.appendChild(container);
  body.appendChild(wrapper);

  const term = new window.Terminal({
    scrollback: 5000,
    convertEol: false,
    fontFamily: '"Courier New", Consolas, monospace',
    fontSize: 14,
    lineHeight: 1.4,
    theme: {
      background: '#0d0e11',
      foreground: '#c8cdd4',
      cursor: '#c8cdd4',
      selectionBackground: 'rgba(47, 111, 237, 0.35)',
      black: '#1e2129',
      brightBlack: '#3a4049',
      white: '#c8cdd4',
      brightWhite: '#eef1f4',
    },
  });
  state.xtermInstance = term;
  term.open(container);

  const containerDiv = container;
  const resizeObserver = new ResizeObserver(() => {
    if (!term._core) return;
    const screen = containerDiv.querySelector(".xterm-screen");
    const viewport = containerDiv.querySelector(".xterm-viewport");
    if (!screen) return;

    const dims = term._core._renderService?.dimensions;
    const cellW = dims?.actualCellWidth || dims?.css?.cell?.width;
    const cellH = dims?.actualCellHeight || dims?.css?.cell?.height;
    if (!cellW || !cellH) return;

    const availW =
      containerDiv.clientWidth -
      (viewport
        ? (parseInt(getComputedStyle(viewport).paddingLeft) || 0) +
          (parseInt(getComputedStyle(viewport).paddingRight) || 0)
        : 0) -
      16;
    const availH = containerDiv.clientHeight;

    const cols = Math.max(1, Math.floor(availW / cellW));
    const rows = Math.max(1, Math.floor(availH / cellH));

    if (cols !== term.cols || rows !== term.rows) {
      term.resize(cols, rows);
    }
  });
  resizeObserver.observe(containerDiv);
  state.resizeObserver = resizeObserver;

  setTimeout(() => {
    resizeObserver.disconnect();
    resizeObserver.observe(containerDiv);
  }, 50);

  applyWrapMode(wrapCheckbox.checked);

  const main = document.createElement("div");
  main.className = "console-panel-main";
  main.append(status, body);

  panel.append(toolbarRow, main);

  elements.consolePanels?.appendChild(panel);

  setupTerminalInputForSession(state);
  switchTab(sessionId);
  updateConsoleEmptyState();
  updateSessionsMeta();

  state.wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, { autoReconnect: false });
  state.wsClient.onStatus((status) => {
    state.wsStatus = status;
    if (status === "connected" || status === "disconnected" || status === "error") {
      if (state.connectTimeoutId != null) {
        window.clearTimeout(state.connectTimeoutId);
        state.connectTimeoutId = null;
      }
    }
    if (state.statusEl) {
      state.statusEl.textContent = status;
      state.statusEl.className = "console-status status-" + status;
    }
    if (status === "connected") {
      if (activeTabSessionId === sessionId) {
        state.xtermInstance?.focus();
      }
    }
    if (status === "disconnected" || status === "error") {
      state.wsClient = null;
      state.wsStatus = "";
    }
    renderDevices(deviceCache);
  });
  state.wsClient.on("data", (message) => {
    const raw = message.data || "";
    const display = applyHighlighting(raw);
    state.xtermInstance?.write(display);
  });
  state.wsClient.on("status", (message) => {
    if (state.statusEl) {
      const tx = message.bytes_tx || 0;
      const rx = message.bytes_rx || 0;
      state.statusEl.textContent = `Tx ${tx} / Rx ${rx}`;
      state.statusEl.title = tx > 0 && rx === 0
        ? "No output yet. Verify baud rate in Configure if the device should respond."
        : "";
    }
  });
  state.wsClient.on("error", (message) => {
    showToast(message?.message || "Serial connection error.", "error");
  });
  state.wsClient.connect();
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
  }
  state.connectTimeoutId = window.setTimeout(() => {
    if (!state.wsStatus || state.wsStatus === "connecting") {
      if (state.wsClient) {
        state.wsClient.close();
        state.wsClient = null;
      }
      state.wsStatus = "";
      if (state.statusEl) {
        state.statusEl.textContent = "Disconnected (connection timed out)";
        state.statusEl.className = "console-status status-error";
      }
      showToast(
        "Serial connection timed out. Try reconnecting or check the network and device.",
        "error"
      );
      renderDevices(deviceCache);
    }
    state.connectTimeoutId = null;
  }, 15000);
  state.xtermInstance?.focus();

  return state;
}

function setupTerminalInputForSession(state) {
  state.xtermInstance.onData((data) => {
    if (sendToSerialForSession(state.sessionId, data)) {
      if (state.localEcho) {
        state.xtermInstance.write(data);
      }
    }
  });
}

function switchTab(sessionId) {
  activeTabSessionId = sessionId;
  const state = sessionMap.get(sessionId);
  if (state?.deviceId) selectedDeviceId = state.deviceId;
  sessionMap.forEach((s, sid) => {
    s.tabPanelEl?.classList.toggle("is-active", sid === sessionId);
  });
  updateListSelection();
  state?.xtermInstance?.focus();
}

function removeTabAndDisconnect(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state) return;
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
    state.connectTimeoutId = null;
  }
  if (state.wsClient) {
    state.wsClient.close();
    state.wsClient = null;
  }
  state.xtermInstance?.dispose();
  state.resizeObserver?.disconnect();
  state.tabPanelEl?.remove();
  sessionMap.delete(sessionId);
  if (activeTabSessionId === sessionId) {
    activeTabSessionId = sessionMap.size > 0 ? Array.from(sessionMap.keys())[0] : null;
    if (activeTabSessionId) switchTab(activeTabSessionId);
  }
  updateConsoleEmptyState();
  updateSessionsMeta();
  renderDevices(deviceCache);
}

function sendBreakForSession(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state?.wsClient?.send) return;
  const sent = state.wsClient.send({ type: "control", action: "break", duration: 0.25 });
  if (sent) showToast("Break signal sent.", "info");
  else showToast("Not connected.", "error");
}

function sendToSerialForSession(sessionId, data) {
  const state = sessionMap.get(sessionId);
  if (!state?.wsClient) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Not connected.", "error");
    }
    return false;
  }
  const sent = state.wsClient.send({ type: "data", data });
  if (!sent) {
    const now = Date.now();
    if (now - lastNotConnectedToast > 2000) {
      lastNotConnectedToast = now;
      showToast("Connection not ready.", "error");
    }
    return false;
  }
  return true;
}

function reconnectSession(sessionId) {
  const state = sessionMap.get(sessionId);
  if (!state?.tabPanelEl) return;
  if (state.wsClient) {
    state.wsClient.close();
    state.wsClient = null;
  }
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
    state.connectTimeoutId = null;
  }
  state.wsStatus = "";
  if (state.statusEl) {
    state.statusEl.textContent = "Connecting...";
    state.statusEl.className = "console-status status-connecting";
  }
  showToast("Reconnecting…", "info");
  state.wsClient = createWebSocketClient(`/ws/serial/${sessionId}`, { autoReconnect: false });
  state.wsClient.onStatus((status) => {
    state.wsStatus = status;
    if (status === "connected" || status === "disconnected" || status === "error") {
      if (state.connectTimeoutId != null) {
        window.clearTimeout(state.connectTimeoutId);
        state.connectTimeoutId = null;
      }
    }
    if (state.statusEl) {
      state.statusEl.textContent = status;
      state.statusEl.className = "console-status status-" + status;
    }
    if (status === "connected") {
      showToast("Reconnected.", "success");
      if (activeTabSessionId === sessionId) {
        state.xtermInstance?.focus();
      }
    }
    if (status === "disconnected" || status === "error") {
      state.wsClient = null;
      state.wsStatus = "";
    }
    renderDevices(deviceCache);
  });
  state.wsClient.on("data", (message) => {
    const raw = message.data || "";
    const display = applyHighlighting(raw);
    state.xtermInstance?.write(display);
  });
  state.wsClient.on("status", (message) => {
    if (state.statusEl) {
      const tx = message.bytes_tx || 0;
      const rx = message.bytes_rx || 0;
      state.statusEl.textContent = `Tx ${tx} / Rx ${rx}`;
      state.statusEl.title = tx > 0 && rx === 0
        ? "No output yet. Verify baud rate in Configure if the device should respond."
        : "";
    }
  });
  state.wsClient.on("error", (message) => {
    showToast(message?.message || "Serial connection error.", "error");
  });
  state.wsClient.connect();
  switchTab(sessionId);
  if (state.connectTimeoutId != null) {
    window.clearTimeout(state.connectTimeoutId);
  }
  state.connectTimeoutId = window.setTimeout(() => {
    if (!state.wsStatus || state.wsStatus === "connecting") {
      if (state.wsClient) {
        state.wsClient.close();
        state.wsClient = null;
      }
      state.wsStatus = "";
      if (state.statusEl) {
        state.statusEl.textContent = "Disconnected (connection timed out)";
        state.statusEl.className = "console-status status-error";
      }
      showToast(
        "Serial reconnection timed out. Try again or check the network and device.",
        "error"
      );
      renderDevices(deviceCache);
    }
    state.connectTimeoutId = null;
  }, 15000);
  state.xtermInstance?.focus();
}

async function connectDevice(deviceId) {
  connectingDeviceId = deviceId;
  renderDevices(deviceCache);
  showToast("Connecting…", "info");
  try {
    let payload;
    try {
      payload = await apiPost(
        "/api/v1/serial/sessions",
        { device_id: deviceId, config: {} },
        { timeoutMs: 20000 }
      );
    } catch (createErr) {
      const msg = String(createErr?.message || "");
      if (msg.includes("Device already in use") || msg.includes("Device already")) {
        // Device already has a session; reuse it instead of tearing everything down.
        await loadSessions();
        const existing = getSessionForDevice(deviceId);
        if (existing) {
          const deviceName = deviceDisplayName(
            deviceCache.find((d) => d.id === deviceId) || { id: deviceId }
          );
          if (!sessionMap.has(existing.session_id)) {
            createTabAndConnect(existing.session_id, deviceId, deviceName);
          }
          switchTab(existing.session_id);
          showToast("Device already connected; switched to existing session.", "info");
        } else {
          showToast(msg || "Device is already in use.", "error");
        }
        return;
      }
      if (msg.includes("Maximum sessions")) {
        showToast(
          "Maximum serial sessions reached. Close an existing session before starting a new one.",
          "error"
        );
        return;
      }
      throw createErr;
    }
    const data = extractData(payload) || {};
    const sessionId = data.session_id;
    const deviceName = deviceDisplayName(deviceCache.find((d) => d.id === deviceId) || { id: deviceId });
    showToast("Session created.", "success");
    activeSessions.push({ session_id: sessionId, device_id: deviceId });
    renderDevices(deviceCache);
    createTabAndConnect(sessionId, deviceId, deviceName);
    renderDevices(deviceCache);
  } catch (error) {
    activeSessions = activeSessions.filter((s) => s.device_id !== deviceId);
    const msg = String(error?.message || "");
    const hint = msg.includes("timed out")
      ? "Connection timed out. The device may be slow. Try again or check the serial connection."
      : msg || "Unable to create session.";
    showToast(hint, "error");
  } finally {
    connectingDeviceId = null;
    renderDevices(deviceCache);
  }
}

async function disconnectDevice(sessionId) {
  if (!sessionId) return;
  removeTabAndDisconnect(sessionId);
  activeSessions = activeSessions.filter(s => s.session_id !== sessionId);
  try {
    await apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(sessionId)}`);
    showToast("Session closed.", "success");
  } catch (err) {
    if (String(err?.message || "").includes("404")) {
      showToast("Session closed.", "success");
    } else {
      showToast("Unable to close session.", "error");
    }
  }
  await loadSessions();
}

async function configureSerial(deviceId) {
  const devices = deviceCache.length ? deviceCache : [];
  if (!devices.length) {
    showToast("No serial devices available.", "error");
    return;
  }
  const targetId = deviceId || devices[0]?.id || "";
  const device = devices.find((d) => d.id === targetId) || devices[0];
  const form = await modalForm(
    [
      { name: "device_id", label: "Device ID to configure", default: device?.id || "" },
      { name: "friendly_name", label: "Friendly name (optional)", default: device?.friendly_name || "" },
      { name: "baud_rate", label: "Baud rate", default: String(device?.baud_rate || 9600) },
      { name: "data_bits", label: "Data bits", default: "8" },
      { name: "parity", label: "Parity (none/even/odd)", default: "none" },
      { name: "stop_bits", label: "Stop bits", default: "1" },
    ],
    "Configure serial device"
  );
  if (!form) return;
  const { device_id: devId, friendly_name: friendlyName, baud_rate: baudRate, data_bits: dataBits, parity: parity, stop_bits: stopBits } = form;
  if (!devId.trim()) {
    showToast("Device ID is required.", "error");
    return;
  }
  const payload = {
    device_id: devId.trim(),
    baud_rate: Number(baudRate) || 9600,
    data_bits: Number(dataBits) || 8,
    parity: (parity || "none").toLowerCase(),
    stop_bits: Number(stopBits) || 1,
  };
  if (friendlyName.trim()) payload.friendly_name = friendlyName;
  try {
    await apiPut("/api/v1/serial/devices/configure", payload);
    showToast("Serial device updated.", "success");
    loadDevices();
  } catch {
    showToast("Unable to update device.", "error");
  }
}

async function saveSerialLogForSession(sessionId) {
  if (!sessionId) {
    showToast("Select a session first.", "error");
    return;
  }
  try {
    const payload = await apiGet(`/api/v1/serial/logs/${encodeURIComponent(sessionId)}/content`);
    const data = extractData(payload) || {};
    const content = data.content || "";
    downloadText(`serial-${sessionId}.log`, content);
    showToast("Log downloaded.", "success");
  } catch {
    showToast("Unable to download log.", "error");
  }
}

function formatDuration(seconds) {
  if (seconds == null || seconds < 0) return "--";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatSize(bytes) {
  if (bytes == null) return "--";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function updateLogsMeta(count) {
  const el = document.getElementById("serial-logs-meta");
  if (!el) return;
  el.textContent = count > 0 ? `${count} sessions` : "";
}

function renderLogs(logsArg) {
  if (arguments.length > 0 && Array.isArray(logsArg)) {
    serialLogsCache = logsArg;
    logsPageIndex = 0;
  }
  if (!elements.logsTable) return;
  const logs = serialLogsCache;
  const total = logs.length;
  updateLogsMeta(total);

  const toolbarEl = document.getElementById("serial-logs-toolbar");
  if (toolbarEl) {
    toolbarEl.textContent = "";
    if (total > 0) {
      const perPageLabel = document.createElement("label");
      perPageLabel.className = "field";
      perPageLabel.innerHTML = '<span class="field-label">Rows per page</span>';
      const perPageSelect = document.createElement("select");
      perPageSelect.className = "select per-page-select";
      perPageSelect.setAttribute("aria-label", "Rows per page");
      LOGS_PAGE_SIZES.forEach((n) => {
        const opt = document.createElement("option");
        opt.value = String(n);
        opt.textContent = String(n);
        if (n === logsPageSize) opt.selected = true;
        perPageSelect.appendChild(opt);
      });
      perPageSelect.addEventListener("change", () => {
        logsPageSize = Number(perPageSelect.value) || 10;
        logsPageIndex = 0;
        renderLogs();
      });
      perPageLabel.appendChild(perPageSelect);
      toolbarEl.appendChild(perPageLabel);

      const totalPages = Math.max(1, Math.ceil(total / logsPageSize));
      if (logsPageIndex >= totalPages) logsPageIndex = totalPages - 1;
      const pagination = document.createElement("div");
      pagination.className = "logs-pagination";
      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "btn btn-secondary btn-sm tab-button";
      prevBtn.textContent = "Previous";
      prevBtn.disabled = logsPageIndex === 0;
      prevBtn.addEventListener("click", () => {
        if (logsPageIndex > 0) {
          logsPageIndex--;
          renderLogs();
        }
      });
      pagination.appendChild(prevBtn);
      for (let p = 0; p < totalPages; p++) {
        const pageBtn = document.createElement("button");
        pageBtn.type = "button";
        pageBtn.className = "tab-button" + (p === logsPageIndex ? " tab-button-active" : "");
        pageBtn.textContent = String(p + 1);
        pageBtn.setAttribute("aria-label", `Page ${p + 1}`);
        const page = p;
        pageBtn.addEventListener("click", () => {
          logsPageIndex = page;
          renderLogs();
        });
        pagination.appendChild(pageBtn);
      }
      const nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "btn btn-secondary btn-sm tab-button";
      nextBtn.textContent = "Next";
      nextBtn.disabled = logsPageIndex >= totalPages - 1;
      nextBtn.addEventListener("click", () => {
        if (logsPageIndex < totalPages - 1) {
          logsPageIndex++;
          renderLogs();
        }
      });
      pagination.appendChild(nextBtn);
      toolbarEl.appendChild(pagination);
    }
  }

  elements.logsTable.textContent = "";
  if (!total) {
    const row = document.createElement("tr");
    row.appendChild(document.createElement("td"));
    row.cells[0].colSpan = 6;
    row.cells[0].textContent = "No recorded sessions.";
    elements.logsTable.appendChild(row);
    return;
  }

  const start = logsPageIndex * logsPageSize;
  const pageLogs = logs.slice(start, start + logsPageSize);
  pageLogs.forEach((log) => {
    const row = document.createElement("tr");
    [log.name || log.id, log.device || "--", formatDate(log.created || log.modified), formatDuration(log.duration_seconds), formatSize(log.size_bytes)].forEach((v) => {
      const cell = document.createElement("td");
      cell.textContent = v || "--";
      row.appendChild(cell);
    });
    const actionCell = document.createElement("td");
    const renameBtn = document.createElement("button");
    renameBtn.className = "btn btn-ghost btn-sm";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", () => renameLog(log.id));
    const exportBtn = document.createElement("button");
    exportBtn.className = "btn btn-secondary btn-sm";
    exportBtn.textContent = "Export";
    exportBtn.addEventListener("click", () => exportLog(log.id));
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost btn-sm";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => deleteLog(log.id));
    actionCell.append(renameBtn, exportBtn, deleteBtn);
    row.appendChild(actionCell);
    elements.logsTable.appendChild(row);
  });
}

async function renameLog(logId) {
  const name = await modalPrompt("New name", logId, { label: "Name" });
  if (name === null || !name.trim()) return;
  try {
    await apiPut(`/api/v1/serial/logs/${encodeURIComponent(logId)}`, { name: name.trim() });
    showToast("Log renamed.", "success");
    loadLogs();
  } catch {
    showToast("Unable to rename log.", "error");
  }
}

async function deleteLog(logId) {
  const confirmed = await modalConfirm(`Delete session log "${logId}"? This cannot be undone.`);
  if (!confirmed) return;
  try {
    await apiDelete(`/api/v1/serial/logs/${encodeURIComponent(logId)}`);
    showToast("Log deleted.", "success");
    loadLogs();
  } catch {
    showToast("Unable to delete log.", "error");
  }
}

async function exportLog(logId) {
  try {
    const payload = await apiPost("/api/v1/serial/logs/export", { log_ids: [logId] });
    const data = extractData(payload) || {};
    const archiveName = (data.archive || "").split(/[/\\]/).pop();
    if (archiveName) {
      window.location.assign(`/api/v1/serial/logs/export/${archiveName}`);
      showToast("Export started.", "success");
    }
  } catch {
    showToast("Unable to export log.", "error");
  }
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

async function loadDevices(forceRefresh = false) {
  try {
    const url = forceRefresh ? "/api/v1/serial/devices?refresh=1" : "/api/v1/serial/devices";
    const payload = await apiGet(url, { timeoutMs: SERIAL_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    renderDevices(data.devices || []);
  } catch {
    showToast("Unable to load serial devices.", "error");
  }
}

async function loadSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions", { timeoutMs: SERIAL_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    const apiSessions = data.sessions || [];
    const apiIds = new Set(apiSessions.map((s) => s.session_id));
    const kept = activeSessions.filter((s) => !apiIds.has(s.session_id));
    activeSessions = [...apiSessions, ...kept];
    sessionMap.forEach((st, sessionId) => {
      if (!activeSessions.some((s) => s.session_id === sessionId)) {
        activeSessions.push({ session_id: sessionId, device_id: st.deviceId });
      }
    });
    renderDevices(deviceCache);
    activeSessions.forEach((session) => {
      if (!sessionMap.has(session.session_id)) {
        const deviceName = deviceDisplayName(deviceCache.find((d) => d.id === session.device_id) || { id: session.device_id });
        createTabAndConnect(session.session_id, session.device_id, deviceName);
      }
    });
    const toRemove = [];
    sessionMap.forEach((st, sid) => {
      if (!activeSessions.some((s) => s.session_id === sid)) {
        toRemove.push(sid);
      }
    });
    toRemove.forEach((sid) => removeTabAndDisconnect(sid));
    renderDevices(deviceCache);
  } catch {
    showToast("Unable to load serial sessions.", "error");
  }
}

async function loadLogs() {
  try {
    const payload = await apiGet("/api/v1/serial/logs");
    const data = extractData(payload) || {};
    serialLogsCache = data.logs || [];
    logsPageIndex = 0;
    renderLogs();
  } catch {
    showToast("Unable to load serial logs.", "error");
  }
}

async function closeAllSessions() {
  try {
    const payload = await apiGet("/api/v1/serial/sessions", { timeoutMs: SERIAL_API_TIMEOUT_MS });
    const data = extractData(payload) || {};
    const sessions = data.sessions || [];
    await Promise.all(
      sessions.map((s) =>
        apiDelete(`/api/v1/serial/sessions/${encodeURIComponent(s.session_id)}`, {
          timeoutMs: SERIAL_API_TIMEOUT_MS,
        }).catch(() => {})
      )
    );
  } catch {
    /* ignore */
  }
}

async function openNewSerialSessionModal() {
  if (!deviceCache.length) {
    await loadDevices(true);
  }
  const available = deviceCache.filter((d) => {
    const status = d.status || "unknown";
    if (status === "in_use") return false;
    const session = getSessionForDevice(d.id);
    return !session || !isSessionWsConnected(session.session_id);
  });
  const options = available.map((d) => ({
    value: d.id,
    label: deviceDisplayName(d),
  }));
  if (!options.length) {
    showToast("No devices available. Refresh or disconnect an existing session.", "error");
    return;
  }
  const form = await modalForm(
    [
      {
        name: "device_id",
        label: "Device",
        type: "select",
        default: options[0].value,
        options,
      },
    ],
    "New serial session"
  );
  if (!form?.device_id) return;
  await connectDevice(form.device_id);
}

async function init() {
  const refresh = document.getElementById("refresh-serial");
  if (refresh) {
    refresh.addEventListener("click", () => {
      loadDevices(true);
      loadSessions();
      loadLogs();
    });
  }
  const newSessionBtn = document.getElementById("new-serial-session");
  if (newSessionBtn) {
    newSessionBtn.addEventListener("click", () => openNewSerialSessionModal());
  }
  initHighlightPanel();
  await loadDevices();
  await loadSessions();
  loadLogs();
}

document.addEventListener("DOMContentLoaded", init);
window.addEventListener("beforeunload", () => {
  sessionMap.forEach((state) => state.wsClient?.close());
});

// Reset module state for tests so each test starts with a clean sessionMap/activeSessions.
function resetStateForTest() {
  sessionMap.forEach((st) => {
    if (st.connectTimeoutId != null) {
      window.clearTimeout(st.connectTimeoutId);
      st.connectTimeoutId = null;
    }
    st.wsClient?.close?.();
    st.xtermInstance?.dispose?.();
  });
  sessionMap.clear();
  activeSessions.length = 0;
  connectingDeviceId = null;
  activeTabSessionId = null;
  selectedDeviceId = null;
  deviceCache.length = 0;
}

// Internal hooks exported for tests only. Has no effect when loaded via <script>.
export const __testHooks = {
  state: {
    get activeSessions() {
      return activeSessions;
    },
    get deviceCache() {
      return deviceCache;
    },
    get sessionMap() {
      return sessionMap;
    },
    get activeTabSessionId() {
      return activeTabSessionId;
    },
    get connectingDeviceId() {
      return connectingDeviceId;
    },
  },
  resetStateForTest,
  renderDevices,
  loadDevices,
  loadSessions,
  connectDevice,
  disconnectDevice,
  reconnectSession,
  createTabAndConnect,
  switchTab,
};

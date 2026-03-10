import { apiGet, apiPost, apiPut, apiDelete, extractData } from "../api.js";
import { initTabs } from "../components.js";
import { modalForm, modalConfirm } from "../modal.js";

const elements = {
  interfaceList: document.getElementById("interface-list"),
  interfaceListPlaceholder: document.getElementById("interface-list-placeholder"),
  interfaceDetailEmpty: document.getElementById("interface-detail-empty"),
  interfaceDetailContent: document.getElementById("interface-detail-content"),
  interfaceInfoStrip: document.getElementById("interface-info-strip"),
  interfaceConfigTitle: document.getElementById("interface-config-title"),
  interfaceDhcpToggle: document.getElementById("interface-dhcp-toggle"),
  interfaceShareRow: document.getElementById("interface-share-row"),
  interfaceShareHotspotToggle: document.getElementById("interface-share-hotspot-toggle"),
  interfaceFormGrid: document.getElementById("interface-form-grid"),
  interfaceToggleUpDown: document.getElementById("interface-toggle-updown"),
  interfaceToggleUpDownLabel: document.getElementById("interface-toggle-updown-label"),
  interfaceSavedMsg: document.getElementById("interface-saved-msg"),
  interfaceDiscard: document.getElementById("interface-discard"),
  interfaceApply: document.getElementById("interface-apply"),
  routeTable: document.getElementById("route-table-body"),
  currentRouteTable: document.getElementById("current-route-table-body"),
  profileList: document.getElementById("profile-list"),
  hotspot: {
    status: document.getElementById("hotspot-status"),
    ssid: document.getElementById("hotspot-ssid"),
    channel: document.getElementById("hotspot-channel"),
    clientTable: document.getElementById("hotspot-client-table-body"),
  },
};
let interfaceCache = [];
let selectedInterfaceId = null;
let interfaceDraft = null;

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

function setupActions() {
  const actions = [
    { id: "add-interface", action: addInterface },
    { id: "add-vlan", action: addVlan },
    { id: "add-route", action: addRoute },
    { id: "save-profile", action: saveProfile },
    { id: "configure-hotspot", action: configureHotspot },
  ];

  actions.forEach((action) => {
    const button = document.getElementById(action.id);
    if (!button) {
      return;
    }
    button.addEventListener("click", () => {
      if (action.action) {
        action.action();
      } else {
        showToast(action.message, "info");
      }
    });
  });

  const resetButton = document.getElementById("reset-network");
  if (resetButton) {
    resetButton.addEventListener("click", async () => {
      const form = await modalForm(
        [
          {
            name: "warning",
            label: "",
            type: "display",
            default:
              "Reset network settings to factory defaults. Hotspot will remain available unless you choose to reset it too.",
          },
          {
            name: "reset_hotspot",
            label: "Also reset hotspot configuration",
            type: "checkbox",
            default: false,
          },
        ],
        "Reset network settings?"
      );
      if (!form) {
        return;
      }
      const resetHotspot = form.reset_hotspot === "true";
      const preserveHotspot = !resetHotspot;
      apiPost("/api/v1/network/reset", { preserve_hotspot: preserveHotspot })
        .then(() => {
          showToast(
            preserveHotspot
              ? "Network reset (preserving hotspot) completed."
              : "Network reset completed.",
            "success"
          );
          return loadNetworkData().catch(() =>
            showToast("Network reset; list could not be refreshed.", "error")
          );
        })
        .catch(() => showToast("Unable to reset network.", "error"));
    });
  }
}

function isLoopbackInterface(iface) {
  const name = iface?.id || iface?.name || "";
  return name === "lo" || name === "lo0" || name.startsWith("lo");
}

function getInterfaceOptions(includeBlank = false) {
  const options = interfaceCache.map((iface) => {
    const label = iface.friendly_name
      ? `${iface.friendly_name} (${iface.name || iface.id})`
      : iface.name || iface.id;
    return { value: iface.id || iface.name, label };
  });
  if (includeBlank) {
    options.unshift({ value: "", label: "No interface" });
  }
  return options;
}

function updateFieldVisibility(overlay, showFields = [], hideFields = []) {
  showFields.forEach((name) => {
    const field = overlay.querySelector(`[data-field-name="${name}"]`);
    if (field) field.style.display = "";
  });
  hideFields.forEach((name) => {
    const field = overlay.querySelector(`[data-field-name="${name}"]`);
    if (field) field.style.display = "none";
  });
}

function ipv4ToInt(ip) {
  const parts = ip.split(".").map((part) => parseInt(part, 10));
  if (parts.length !== 4 || parts.some((part) => isNaN(part))) {
    return null;
  }
  return (
    ((parts[0] << 24) >>> 0) +
    ((parts[1] << 16) >>> 0) +
    ((parts[2] << 8) >>> 0) +
    (parts[3] >>> 0)
  );
}

function intToIpv4(num) {
  if (typeof num !== "number") return null;
  return [
    (num >>> 24) & 255,
    (num >>> 16) & 255,
    (num >>> 8) & 255,
    num & 255,
  ].join(".");
}

function subnetFrom(ip, netmask) {
  const ipInt = ipv4ToInt(ip || "");
  const maskInt = ipv4ToInt(netmask || "");
  if (ipInt == null || maskInt == null) {
    return null;
  }
  return intToIpv4(ipInt & maskInt);
}

async function toggleShareWithHotspot(checkbox) {
  const interfaceId = checkbox.dataset.interfaceId;
  if (!interfaceId) return;

  const intended = checkbox.checked;
  const wrap = checkbox.closest(".interface-share-toggle-wrap");
  const loadingEl = document.getElementById("interface-share-loading");

  // Lock UI immediately
  checkbox.disabled = true;
  checkbox.dataset.pending = "true";
  if (wrap) wrap.classList.add("is-loading");
  if (loadingEl) loadingEl.hidden = false;

  try {
    await apiPut(
      `/api/v1/network/interfaces/${encodeURIComponent(interfaceId)}/share-with-hotspot`,
      { enabled: intended }
    );

    // Re-fetch the interface to get the actual server state — do not trust the checkbox
    await loadNetworkData();
    if (selectedInterfaceId) selectInterface(selectedInterfaceId);

    // Read back the real value from the refreshed cache
    const updated = interfaceCache.find((i) => (i.id || i.name) === interfaceId);
    const actual = updated?.share_with_hotspot === true;

    if (actual !== intended) {
      // Server state disagrees with what we asked for — show a warning
      showToast(`Share state mismatch on ${interfaceId} — check Pi logs.`, "error");
    } else {
      showToast(
        intended ? `Sharing ${interfaceId} with hotspot.` : `Stopped sharing ${interfaceId}.`,
        "success"
      );
    }
  } catch (err) {
    // Revert checkbox to last known good state from cache
    const cached = interfaceCache.find((i) => (i.id || i.name) === interfaceId);
    checkbox.checked = cached?.share_with_hotspot === true;
    showToast("Unable to update connection share.", "error");
  } finally {
    checkbox.disabled = false;
    delete checkbox.dataset.pending;
    if (wrap) wrap.classList.remove("is-loading");
    if (loadingEl) loadingEl.hidden = true;
  }
}

async function addInterface() {
  if (!interfaceCache.length) {
    showToast("No interfaces available to configure.", "error");
    return;
  }
  const defaultIface = interfaceCache[0]?.id || interfaceCache[0]?.name || "";
  const defaultInterface = interfaceCache.find(
    (iface) => (iface.id || iface.name) === defaultIface
  );
  const form = await modalForm(
    [
      {
        name: "interface_id",
        label: "Interface",
        type: "select",
        default: defaultIface,
        options: getInterfaceOptions(),
      },
      {
        name: "mode",
        label: "Mode",
        type: "select",
        default: "dhcp",
        options: [
          { value: "dhcp", label: "DHCP" },
          { value: "static", label: "Static" },
        ],
      },
      { name: "dhcp_ip", label: "DHCP IP", type: "display", default: defaultInterface?.ip_address || "--" },
      { name: "dhcp_netmask", label: "DHCP netmask", type: "display", default: defaultInterface?.netmask || "--" },
      { name: "dhcp_gateway", label: "DHCP gateway", type: "display", default: defaultInterface?.gateway || "--" },
      { name: "ip_address", label: "IP address", default: defaultInterface?.ip_address || "" },
      { name: "netmask", label: "Netmask", default: defaultInterface?.netmask || "255.255.255.0" },
      { name: "gateway", label: "Gateway (optional)", default: defaultInterface?.gateway || "" },
    ],
    "Add Interface",
    {
      onOpen: (overlay) => {
        const interfaceSelect = overlay.querySelector("#modal-form-interface_id");
        const modeSelect = overlay.querySelector("#modal-form-mode");
        const ipInput = overlay.querySelector("#modal-form-ip_address");
        const netmaskInput = overlay.querySelector("#modal-form-netmask");
        const gatewayInput = overlay.querySelector("#modal-form-gateway");
        const dhcpIp = overlay.querySelector("#modal-form-dhcp_ip");
        const dhcpNetmask = overlay.querySelector("#modal-form-dhcp_netmask");
        const dhcpGateway = overlay.querySelector("#modal-form-dhcp_gateway");

        const applyMode = (mode) => {
          if (mode === "static") {
            updateFieldVisibility(
              overlay,
              ["ip_address", "netmask", "gateway"],
              ["dhcp_ip", "dhcp_netmask", "dhcp_gateway"]
            );
          } else {
            updateFieldVisibility(
              overlay,
              ["dhcp_ip", "dhcp_netmask", "dhcp_gateway"],
              ["ip_address", "netmask", "gateway"]
            );
          }
        };

        const syncDhcpInfo = (ifaceId) => {
          const iface = interfaceCache.find(
            (item) => (item.id || item.name) === ifaceId
          );
          if (dhcpIp) dhcpIp.textContent = iface?.ip_address || "--";
          if (dhcpNetmask) dhcpNetmask.textContent = iface?.netmask || "--";
          if (dhcpGateway) dhcpGateway.textContent = iface?.gateway || "--";
          if (ipInput && iface?.ip_address) ipInput.value = iface.ip_address;
          if (netmaskInput && iface?.netmask) netmaskInput.value = iface.netmask;
          if (gatewayInput && iface?.gateway) gatewayInput.value = iface.gateway;
        };

        applyMode(modeSelect?.value || "dhcp");
        syncDhcpInfo(interfaceSelect?.value || defaultIface);

        modeSelect?.addEventListener("change", () => {
          applyMode(modeSelect.value);
        });
        interfaceSelect?.addEventListener("change", () => {
          syncDhcpInfo(interfaceSelect.value);
        });
      },
    }
  );
  if (!form) {
    return;
  }
  const { interface_id: interfaceId, mode, ip_address: ipAddress, netmask, gateway } = form;
  if (!interfaceId.trim()) {
    showToast("Interface is required.", "error");
    return;
  }
  if (!["dhcp", "static"].includes(mode)) {
    showToast("Mode must be dhcp or static.", "error");
    return;
  }
  const payload = { mode };
  if (mode === "static") {
    if (!ipAddress.trim() || !netmask.trim()) {
      showToast("IP address and netmask are required for static mode.", "error");
      return;
    }
    payload.ip_address = ipAddress;
    payload.netmask = netmask;
    if (gateway.trim()) {
      payload.gateway = gateway;
    }
  }
  apiPut(`/api/v1/network/interfaces/${interfaceId}`, payload)
    .then(() => {
      showToast(`Updated ${interfaceId}.`, "success");
      loadNetworkData();
    })
    .catch(() => showToast("Unable to update interface.", "error"));
}

async function addRoute() {
  const form = await modalForm(
    [
      { name: "destination", label: "Route destination (CIDR)", default: "10.0.0.0/8" },
      { name: "gateway", label: "Gateway", default: "" },
      {
        name: "interface",
        label: "Interface (optional)",
        type: "select",
        default: "",
        options: getInterfaceOptions(true),
      },
    ],
    "Add route"
  );
  if (!form) {
    return;
  }
  const { destination, gateway: gw, interface: iface } = form;
  if (!destination.trim()) {
    showToast("Destination is required.", "error");
    return;
  }
  if (!gw.trim()) {
    showToast("Gateway is required.", "error");
    return;
  }
  const payload = { destination, gateway: gw };
  if (iface && iface.trim()) {
    payload.interface = iface;
  }
  apiPost("/api/v1/network/routes", payload)
    .then(() => {
      showToast("Route added.", "success");
      loadNetworkData();
    })
    .catch(() => showToast("Unable to add route.", "error"));
}

async function saveProfile() {
  const form = await modalForm(
    [
      { name: "name", label: "Profile name", default: "" },
      { name: "description", label: "Profile description (optional)", default: "" },
    ],
    "Save profile"
  );
  if (!form) {
    return;
  }
  const { name, description } = form;
  if (!name.trim()) {
    showToast("Profile name is required.", "error");
    return;
  }
  apiPost("/api/v1/network/profiles", { name, description: description || "" })
    .then(() => {
      showToast("Profile saved.", "success");
      loadNetworkData();
    })
    .catch((error) =>
      showToast(error?.message || "Unable to save profile.", "error")
    );
}

async function addVlan() {
  if (!interfaceCache.length) {
    showToast("No interfaces available.", "error");
    return;
  }
  const defaultParent = interfaceCache[0]?.id || interfaceCache[0]?.name || "";
  const form = await modalForm(
    [
      {
        name: "parent",
        label: "Parent interface",
        type: "select",
        default: defaultParent,
        options: getInterfaceOptions(),
      },
      { name: "vlan_id", label: "VLAN ID (1-4094)", default: "" },
      { name: "name", label: "VLAN name (optional)", default: "" },
      {
        name: "mode",
        label: "Mode",
        type: "select",
        default: "dhcp",
        options: [
          { value: "dhcp", label: "DHCP" },
          { value: "static", label: "Static" },
        ],
      },
      { name: "ip_address", label: "IP address", default: "" },
      { name: "netmask", label: "Netmask", default: "255.255.255.0" },
      { name: "gateway", label: "Gateway (optional)", default: "" },
    ],
    "Add VLAN",
    {
      onOpen: (overlay) => {
        const modeSelect = overlay.querySelector("#modal-form-mode");
        const applyMode = (mode) => {
          if (mode === "static") {
            updateFieldVisibility(
              overlay,
              ["ip_address", "netmask", "gateway"],
              []
            );
          } else {
            updateFieldVisibility(
              overlay,
              [],
              ["ip_address", "netmask", "gateway"]
            );
          }
        };
        applyMode(modeSelect?.value || "dhcp");
        modeSelect?.addEventListener("change", () => applyMode(modeSelect.value));
      },
    }
  );
  if (!form) {
    return;
  }
  const { parent, vlan_id: vlanIdStr, name, mode, ip_address: ipAddress, netmask, gateway } = form;
  if (!parent.trim()) {
    showToast("Parent interface is required.", "error");
    return;
  }
  const vlanId = parseInt(vlanIdStr, 10);
  if (isNaN(vlanId) || vlanId < 1 || vlanId > 4094) {
    showToast("VLAN ID must be between 1 and 4094.", "error");
    return;
  }
  const payload = { parent, vlan_id: vlanId };
  if (name.trim()) {
    payload.name = name;
  }
  apiPost("/api/v1/network/vlans", payload)
    .then((response) => {
      const data = extractData(response) || {};
      const vlanName = data.name || name || `${parent}.${vlanId}`;
      const configPayload = { mode };
      if (mode === "static") {
        if (!ipAddress.trim() || !netmask.trim()) {
          showToast("IP address and netmask are required for static VLAN.", "error");
          return;
        }
        configPayload.ip_address = ipAddress;
        configPayload.netmask = netmask;
        if (gateway.trim()) {
          configPayload.gateway = gateway;
        }
      }
      return apiPut(`/api/v1/network/interfaces/${vlanName}`, configPayload)
        .then(() => {
          showToast("VLAN created.", "success");
          loadNetworkData();
        })
        .catch(() => showToast("Unable to configure VLAN interface.", "error"));
    })
    .catch(() => showToast("Unable to create VLAN.", "error"));
}

async function configureHotspot() {
  const form = await modalForm(
    [
      {
        name: "warning",
        label: "",
        type: "display",
        default:
          "Do not change WiFi hotspot settings unless you completely know what you are doing.",
      },
      { name: "ssid", label: "SSID", default: "" },
      { name: "password", label: "Password (optional)", default: "" },
      { name: "channel", label: "Channel (1-11, default 6)", default: "6" },
    ],
    "Configure hotspot"
  );
  if (!form) {
    return;
  }
  const { ssid, password, channel: channelStr } = form;
  if (!ssid.trim()) {
    showToast("SSID is required.", "error");
    return;
  }
  const channel = channelStr ? parseInt(channelStr, 10) : 6;
  const payload = { ssid, channel: isNaN(channel) ? 6 : channel };
  if (password.trim()) {
    payload.password = password;
  }
  apiPost("/api/v1/network/hotspot", payload)
    .then(() => {
      showToast("Hotspot configured.", "success");
      loadNetworkData();
    })
    .catch(() => showToast("Unable to configure hotspot.", "error"));
}

function renderInterfaces(interfaces) {
  interfaceCache = interfaces.filter((iface) => !isLoopbackInterface(iface));

  const listEl = elements.interfaceList;
  const placeholderEl = elements.interfaceListPlaceholder;
  if (!listEl) return;

  listEl.textContent = "";

  if (!interfaceCache.length) {
    const li = document.createElement("li");
    li.className = "interface-list-placeholder";
    li.textContent = "No interfaces detected.";
    listEl.appendChild(li);
    selectInterface(null);
    return;
  }

  interfaceCache.forEach((iface) => {
    const id = iface.id || iface.name;
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "interface-list-item" + (selectedInterfaceId === id ? " is-active" : "");
    btn.setAttribute("role", "option");
    btn.setAttribute("aria-selected", selectedInterfaceId === id ? "true" : "false");
    btn.dataset.interfaceId = id;

    const dot = document.createElement("span");
    dot.className = "interface-list-item-dot" + (String(iface.status || "").toLowerCase() === "up" ? " is-up" : "");

    const info = document.createElement("div");
    info.className = "interface-list-item-info";
    const nameEl = document.createElement("div");
    nameEl.className = "interface-list-item-name";
    nameEl.textContent = iface.friendly_name || iface.name || id;
    const subEl = document.createElement("div");
    subEl.className = "interface-list-item-subtitle";
    subEl.textContent = [iface.ip_address || "--", iface.driver || "--"].join(" · ");
    info.appendChild(nameEl);
    info.appendChild(subEl);

    const badge = document.createElement("span");
    const role = String(iface.role || "").toLowerCase();
    badge.className = "interface-list-item-badge " + (role === "lan" || role === "wan" ? role : "");
    badge.textContent = role || "--";

    btn.appendChild(dot);
    btn.appendChild(info);
    btn.appendChild(badge);
    btn.addEventListener("click", () => selectInterface(id));
    li.appendChild(btn);
    listEl.appendChild(li);
  });

  if (selectedInterfaceId && !interfaceCache.some((i) => (i.id || i.name) === selectedInterfaceId)) {
    selectInterface(null);
  } else if (selectedInterfaceId) {
    syncDraftFromInterface(interfaceCache.find((i) => (i.id || i.name) === selectedInterfaceId));
    populateDetailPanel();
  }
}

function selectInterface(id) {
  selectedInterfaceId = id;
  if (id) {
    syncDraftFromInterface(interfaceCache.find((i) => (i.id || i.name) === id));
    if (elements.interfaceDetailEmpty) elements.interfaceDetailEmpty.hidden = true;
    if (elements.interfaceDetailContent) {
      elements.interfaceDetailContent.hidden = false;
      populateDetailPanel();
    }
    document.querySelectorAll(".interface-list-item").forEach((el) => {
      el.classList.toggle("is-active", el.dataset.interfaceId === id);
      el.setAttribute("aria-selected", el.dataset.interfaceId === id ? "true" : "false");
    });
  } else {
    if (elements.interfaceDetailEmpty) elements.interfaceDetailEmpty.hidden = false;
    if (elements.interfaceDetailContent) elements.interfaceDetailContent.hidden = true;
    interfaceDraft = null;
  }
}

function syncDraftFromInterface(iface) {
  if (!iface) {
    interfaceDraft = null;
    return;
  }
  const isDhcp = !iface.ip_address || String(iface.mode || "dhcp").toLowerCase() === "dhcp";
  interfaceDraft = {
    id: iface.id || iface.name,
    mode: isDhcp ? "dhcp" : "static",
    ip_address: iface.ip_address || "",
    netmask: iface.netmask || "255.255.255.0",
    gateway: iface.gateway || "",
    role: String(iface.role || "lan").toLowerCase(),
    mtu: String(iface.mtu ?? ""),
    status: String(iface.status || "down").toLowerCase(),
  };
}

function populateDetailPanel() {
  const iface = interfaceCache.find((i) => (i.id || i.name) === selectedInterfaceId);
  if (!iface || !interfaceDraft) return;

  const id = iface.id || iface.name;
  const status = String(iface.status || "down").toLowerCase();

  if (elements.interfaceInfoStrip) {
    elements.interfaceInfoStrip.innerHTML = "";
    const cells = [
      { label: "Status", value: status, isPill: true },
      { label: "MAC", value: iface.mac_address },
      { label: "MTU", value: iface.mtu },
      { label: "Driver", value: iface.driver },
      { label: "Speed", value: iface.speed_mbps ? `${iface.speed_mbps} Mbps` : null },
    ];
    cells.forEach(({ label, value, isPill }) => {
      const cell = document.createElement("div");
      cell.className = "interface-info-cell";
      cell.innerHTML = `<div class="interface-info-label">${escapeHtml(label)}</div><div class="interface-info-value">`;
      const valEl = cell.querySelector(".interface-info-value");
      if (isPill && (label === "Status")) {
        const pill = document.createElement("span");
        pill.className = "interface-info-status-pill " + (status === "up" ? "is-up" : "is-down");
        pill.textContent = status || "--";
        valEl.appendChild(pill);
      } else {
        valEl.textContent = value || "--";
      }
      elements.interfaceInfoStrip.appendChild(cell);
    });
  }

  if (elements.interfaceConfigTitle) {
    elements.interfaceConfigTitle.textContent = `Configuration — ${iface.friendly_name || id}`;
  }

  if (elements.interfaceDhcpToggle) {
    elements.interfaceDhcpToggle.checked = interfaceDraft.mode === "dhcp";
    elements.interfaceDhcpToggle.onchange = () => {
      interfaceDraft.mode = elements.interfaceDhcpToggle.checked ? "dhcp" : "static";
      setStaticFieldsDisabled(elements.interfaceDhcpToggle.checked);
    };
    setStaticFieldsDisabled(interfaceDraft.mode === "dhcp");
  }

  const isWlan = String(id || "").toLowerCase().startsWith("wlan");
  if (elements.interfaceShareRow && elements.interfaceShareHotspotToggle) {
    if (isWlan) {
      elements.interfaceShareRow.hidden = true;
    } else {
      elements.interfaceShareRow.hidden = false;
      elements.interfaceShareHotspotToggle.dataset.interfaceId = id;

      // Always set checked from server data, never from prior DOM state
      const isSharing = iface.share_with_hotspot === true;
      elements.interfaceShareHotspotToggle.checked = isSharing;

      // Disable the toggle if another interface is currently pending
      const anyPending = document.querySelector("[data-pending='true']");
      elements.interfaceShareHotspotToggle.disabled = !!anyPending;

      // Replace onchange each render to avoid stale closures
      elements.interfaceShareHotspotToggle.onchange = () =>
        toggleShareWithHotspot(elements.interfaceShareHotspotToggle);
    }
  }

  if (elements.interfaceFormGrid) {
    elements.interfaceFormGrid.innerHTML = "";
    const fields = [
      { key: "ip_address", label: "IP Address", type: "text", disabled: interfaceDraft.mode === "dhcp" },
      { key: "netmask", label: "Netmask", type: "text", disabled: interfaceDraft.mode === "dhcp" },
      { key: "gateway", label: "Gateway", type: "text", disabled: interfaceDraft.mode === "dhcp" },
      {
        key: "role",
        label: "Role",
        type: "select",
        options: [
          { value: "lan", label: "LAN" },
          { value: "wan", label: "WAN" },
        ],
        disabled: false,
      },
      { key: "mtu", label: "MTU", type: "text", disabled: false },
    ];
    fields.forEach(({ key, label, type, options, disabled }) => {
      const field = document.createElement("div");
      field.className = "field";
      field.dataset.fieldKey = key;
      const lab = document.createElement("label");
      lab.className = "field-label";
      lab.htmlFor = `interface-form-${key}`;
      lab.textContent = label;
      field.appendChild(lab);
      if (type === "select") {
        const sel = document.createElement("select");
        sel.id = `interface-form-${key}`;
        sel.className = "select input";
        sel.dataset.key = key;
        (options || []).forEach((opt) => {
          const o = document.createElement("option");
          o.value = opt.value;
          o.textContent = opt.label;
          o.selected = (interfaceDraft[key] || "").toLowerCase() === opt.value.toLowerCase();
          sel.appendChild(o);
        });
        sel.disabled = !!disabled;
        sel.addEventListener("change", () => {
          interfaceDraft[key] = sel.value;
        });
        field.appendChild(sel);
      } else {
        const inp = document.createElement("input");
        inp.id = `interface-form-${key}`;
        inp.type = type || "text";
        inp.className = "input";
        inp.dataset.key = key;
        inp.value = interfaceDraft[key] || "";
        inp.disabled = !!disabled;
        inp.addEventListener("input", () => {
          interfaceDraft[key] = inp.value;
        });
        field.appendChild(inp);
      }
      elements.interfaceFormGrid.appendChild(field);
    });
  }

  if (elements.interfaceToggleUpDown && elements.interfaceToggleUpDownLabel) {
    const isUp = status === "up";
    elements.interfaceToggleUpDownLabel.textContent = isUp ? "Bring Down" : "Bring Up";
    elements.interfaceToggleUpDown.className = isUp ? "btn btn-ghost btn-danger-ghost" : "btn btn-secondary";
    elements.interfaceToggleUpDown.onclick = () => {
      showToast("Interface bring up/down requires backend support.", "info");
    };
  }

  if (elements.interfaceDiscard) {
    elements.interfaceDiscard.onclick = () => {
      syncDraftFromInterface(iface);
      populateDetailPanel();
    };
  }

  if (elements.interfaceApply) {
    elements.interfaceApply.onclick = () => applyInterfaceConfig();
  }
}

function setStaticFieldsDisabled(disabled) {
  ["ip_address", "netmask", "gateway"].forEach((key) => {
    const inp = elements.interfaceFormGrid?.querySelector(`[data-key="${key}"]`);
    if (inp) inp.disabled = disabled;
  });
}

function getFormValues() {
  const values = { ...interfaceDraft };
  if (elements.interfaceFormGrid) {
    elements.interfaceFormGrid.querySelectorAll("[data-key]").forEach((el) => {
      values[el.dataset.key] = el.value;
    });
  }
  return values;
}

function applyInterfaceConfig() {
  if (!selectedInterfaceId || !interfaceDraft) return;
  const vals = getFormValues();
  const payload = { mode: vals.mode };
  if (vals.mode === "static") {
    if (!vals.ip_address?.trim() || !vals.netmask?.trim()) {
      showToast("IP address and netmask are required for static mode.", "error");
      return;
    }
    payload.ip_address = vals.ip_address.trim();
    payload.netmask = vals.netmask.trim();
    if (vals.gateway?.trim()) payload.gateway = vals.gateway.trim();
  }
  apiPut(`/api/v1/network/interfaces/${encodeURIComponent(selectedInterfaceId)}`, payload)
    .then(() => {
      showSavedMessage();
      showToast(`Updated ${selectedInterfaceId}.`, "success");
      loadNetworkData();
    })
    .catch(() => showToast("Unable to update interface.", "error"));
}

function showSavedMessage() {
  const msg = elements.interfaceSavedMsg;
  if (!msg) return;
  msg.textContent = "✓ Saved";
  msg.hidden = false;
  msg.classList.remove("fade-out");
  clearTimeout(msg._fadeTimeout);
  msg._fadeTimeout = setTimeout(() => {
    msg.classList.add("fade-out");
    msg._fadeTimeout = setTimeout(() => {
      msg.hidden = true;
    }, 300);
  }, 2500);
}

function renderRoutes(routes) {
  if (!elements.routeTable) {
    return;
  }
  elements.routeTable.textContent = "";
  if (!routes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.textContent = "No routes configured.";
    row.appendChild(cell);
    elements.routeTable.appendChild(row);
    return;
  }

  routes.forEach((route) => {
    const row = document.createElement("tr");
    [route.destination, route.gateway, route.interface].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });
    elements.routeTable.appendChild(row);
  });
}

function renderCurrentRoutes(routes) {
  if (!elements.currentRouteTable) {
    return;
  }
  elements.currentRouteTable.textContent = "";
  if (!routes.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 7;
    cell.textContent = "No current routes available.";
    row.appendChild(cell);
    elements.currentRouteTable.appendChild(row);
    return;
  }
  routes.forEach((route) => {
    const row = document.createElement("tr");
    [
      route.destination,
      route.gateway,
      route.interface,
      route.source,
      route.metric,
      route.protocol,
      route.scope,
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });
    elements.currentRouteTable.appendChild(row);
  });
}

function renderProfileInterfacesTable(interfaces) {
  if (!interfaces.length) {
    const p = document.createElement("p");
    p.className = "profile-empty";
    p.textContent = "No interfaces in this profile.";
    return p;
  }
  const table = document.createElement("table");
  table.className = "status-table profile-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>Name</th><th>Status</th><th>IP</th><th>Gateway</th><th>Role</th></tr>";
  const tbody = document.createElement("tbody");
  interfaces.forEach((iface) => {
    const row = document.createElement("tr");
    row.innerHTML = [
      iface.name || iface.id || "--",
      iface.status || "--",
      iface.ip_address || "--",
      iface.gateway || "--",
      iface.role || "--",
    ]
      .map((v) => `<td>${escapeHtml(String(v || "--"))}</td>`)
      .join("");
    tbody.appendChild(row);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  return table;
}

function renderProfileRoutesTable(routes) {
  if (!routes.length) {
    const p = document.createElement("p");
    p.className = "profile-empty";
    p.textContent = "No routes in this profile.";
    return p;
  }
  const table = document.createElement("table");
  table.className = "status-table profile-table";
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>Destination</th><th>Gateway</th><th>Interface</th></tr>";
  const tbody = document.createElement("tbody");
  routes.forEach((route) => {
    const row = document.createElement("tr");
    row.innerHTML = [
      route.destination || "--",
      route.gateway || "--",
      route.interface || "--",
    ]
      .map((v) => `<td>${escapeHtml(String(v || "--"))}</td>`)
      .join("");
    tbody.appendChild(row);
  });
  table.appendChild(thead);
  table.appendChild(tbody);
  return table;
}

function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function renderProfiles(profiles) {
  if (!elements.profileList) {
    return;
  }
  elements.profileList.textContent = "";
  if (!profiles.length) {
    const item = document.createElement("li");
    item.textContent = "No profiles saved.";
    elements.profileList.appendChild(item);
    return;
  }

  profiles.forEach((profile) => {
    const item = document.createElement("li");
    const card = document.createElement("div");
    card.className = "profile-card";
    const header = document.createElement("div");
    header.className = "profile-card-header";
    const title = document.createElement("h4");
    title.textContent = profile.name || "Profile";
    const actions = document.createElement("div");
    actions.className = "profile-card-actions";
    const loadBtn = document.createElement("button");
    loadBtn.className = "btn btn-primary btn-sm";
    loadBtn.textContent = "Load";
    loadBtn.type = "button";
    loadBtn.addEventListener("click", () => loadProfile(profile.name));
    const editBtn = document.createElement("button");
    editBtn.className = "btn btn-secondary btn-sm";
    editBtn.textContent = "Edit";
    editBtn.type = "button";
    editBtn.addEventListener("click", () => editProfile(profile));
    const renameBtn = document.createElement("button");
    renameBtn.className = "btn btn-secondary btn-sm";
    renameBtn.textContent = "Rename";
    renameBtn.type = "button";
    renameBtn.addEventListener("click", () => renameProfile(profile));
    const deleteBtn = document.createElement("button");
    deleteBtn.className = "btn btn-ghost btn-sm";
    deleteBtn.textContent = "Delete";
    deleteBtn.type = "button";
    deleteBtn.addEventListener("click", () => deleteProfile(profile.name));
    actions.append(loadBtn, editBtn, renameBtn, deleteBtn);
    header.appendChild(title);
    header.appendChild(actions);
    card.appendChild(header);

    const meta = document.createElement("div");
    meta.className = "profile-meta";
    const description = profile.description || "No description";
    const savedAt = profile.saved_at ? `Saved ${profile.saved_at}` : "Saved --";
    meta.textContent = `${description} • ${savedAt}`;
    card.appendChild(meta);

    const routes = Array.isArray(profile.routes) ? profile.routes : [];
    const interfaces = Array.isArray(profile.interfaces) ? profile.interfaces : [];

    const interfaceSection = document.createElement("details");
    interfaceSection.className = "profile-section";
    interfaceSection.open = true;
    const interfaceSummary = document.createElement("summary");
    interfaceSummary.textContent = `Interfaces (${interfaces.length})`;
    interfaceSection.appendChild(interfaceSummary);
    interfaceSection.appendChild(renderProfileInterfacesTable(interfaces));

    const routeSection = document.createElement("details");
    routeSection.className = "profile-section";
    routeSection.open = true;
    const routeSummary = document.createElement("summary");
    routeSummary.textContent = `Routes (${routes.length})`;
    routeSection.appendChild(routeSummary);
    routeSection.appendChild(renderProfileRoutesTable(routes));

    card.appendChild(interfaceSection);
    card.appendChild(routeSection);
    item.appendChild(card);
    elements.profileList.appendChild(item);
  });
}

async function loadProfile(name) {
  try {
    await apiPost(`/api/v1/network/profiles/${encodeURIComponent(name)}/load`);
    showToast(`Profile "${name}" loaded.`, "success");
    loadNetworkData();
  } catch (error) {
    showToast(error?.message || "Unable to load profile.", "error");
  }
}

async function editProfile(profile) {
  const form = await modalForm(
    [
      { name: "name", label: "Profile name", default: profile.name || "" },
      { name: "description", label: "Description", default: profile.description || "" },
    ],
    "Edit profile"
  );
  if (!form) return;
  if (!form.name.trim()) {
    showToast("Profile name is required.", "error");
    return;
  }
  try {
    await apiPut(`/api/v1/network/profiles/${encodeURIComponent(profile.name)}`, {
      name: form.name.trim(),
      description: form.description.trim(),
    });
    showToast("Profile updated.", "success");
    loadNetworkData();
  } catch (error) {
    showToast(error?.message || "Unable to update profile.", "error");
  }
}

async function renameProfile(profile) {
  const form = await modalForm(
    [{ name: "name", label: "New name", default: profile.name || "" }],
    "Rename profile"
  );
  if (!form) return;
  if (!form.name.trim()) {
    showToast("Profile name is required.", "error");
    return;
  }
  try {
    await apiPut(`/api/v1/network/profiles/${encodeURIComponent(profile.name)}`, {
      name: form.name.trim(),
    });
    showToast("Profile renamed.", "success");
    loadNetworkData();
  } catch (error) {
    showToast(error?.message || "Unable to rename profile.", "error");
  }
}

async function deleteProfile(name) {
  const confirmed = await modalConfirm(`Delete profile "${name}"? This cannot be undone.`);
  if (!confirmed) return;
  try {
    await apiDelete(`/api/v1/network/profiles/${encodeURIComponent(name)}`);
    showToast("Profile deleted.", "success");
    loadNetworkData();
  } catch (error) {
    showToast(error?.message || "Unable to delete profile.", "error");
  }
}

function renderHotspot(statusPayload) {
  if (!elements.hotspot.status) {
    return;
  }
  elements.hotspot.status.textContent = statusPayload?.hotspot_status || "--";
  elements.hotspot.ssid.textContent = statusPayload?.ssid || "--";
  elements.hotspot.channel.textContent = statusPayload?.channel || "--";
  renderHotspotClients(statusPayload?.clients || []);
}

function renderHotspotClients(clients) {
  if (!elements.hotspot.clientTable) {
    return;
  }
  elements.hotspot.clientTable.textContent = "";
  if (!clients.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No connected clients detected.";
    row.appendChild(cell);
    elements.hotspot.clientTable.appendChild(row);
    return;
  }
  clients.forEach((client) => {
    const row = document.createElement("tr");
    const name = client.hostname || client.device || "Client";
    const signal = client.signal_dbm != null ? `${client.signal_dbm} dBm` : "";
    const link = [client.rx_rate, client.tx_rate].filter(Boolean).join(" / ");
    [name, client.ip, client.mac, signal, link].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });
    elements.hotspot.clientTable.appendChild(row);
  });
}

async function loadNetworkData() {
  try {
    const payload = await apiGet("/api/v1/network/interfaces");
    const data = extractData(payload) || {};
    renderInterfaces(data.interfaces || []);
  } catch (error) {
    showToast("Unable to load interfaces.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/network/routes");
    const data = extractData(payload) || {};
    renderRoutes(data.routes || []);
  } catch (error) {
    showToast("Unable to load routes.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/network/routes/current");
    const data = extractData(payload) || {};
    renderCurrentRoutes(data.routes || []);
  } catch (error) {
    renderCurrentRoutes([]);
  }

  try {
    const payload = await apiGet("/api/v1/network/profiles");
    const data = extractData(payload) || {};
    renderProfiles(data.profiles || []);
  } catch (error) {
    showToast("Unable to load profiles.", "error");
  }

  try {
    const payload = await apiGet("/api/v1/network/status");
    const data = extractData(payload) || {};
    renderHotspot(data);
  } catch (error) {
    renderHotspot(null);
  }
}

function init() {
  initTabs(document.querySelector("[data-tabs]"));
  const refreshInterfacesButton = document.getElementById("refresh-interfaces");
  if (refreshInterfacesButton) {
    refreshInterfacesButton.addEventListener("click", async () => {
      try {
        const payload = await apiGet("/api/v1/network/interfaces");
        const data = extractData(payload) || {};
        renderInterfaces(data.interfaces || []);
        showToast("Interfaces refreshed.", "success");
      } catch (error) {
        showToast("Unable to refresh interfaces.", "error");
      }
    });
  }
  setupActions();
  loadNetworkData();
}

document.addEventListener("DOMContentLoaded", init);

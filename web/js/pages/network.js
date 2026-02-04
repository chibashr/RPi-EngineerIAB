import { apiGet, apiPost, apiPut, extractData } from "../api.js";
import { initTabs, createStatusItem } from "../components.js";
import { modalConfirm, modalForm } from "../modal.js";

const elements = {
  interfaceTable: document.getElementById("interface-table-body"),
  routeTable: document.getElementById("route-table-body"),
  profileList: document.getElementById("profile-list"),
  hotspot: {
    status: document.getElementById("hotspot-status"),
    ssid: document.getElementById("hotspot-ssid"),
    channel: document.getElementById("hotspot-channel"),
  },
};
let interfaceCache = [];

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
    { id: "configure-interface", action: configureInterface },
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
  const preserveCheckbox = document.getElementById("preserve-hotspot");
  if (resetButton) {
    resetButton.addEventListener("click", async () => {
      const confirmed = await modalConfirm(
        "Reset network settings to factory defaults?"
      );
      if (!confirmed) {
        return;
      }
      const preserveHotspot = preserveCheckbox?.checked ?? false;
      apiPost("/api/v1/network/reset", { preserve_hotspot: preserveHotspot })
        .then(() => {
          showToast(
            preserveHotspot
              ? "Network reset (preserving hotspot) completed."
              : "Network reset completed.",
            "success"
          );
          loadNetworkData();
        })
        .catch(() => showToast("Unable to reset network.", "error"));
    });
  }
}

async function configureInterface() {
  if (!interfaceCache.length) {
    showToast("No interfaces available to configure.", "error");
    return;
  }
  const defaultIface = interfaceCache[0]?.id || interfaceCache[0]?.name || "";
  const form = await modalForm(
    [
      { name: "interface_id", label: "Interface", default: defaultIface },
      { name: "mode", label: "Mode (dhcp/static)", default: "dhcp" },
      { name: "ip_address", label: "IP address (if static)", default: "" },
      { name: "netmask", label: "Netmask (if static)", default: "255.255.255.0" },
      { name: "gateway", label: "Gateway (optional)", default: "" },
    ],
    "Configure interface"
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
      { name: "interface", label: "Interface (optional)", default: "" },
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
  if (iface.trim()) {
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
    .catch(() => showToast("Unable to save profile.", "error"));
}

async function addVlan() {
  if (!interfaceCache.length) {
    showToast("No interfaces available.", "error");
    return;
  }
  const defaultParent = interfaceCache[0]?.id || interfaceCache[0]?.name || "";
  const form = await modalForm(
    [
      { name: "parent", label: "Parent interface", default: defaultParent },
      { name: "vlan_id", label: "VLAN ID (1-4094)", default: "" },
      { name: "name", label: "VLAN name (optional)", default: "" },
    ],
    "Add VLAN"
  );
  if (!form) {
    return;
  }
  const { parent, vlan_id: vlanIdStr, name } = form;
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
    .then(() => {
      showToast("VLAN created.", "success");
      loadNetworkData();
    })
    .catch(() => showToast("Unable to create VLAN.", "error"));
}

async function configureHotspot() {
  const form = await modalForm(
    [
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
  if (!elements.interfaceTable) {
    return;
  }
  interfaceCache = interfaces;
  elements.interfaceTable.textContent = "";
  if (!interfaces.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = "No interfaces detected.";
    row.appendChild(cell);
    elements.interfaceTable.appendChild(row);
    return;
  }

  interfaces.forEach((iface) => {
    const row = document.createElement("tr");
    [iface.name || iface.id, iface.status, iface.ip_address, iface.role].forEach(
      (value) => {
        const cell = document.createElement("td");
        cell.textContent = value || "--";
        row.appendChild(cell);
      }
    );
    elements.interfaceTable.appendChild(row);
  });
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
    elements.profileList.appendChild(
      createStatusItem(profile.name || "Profile", profile.description || "")
    );
  });
}

function renderHotspot(statusPayload) {
  if (!elements.hotspot.status) {
    return;
  }
  elements.hotspot.status.textContent = statusPayload?.hotspot_status || "--";
  elements.hotspot.ssid.textContent = statusPayload?.ssid || "--";
  elements.hotspot.channel.textContent = statusPayload?.channel || "--";
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
  const refreshButton = document.getElementById("refresh-network");
  if (refreshButton) {
    refreshButton.addEventListener("click", loadNetworkData);
  }
  setupActions();
  loadNetworkData();
}

document.addEventListener("DOMContentLoaded", init);

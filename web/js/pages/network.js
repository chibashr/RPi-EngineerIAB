import { apiGet, apiPost, apiPut, extractData } from "../api.js";
import { initTabs } from "../components.js";
import { modalForm } from "../modal.js";

const elements = {
  interfaceTable: document.getElementById("interface-table-body"),
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
          loadNetworkData();
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

async function configureInterface() {
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
    "Configure interface",
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
  interfaceCache = interfaces.filter((iface) => !isLoopbackInterface(iface));
  elements.interfaceTable.textContent = "";
  if (!interfaceCache.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No interfaces detected.";
    row.appendChild(cell);
    elements.interfaceTable.appendChild(row);
    return;
  }

  interfaceCache.forEach((iface) => {
    const row = document.createElement("tr");
    [iface.name || iface.id, iface.status, iface.ip_address, iface.role].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value || "--";
      row.appendChild(cell);
    });

    const actionCell = document.createElement("td");
    const detailsButton = document.createElement("button");
    detailsButton.className = "btn btn-ghost";
    detailsButton.type = "button";
    detailsButton.textContent = "Details";
    detailsButton.setAttribute("aria-expanded", "false");
    actionCell.appendChild(detailsButton);
    row.appendChild(actionCell);

    const detailsRow = document.createElement("tr");
    detailsRow.className = "details-row";
    detailsRow.hidden = true;
    const detailsCell = document.createElement("td");
    detailsCell.colSpan = 5;
    const subnet = subnetFrom(iface.ip_address, iface.netmask);
    const details = [
      { label: "IP address", value: iface.ip_address },
      { label: "Netmask", value: iface.netmask },
      { label: "Subnet", value: subnet },
      { label: "Gateway", value: iface.gateway },
      { label: "MAC", value: iface.mac_address },
      { label: "MTU", value: iface.mtu },
      { label: "Speed", value: iface.speed_mbps ? `${iface.speed_mbps} Mbps` : "" },
      { label: "Driver", value: iface.driver },
    ];
    const detailsContent = document.createElement("div");
    detailsContent.className = "details-content";
    details.forEach((item) => {
      const detailItem = document.createElement("div");
      detailItem.className = "details-item";
      const label = document.createElement("span");
      label.className = "details-label";
      label.textContent = item.label;
      const value = document.createElement("span");
      value.className = "details-value";
      value.textContent = item.value || "--";
      detailItem.appendChild(label);
      detailItem.appendChild(value);
      detailsContent.appendChild(detailItem);
    });
    detailsCell.appendChild(detailsContent);
    detailsRow.appendChild(detailsCell);

    detailsButton.addEventListener("click", () => {
      const expanded = detailsButton.getAttribute("aria-expanded") === "true";
      detailsButton.setAttribute("aria-expanded", expanded ? "false" : "true");
      detailsRow.hidden = expanded;
    });

    elements.interfaceTable.appendChild(row);
    elements.interfaceTable.appendChild(detailsRow);
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
    const title = document.createElement("h4");
    title.textContent = profile.name || "Profile";
    const meta = document.createElement("div");
    meta.className = "profile-meta";
    const description = profile.description || "No description";
    const savedAt = profile.saved_at ? `Saved ${profile.saved_at}` : "Saved --";
    meta.textContent = `${description} • ${savedAt}`;
    const routes = Array.isArray(profile.routes) ? profile.routes : [];
    const interfaces = Array.isArray(profile.interfaces) ? profile.interfaces : [];
    const interfaceDetails = document.createElement("details");
    interfaceDetails.className = "profile-json";
    interfaceDetails.open = true;
    const interfaceSummary = document.createElement("summary");
    interfaceSummary.textContent = `Interfaces (${interfaces.length})`;
    const interfacePre = document.createElement("pre");
    interfacePre.textContent = JSON.stringify(interfaces, null, 2);
    interfaceDetails.appendChild(interfaceSummary);
    interfaceDetails.appendChild(interfacePre);

    const routeDetails = document.createElement("details");
    routeDetails.className = "profile-json";
    routeDetails.open = true;
    const routeSummary = document.createElement("summary");
    routeSummary.textContent = `Routes (${routes.length})`;
    const routePre = document.createElement("pre");
    routePre.textContent = JSON.stringify(routes, null, 2);
    routeDetails.appendChild(routeSummary);
    routeDetails.appendChild(routePre);

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(interfaceDetails);
    card.appendChild(routeDetails);
    item.appendChild(card);
    elements.profileList.appendChild(item);
  });
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

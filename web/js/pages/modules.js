import { apiDelete, apiGet, apiPost, extractData } from "../api.js";
import { initTabs } from "../components.js";

const elements = {
  installed: document.getElementById("installed-modules"),
};

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

function renderInstalled(modules) {
  if (!elements.installed) {
    return;
  }
  elements.installed.textContent = "";
  if (!modules.length) {
    const item = document.createElement("li");
    item.textContent = "No modules installed.";
    elements.installed.appendChild(item);
    return;
  }

  modules.forEach((module) => {
    const card = document.createElement("li");
    card.className = "module-card";
    const name = document.createElement("div");
    name.className = "module-name";
    name.textContent = module.name || module.id || "Module";
    const meta = document.createElement("div");
    meta.className = "module-meta";
    meta.textContent = `Version: ${module.version || "--"} • ${
      module.enabled ? "Enabled" : "Disabled"
    }`;
    card.appendChild(name);
    card.appendChild(meta);
    if (module.web_components?.length) {
      const link = document.createElement("a");
      link.className = "module-link";
      link.href = module.web_components[0].path;
      link.textContent = "Open Module UI";
      link.target = "_blank";
      card.appendChild(link);
    }
    const actions = document.createElement("div");
    actions.className = "module-actions";
    const toggle = document.createElement("button");
    toggle.className = "btn btn-secondary";
    toggle.textContent = module.enabled ? "Disable" : "Enable";
    toggle.addEventListener("click", async () => {
      try {
        await apiPost(
          `/api/v1/modules/${module.enabled ? "disable" : "enable"}/${module.id}`,
          {}
        );
        loadModules();
      } catch (error) {
        showToast("Unable to update module state.", "error");
      }
    });
    const uninstall = document.createElement("button");
    uninstall.className = "btn btn-ghost";
    uninstall.textContent = "Uninstall";
    uninstall.addEventListener("click", async () => {
      try {
        await apiDelete(`/api/v1/modules/uninstall/${module.id}`);
        loadModules();
      } catch (error) {
        showToast("Unable to uninstall module.", "error");
      }
    });
    actions.appendChild(toggle);
    actions.appendChild(uninstall);
    card.appendChild(actions);
    elements.installed.appendChild(card);
  });
}

async function loadModules() {
  try {
    const payload = await apiGet("/api/v1/modules/list");
    const data = extractData(payload) || {};
    renderInstalled(data.modules || []);
  } catch (error) {
    showToast("Unable to load modules.", "error");
  }
}

function setupActions() {
  const uploadButton = document.getElementById("upload-module");
  if (uploadButton) {
    uploadButton.addEventListener("click", async () => {
      const moduleUrl = window.prompt("Enter module archive path or URL:");
      if (!moduleUrl) {
        return;
      }
      try {
        await apiPost("/api/v1/modules/install", { module_url: moduleUrl });
        showToast("Module installed.", "success");
        loadModules();
      } catch (error) {
        showToast("Unable to install module.", "error");
      }
    });
  }
}

function init() {
  initTabs(document.querySelector("[data-tabs]"));
  const refresh = document.getElementById("refresh-modules");
  if (refresh) {
    refresh.addEventListener("click", loadModules);
  }
  setupActions();
  loadModules();
}

document.addEventListener("DOMContentLoaded", init);

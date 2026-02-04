import { apiDelete, apiGet, apiPost, extractData } from "../api.js";
import { initTabs } from "../components.js";
import { modalPrompt } from "../modal.js";

const elements = {
  installed: document.getElementById("installed-modules"),
  available: document.getElementById("available-modules"),
  availableEmpty: document.getElementById("available-empty"),
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

/** @type {Array<{ module_id: string, name?: string, current_version?: string, available_version?: string }>} */
let moduleUpdates = [];

function renderInstalled(modules, updates = []) {
  moduleUpdates = updates || moduleUpdates;
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
    const updateInfo = moduleUpdates.find((u) => u.module_id === module.id);
    if (updateInfo) {
      const updateNote = document.createElement("div");
      updateNote.className = "module-update-note";
      updateNote.textContent = `Update available: ${updateInfo.available_version || "?"}`;
      card.appendChild(updateNote);
    }
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
    if (updateInfo) {
      const updateBtn = document.createElement("button");
      updateBtn.className = "btn btn-primary";
      updateBtn.textContent = "Update";
      updateBtn.addEventListener("click", async () => {
        try {
          await apiPost(`/api/v1/modules/update/${module.id}`, {});
          showToast("Module updated.", "success");
          loadModules();
        } catch (error) {
          showToast("Unable to update module.", "error");
        }
      });
      actions.appendChild(updateBtn);
    }
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

function renderAvailable(available) {
  if (!elements.available || !elements.availableEmpty) {
    return;
  }
  elements.available.textContent = "";
  elements.availableEmpty.hidden = true;
  if (!available.length) {
    elements.availableEmpty.hidden = false;
    return;
  }
  available.forEach((m) => {
    const card = document.createElement("li");
    card.className = "module-card";
    const name = document.createElement("div");
    name.className = "module-name";
    name.textContent = m.name || m.id || "Module";
    const meta = document.createElement("div");
    meta.className = "module-meta";
    let metaText = `Version: ${m.version || "--"}`;
    if (m.installed) {
      metaText += ` • Installed (${m.installed_version || "--"})`;
      if (m.update_available) metaText += " • Update available";
    }
    meta.textContent = metaText;
    card.appendChild(name);
    card.appendChild(meta);
    if (m.description) {
      const desc = document.createElement("p");
      desc.className = "module-description";
      desc.textContent = m.description;
      card.appendChild(desc);
    }
    const actions = document.createElement("div");
    actions.className = "module-actions";
    const mainBtn = document.createElement("button");
    mainBtn.className = "btn btn-primary";
    mainBtn.textContent = m.update_available ? "Update" : m.installed ? "Installed" : "Install";
    if (!m.installed || m.update_available) {
      mainBtn.disabled = false;
      mainBtn.addEventListener("click", async () => {
        try {
          if (m.installed && m.update_available) {
            await apiPost(`/api/v1/modules/update/${m.id}`, {});
            showToast("Module updated.", "success");
          } else {
            await apiPost("/api/v1/modules/install-from-repo", { module_id: m.id });
            showToast("Module installed.", "success");
          }
          loadModules();
          loadAvailable();
        } catch (error) {
          showToast(error?.message || "Action failed.", "error");
        }
      });
    } else {
      mainBtn.disabled = true;
    }
    actions.appendChild(mainBtn);
    card.appendChild(actions);
    elements.available.appendChild(card);
  });
}

async function loadModuleUpdates() {
  try {
    const payload = await apiGet("/api/v1/modules/updates");
    const data = extractData(payload) || {};
    return data.updates || [];
  } catch {
    return [];
  }
}

async function loadModules() {
  try {
    const [listPayload, updates] = await Promise.all([
      apiGet("/api/v1/modules/list"),
      loadModuleUpdates(),
    ]);
    const data = extractData(listPayload) || {};
    renderInstalled(data.modules || [], updates);
  } catch (error) {
    showToast("Unable to load modules.", "error");
  }
}

async function loadAvailable() {
  try {
    const payload = await apiGet("/api/v1/modules/available");
    const data = extractData(payload) || {};
    const list = data.available || [];
    if (data.message) {
      showToast(data.message, "info");
    }
    renderAvailable(list);
  } catch (error) {
    showToast("Unable to load available modules.", "error");
    if (elements.availableEmpty) {
      elements.availableEmpty.hidden = false;
      elements.availableEmpty.textContent = "Unable to load catalog.";
    }
  }
}

function setupActions() {
  const uploadButton = document.getElementById("upload-module");
  if (uploadButton) {
    uploadButton.addEventListener("click", async () => {
      const moduleUrl = await modalPrompt("Enter module archive path or URL", "", {
        label: "Path or URL",
      });
      if (moduleUrl === null || !moduleUrl.trim()) {
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
  const checkUpdates = document.getElementById("check-module-updates");
  if (checkUpdates) {
    checkUpdates.addEventListener("click", async () => {
      checkUpdates.disabled = true;
      checkUpdates.textContent = "Checking…";
      try {
        const updates = await loadModuleUpdates();
        const listPayload = await apiGet("/api/v1/modules/list");
        const data = extractData(listPayload) || {};
        renderInstalled(data.modules || [], updates);
        const count = updates.length;
        showToast(
          count ? `${count} update(s) available.` : "All modules are up to date.",
          count ? "success" : "info"
        );
      } catch {
        showToast("Unable to check for module updates.", "error");
      } finally {
        checkUpdates.disabled = false;
        checkUpdates.textContent = "Check for module updates";
      }
    });
  }
  const refreshAvailable = document.getElementById("refresh-available");
  if (refreshAvailable) {
    refreshAvailable.addEventListener("click", loadAvailable);
  }
  const tabs = document.querySelector("[data-tabs]");
  if (tabs) {
    tabs.addEventListener("click", (e) => {
      const target = e.target.closest("[data-tab-target]");
      if (target?.getAttribute("data-tab-target") === "available") {
        loadAvailable();
      }
    });
  }
  setupActions();
  loadModules();
}

document.addEventListener("DOMContentLoaded", init);

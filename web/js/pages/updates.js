import { apiGet, apiPost, apiUpload, extractData } from "../api.js";
import { initTabs } from "../components.js";

const elements = {
  current: document.getElementById("current-version"),
  available: document.getElementById("available-version"),
  isAvailable: document.getElementById("update-available"),
  notes: document.getElementById("release-notes"),
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

function renderUpdateStatus(data) {
  if (!elements.current) {
    return;
  }
  elements.current.textContent = data?.current_version || "--";
  elements.available.textContent = data?.available_version || "--";
  elements.isAvailable.textContent = data?.update_available ? "Yes" : "No";
  elements.notes.textContent = data?.release_notes || "Release notes pending.";
}

async function loadUpdates() {
  try {
    const payload = await apiGet("/api/v1/updates/check");
    const data = extractData(payload) || {};
    renderUpdateStatus(data);
  } catch (error) {
    showToast("Unable to check updates.", "error");
  }
}

function setupActions() {
  const checkButton = document.getElementById("check-updates");
  if (checkButton) {
    checkButton.addEventListener("click", loadUpdates);
  }

  const applyButton = document.getElementById("apply-update");
  if (applyButton) {
    applyButton.addEventListener("click", async () => {
      try {
        const payload = await apiPost("/api/v1/updates/apply", {});
        const data = extractData(payload) || {};
        showToast(
          data.status === "applied"
            ? "Update applied successfully."
            : "System is already up to date.",
          "success"
        );
        await loadUpdates();
      } catch (error) {
        showToast("Unable to apply update.", "error");
      }
    });
  }

  const rollbackButton = document.getElementById("rollback-update");
  if (rollbackButton) {
    rollbackButton.addEventListener("click", async () => {
      try {
        const payload = await apiPost("/api/v1/updates/rollback", {});
        const data = extractData(payload) || {};
        showToast("Rollback completed.", "success");
        await loadUpdates();
      } catch (error) {
        showToast("Unable to rollback update.", "error");
      }
    });
  }

  const backupButton = document.getElementById("create-backup");
  if (backupButton) {
    backupButton.addEventListener("click", () => {
      window.location.assign("/api/v1/backup/config");
    });
  }

  const cleanupButton = document.getElementById("cleanup-wizard");
  if (cleanupButton) {
    cleanupButton.addEventListener("click", () => {
      showToast(
        "Data cleanup tools will be enabled once retention policies are configured.",
        "info"
      );
    });
  }

  const restoreButton = document.getElementById("restore-backup");
  const backupInput = document.getElementById("backup-file");
  if (restoreButton && backupInput) {
    restoreButton.addEventListener("click", async () => {
      if (!backupInput.files?.length) {
        showToast("Select a backup file to restore.", "error");
        return;
      }
      const formData = new FormData();
      formData.append("file", backupInput.files[0]);
      try {
        await apiUpload("/api/v1/backup/restore", formData);
        showToast("Backup restored successfully.", "success");
      } catch (error) {
        showToast("Unable to restore backup.", "error");
      }
    });
  }
}

function init() {
  initTabs(document.querySelector("[data-tabs]"));
  const refresh = document.getElementById("refresh-updates");
  if (refresh) {
    refresh.addEventListener("click", loadUpdates);
  }
  setupActions();
  loadUpdates();
}

document.addEventListener("DOMContentLoaded", init);

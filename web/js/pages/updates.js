import { apiGet, apiPost, apiUpload, extractData } from "../api.js";
import { initTabs } from "../components.js";

const elements = {
  updateBranch: document.getElementById("update-branch"),
  current: document.getElementById("current-version"),
  lastUpdate: document.getElementById("last-update"),
  available: document.getElementById("available-version"),
  isAvailable: document.getElementById("update-available"),
  availableSince: document.getElementById("available-since"),
  notes: document.getElementById("release-notes"),
  detailsCommit: document.getElementById("update-details-commit"),
  commitMessage: document.getElementById("update-commit-message"),
  commitMeta: document.getElementById("update-commit-meta"),
  filesChangedSection: document.getElementById("files-changed-section"),
  filesChangedList: document.getElementById("files-changed-list"),
  detailsEmpty: document.getElementById("update-details-empty"),
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

function formatDateTime(iso) {
  if (!iso) return "--";
  try {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "--" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return "--";
  }
}

function renderUpdateStatus(data) {
  if (!elements.current) {
    return;
  }
  if (elements.updateBranch) {
    elements.updateBranch.textContent = data?.update_branch ?? "--";
  }
  elements.current.textContent = data?.current_version || "--";
  if (elements.lastUpdate) {
    elements.lastUpdate.textContent = formatDateTime(data?.last_update);
  }
  elements.available.textContent = data?.available_version || "--";
  elements.isAvailable.textContent = data?.update_available ? "Yes" : "No";
  if (elements.availableSince) {
    elements.availableSince.textContent = formatDateTime(data?.available_since);
  }
  elements.notes.textContent = data?.release_notes || "Release notes pending.";

  const hasCommitInfo = data?.available_commit_message || data?.available_commit_author;
  if (elements.detailsCommit && elements.commitMessage && elements.commitMeta) {
    if (hasCommitInfo) {
      elements.detailsCommit.hidden = false;
      elements.commitMessage.textContent = data.available_commit_message || "(no message)";
      const metaParts = [];
      if (data.available_commit_author) metaParts.push(data.available_commit_author);
      if (data.available_since) metaParts.push(formatDateTime(data.available_since));
      elements.commitMeta.textContent = metaParts.length ? metaParts.join(" · ") : "";
    } else {
      elements.detailsCommit.hidden = true;
      elements.commitMessage.textContent = "";
      elements.commitMeta.textContent = "";
    }
  }

  const filesChanged = Array.isArray(data?.files_changed) ? data.files_changed : [];
  if (elements.filesChangedSection && elements.filesChangedList) {
    if (filesChanged.length === 0) {
      elements.filesChangedSection.hidden = true;
      elements.filesChangedList.innerHTML = "";
    } else {
      elements.filesChangedSection.hidden = false;
      elements.filesChangedList.innerHTML = filesChanged
        .slice(0, 100)
        .map((path) => `<li><code>${escapeHtml(path)}</code></li>`)
        .join("");
      if (filesChanged.length > 100) {
        elements.filesChangedList.innerHTML += `<li class="section-muted">… and ${filesChanged.length - 100} more</li>`;
      }
    }
  }

  const hasDetails = hasCommitInfo || filesChanged.length > 0;
  if (elements.detailsEmpty) {
    elements.detailsEmpty.hidden = hasDetails;
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

async function fetchCheckUpdates() {
  const url = new URL("/api/v1/updates/check", window.location.origin);
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  const response = await fetch(url.toString(), {
    method: "GET",
    headers: { Accept: "application/json" },
    signal: controller.signal,
  });
  clearTimeout(timeoutId);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = payload?.error?.message || `Request failed (${response.status})`;
    throw new Error(msg);
  }
  return payload;
}

async function loadUpdates() {
  const checkButton = document.getElementById("check-updates");
  const originalLabel = checkButton?.textContent ?? "Check for Updates";

  function setChecking(checking) {
    if (checkButton) {
      checkButton.disabled = checking;
      checkButton.textContent = checking ? "Checking…" : originalLabel;
    }
  }

  setChecking(true);
  try {
    const payload = await fetchCheckUpdates();
    const data = extractData(payload) || {};
    renderUpdateStatus(data);
    if (data?.update_available) {
      showToast("Update available. You can apply it below.", "success");
    } else {
      const note = (data?.release_notes || "").trim();
      const isLimited =
        note.includes("Version comparison unavailable") ||
        note.includes("git not available");
      showToast(
        isLimited ? "Update check complete. " + note : "Update check complete. You're up to date.",
        isLimited ? "info" : "success"
      );
    }
  } catch (error) {
    const message =
      error?.name === "AbortError"
        ? "Check timed out."
        : (error?.message || "Unable to check updates.");
    showToast(message, "error");
    renderUpdateStatus({ release_notes: message });
  } finally {
    setChecking(false);
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
        if (data.dry_run) {
          showToast("Dry run: update not applied. Set RPI_ENGINEER_DRY_RUN=0 to apply.", "info");
        } else if (data.status === "applied") {
          showToast("Update applied successfully (configuration kept).", "success");
        } else {
          showToast("System is already up to date.", "success");
        }
        await loadUpdates();
      } catch (error) {
        showToast("Unable to apply update.", "error");
      }
    });
  }

  const reconfigureButton = document.getElementById("reconfigure-update");
  if (reconfigureButton) {
    reconfigureButton.addEventListener("click", async () => {
      try {
        const payload = await apiPost("/api/v1/updates/reconfigure", {});
        const data = extractData(payload) || {};
        if (data.status === "reconfigure_dry_run") {
          showToast(data.message || "Reconfigure dry run. Set RPI_ENGINEER_DRY_RUN=0 to run.", "info");
        } else if (data.status === "reconfigured") {
          showToast(data.message || "Configuration re-applied. Reboot recommended for hotspot.", "success");
        } else {
          showToast("Reconfigure completed.", "success");
        }
        await loadUpdates();
      } catch (error) {
        showToast("Reconfigure failed. You may need to run the install script as root.", "error");
      }
    });
  }

  const reinstallButton = document.getElementById("reinstall-from-scratch");
  if (reinstallButton) {
    reinstallButton.addEventListener("click", async () => {
      if (!window.confirm("Reinstall from scratch will remove the application directory and run a full install using your existing config. This may take several minutes. Continue?")) {
        return;
      }
      try {
        const payload = await apiPost("/api/v1/updates/reinstall", {});
        const data = extractData(payload) || {};
        if (data.status === "reinstall_dry_run") {
          showToast(data.message || "Reinstall dry run. Set RPI_ENGINEER_DRY_RUN=0 to run.", "info");
        } else if (data.status === "reinstalled") {
          showToast(data.message || "Reinstall from scratch complete. Reboot recommended.", "success");
        } else {
          showToast("Reinstall completed.", "success");
        }
        await loadUpdates();
      } catch (error) {
        showToast("Reinstall from scratch failed. You may need to run the install script as root.", "error");
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

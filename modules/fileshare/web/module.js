import { apiGet, extractData } from "/js/api.js";

const elements = {
  ftp: document.getElementById("fileshare-module-ftp"),
  sftp: document.getElementById("fileshare-module-sftp"),
  path: document.getElementById("fileshare-module-path"),
};

async function loadFileshareStatus() {
  try {
    const payload = await apiGet("/api/v1/fileshare/status");
    const data = extractData(payload) || {};
    if (elements.ftp) {
      elements.ftp.textContent =
        data.ftp_running === true ? "Running" : "Stopped";
    }
    if (elements.sftp) {
      elements.sftp.textContent =
        data.sftp_running === true ? "Running" : "Stopped";
    }
    if (elements.path) {
      elements.path.textContent = data.config?.share_path || "--";
    }
  } catch (_err) {
    if (elements.ftp) {
      elements.ftp.textContent = "Unavailable";
    }
    if (elements.sftp) {
      elements.sftp.textContent = "Unavailable";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadFileshareStatus();
});

import { apiGet, extractData } from "/js/api.js";

const elements = {
  ftp: document.getElementById("fileshare-status-ftp"),
  sftp: document.getElementById("fileshare-status-sftp"),
  path: document.getElementById("fileshare-status-path"),
};

async function loadStatus() {
  try {
    const payload = await apiGet("/api/v1/fileshare/status");
    const data = extractData(payload);
    if (elements.ftp) {
      elements.ftp.textContent = data.ftp_running ? "Running" : "Stopped";
    }
    if (elements.sftp) {
      elements.sftp.textContent = data.sftp_running ? "Running" : "Stopped";
    }
    if (elements.path) {
      elements.path.textContent = data?.config?.share_path || "--";
    }
  } catch (error) {
    if (elements.ftp) {
      elements.ftp.textContent = "Unavailable";
    }
    if (elements.sftp) {
      elements.sftp.textContent = "Unavailable";
    }
  }
}

loadStatus();

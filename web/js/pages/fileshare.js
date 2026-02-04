import { apiDelete, apiGet, apiPost, apiPut, apiUpload, extractData } from "../api.js";
import { modalPrompt } from "../modal.js";

const elements = {
  refresh: document.getElementById("refresh-fileshare"),
  saveConfig: document.getElementById("fileshare-save-config"),
  sharePath: document.getElementById("fileshare-share-path"),
  enableFtp: document.getElementById("fileshare-enable-ftp"),
  ftpBind: document.getElementById("fileshare-ftp-bind"),
  ftpPort: document.getElementById("fileshare-ftp-port"),
  ftpAnon: document.getElementById("fileshare-ftp-anon"),
  ftpAnonDir: document.getElementById("fileshare-ftp-anon-dir"),
  enableSftp: document.getElementById("fileshare-enable-sftp"),
  sftpBind: document.getElementById("fileshare-sftp-bind"),
  sftpPort: document.getElementById("fileshare-sftp-port"),
  statusFtp: document.getElementById("fileshare-status-ftp"),
  statusSftp: document.getElementById("fileshare-status-sftp"),
  statusError: document.getElementById("fileshare-status-error"),
  userName: document.getElementById("fileshare-user-name"),
  userPassword: document.getElementById("fileshare-user-password"),
  userKeys: document.getElementById("fileshare-user-keys"),
  addUser: document.getElementById("fileshare-add-user"),
  userList: document.getElementById("fileshare-user-list"),
  fileInput: document.getElementById("fileshare-file"),
  uploadButton: document.getElementById("fileshare-upload"),
  dropzone: document.getElementById("fileshare-dropzone"),
  fileList: document.getElementById("fileshare-file-list"),
};

const DEFAULTS = {
  share_path: "",
  enable_ftp: false,
  enable_sftp_scp: false,
  ftp_bind_addresses: "0.0.0.0",
  sftp_bind_addresses: "0.0.0.0",
  ftp_port: 2121,
  sftp_port: 2222,
  ftp_anonymous: "off",
  ftp_anonymous_write_dir: "",
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

async function loadConfig() {
  const payload = await apiGet("/api/v1/fileshare/config");
  const data = { ...DEFAULTS, ...(extractData(payload) || {}) };
  if (elements.sharePath) elements.sharePath.value = data.share_path || "";
  if (elements.enableFtp) elements.enableFtp.checked = Boolean(data.enable_ftp);
  if (elements.ftpBind) elements.ftpBind.value = data.ftp_bind_addresses || DEFAULTS.ftp_bind_addresses;
  if (elements.ftpPort) elements.ftpPort.value = data.ftp_port || DEFAULTS.ftp_port;
  if (elements.ftpAnon) elements.ftpAnon.value = data.ftp_anonymous || DEFAULTS.ftp_anonymous;
  if (elements.ftpAnonDir) elements.ftpAnonDir.value = data.ftp_anonymous_write_dir || "";
  if (elements.enableSftp) elements.enableSftp.checked = Boolean(data.enable_sftp_scp);
  if (elements.sftpBind) elements.sftpBind.value = data.sftp_bind_addresses || DEFAULTS.sftp_bind_addresses;
  if (elements.sftpPort) elements.sftpPort.value = data.sftp_port || DEFAULTS.sftp_port;
}

async function loadStatus() {
  const payload = await apiGet("/api/v1/fileshare/status");
  const data = extractData(payload) || {};
  if (elements.statusFtp) elements.statusFtp.textContent = data.ftp_running ? "Running" : "Stopped";
  if (elements.statusSftp) elements.statusSftp.textContent = data.sftp_running ? "Running" : "Stopped";
  if (elements.statusError) elements.statusError.textContent = data.last_error || "--";
}

function renderUsers(users = []) {
  if (!elements.userList) return;
  elements.userList.textContent = "";
  if (!users.length) {
    const item = document.createElement("li");
    item.textContent = "No users configured.";
    elements.userList.appendChild(item);
    return;
  }
  users.forEach((user) => {
    const item = document.createElement("li");
    item.className = "status-item";
    const label = document.createElement("span");
    label.textContent = user.username;
    const actions = document.createElement("div");
    actions.className = "inline-actions";
    const reset = document.createElement("button");
    reset.className = "btn btn-ghost";
    reset.textContent = "Reset password";
    reset.addEventListener("click", () => resetPassword(user.username));
    const remove = document.createElement("button");
    remove.className = "btn btn-ghost";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => deleteUser(user.username));
    actions.append(reset, remove);
    item.append(label, actions);
    elements.userList.appendChild(item);
  });
}

async function loadUsers() {
  const payload = await apiGet("/api/v1/fileshare/users");
  const data = extractData(payload) || {};
  renderUsers(Array.isArray(data.users) ? data.users : []);
}

async function loadFiles() {
  const payload = await apiGet("/api/v1/fileshare/files");
  const data = extractData(payload) || {};
  if (!elements.fileList) return;
  elements.fileList.textContent = "";
  const items = Array.isArray(data.items) ? data.items : [];
  if (!items.length) {
    const item = document.createElement("li");
    item.textContent = "No files in share folder.";
    elements.fileList.appendChild(item);
    return;
  }
  items.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "status-item";
    item.textContent = `${entry.name} (${entry.type})`;
    elements.fileList.appendChild(item);
  });
}

async function saveConfig() {
  const payload = {
    share_path: elements.sharePath?.value || "",
    enable_ftp: Boolean(elements.enableFtp?.checked),
    ftp_bind_addresses: elements.ftpBind?.value || DEFAULTS.ftp_bind_addresses,
    ftp_port: Number(elements.ftpPort?.value || DEFAULTS.ftp_port),
    ftp_anonymous: elements.ftpAnon?.value || "off",
    ftp_anonymous_write_dir: elements.ftpAnonDir?.value || "",
    enable_sftp_scp: Boolean(elements.enableSftp?.checked),
    sftp_bind_addresses: elements.sftpBind?.value || DEFAULTS.sftp_bind_addresses,
    sftp_port: Number(elements.sftpPort?.value || DEFAULTS.sftp_port),
  };
  await apiPut("/api/v1/fileshare/config", payload);
  showToast("Configuration saved.", "success");
  await loadStatus();
}

async function addUser() {
  const username = elements.userName?.value?.trim() || "";
  const password = elements.userPassword?.value || "";
  const keysRaw = elements.userKeys?.value || "";
  const sshKeys = keysRaw
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length);
  await apiPost("/api/v1/fileshare/users", { username, password, ssh_public_keys: sshKeys });
  if (elements.userName) elements.userName.value = "";
  if (elements.userPassword) elements.userPassword.value = "";
  if (elements.userKeys) elements.userKeys.value = "";
  showToast("User added.", "success");
  await loadUsers();
}

async function deleteUser(username) {
  await apiDelete(`/api/v1/fileshare/users/${encodeURIComponent(username)}`);
  showToast("User deleted.", "success");
  await loadUsers();
}

async function resetPassword(username) {
  const password = await modalPrompt(`New password for ${username}`, "", {
    label: "New password",
  });
  if (password === null || password === "") {
    return;
  }
  await apiPut(`/api/v1/fileshare/users/${encodeURIComponent(username)}/password`, { password });
  showToast("Password updated.", "success");
}

async function uploadFile(file) {
  if (!file) {
    showToast("Select a file to upload.", "error");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  await apiUpload("/api/v1/fileshare/upload", formData);
  showToast("File uploaded.", "success");
  if (elements.fileInput) elements.fileInput.value = "";
  await loadFiles();
}

async function refreshAll() {
  try {
    await loadConfig();
    await loadStatus();
    await loadUsers();
    await loadFiles();
  } catch (error) {
    showToast("Unable to load file share data.", "error");
  }
}

if (elements.saveConfig) {
  elements.saveConfig.addEventListener("click", () => {
    saveConfig().catch((error) => showToast(error.message || "Save failed.", "error"));
  });
}

if (elements.addUser) {
  elements.addUser.addEventListener("click", () => {
    addUser().catch((error) => showToast(error.message || "Unable to add user.", "error"));
  });
}

if (elements.uploadButton) {
  elements.uploadButton.addEventListener("click", () => {
    uploadFile(elements.fileInput?.files?.[0]).catch((error) =>
      showToast(error.message || "Upload failed.", "error")
    );
  });
}

if (elements.dropzone) {
  elements.dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
  });
  elements.dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    uploadFile(file).catch((error) => showToast(error.message || "Upload failed.", "error"));
  });
}

if (elements.refresh) {
  elements.refresh.addEventListener("click", () => {
    refreshAll();
  });
}

refreshAll();

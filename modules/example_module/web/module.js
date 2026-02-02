async function loadExampleStatus() {
  const panel = document.getElementById("example-module-panel");
  if (!panel) {
    return;
  }
  const message = panel.querySelector(".module-message");
  try {
    const response = await fetch("/api/v1/example/hello");
    const payload = await response.json();
    const data = payload?.data || payload;
    if (message) {
      message.textContent = data?.message || "Module is ready.";
    }
  } catch (error) {
    if (message) {
      message.textContent = "Unable to reach example module.";
    }
  }
}

document.addEventListener("DOMContentLoaded", loadExampleStatus);

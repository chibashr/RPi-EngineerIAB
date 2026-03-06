import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureAdvancedMode, setMode, goToSimpleMode } from "../mode.js";
import { initNotifications } from "../notifications.js";

function setActiveNav() {
  const path = window.location.pathname;
  const page =
    path === "/advanced/" || path.endsWith("/advanced/index.html")
      ? "dashboard"
      : path.split("/").pop().replace(".html", "");

  const items = document.querySelectorAll(".nav-item");
  items.forEach((item) => {
    if (item.dataset.page === page) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  const breadcrumb = document.getElementById("breadcrumb");
  if (breadcrumb) {
    const label = page.charAt(0).toUpperCase() + page.slice(1);
    breadcrumb.textContent = label;
  }
}

function setupModeSwitch() {
  const button = document.getElementById("switch-simple");
  if (!button) {
    return;
  }
  button.addEventListener("click", async () => {
    const confirmed = await confirmModeSwitch("simple");
    if (!confirmed) {
      return;
    }
    setMode("simple");
    goToSimpleMode();
  });
}

function init() {
  ensureAdvancedMode();
  applyStoredTheme();
  initNotifications();
  initThemeSelector(document.getElementById("theme-select"));
  setActiveNav();
  setupModeSwitch();
}

document.addEventListener("DOMContentLoaded", init);

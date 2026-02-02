import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureAdvancedMode, setMode } from "../mode.js";

const SIDEBAR_STATE_KEY = "rpi-sidebar-collapsed";

function safeGetStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function safeSetStorage(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Ignore storage failures.
  }
}

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

function setupSidebarControls() {
  const sidebar = document.getElementById("sidebar");
  const collapseToggle = document.getElementById("collapse-toggle");
  const sidebarToggle = document.getElementById("sidebar-toggle");

  if (!sidebar || !collapseToggle || !sidebarToggle) {
    return;
  }

  const storedState = safeGetStorage(SIDEBAR_STATE_KEY);
  if (storedState === "true") {
    sidebar.classList.add("is-collapsed");
  }

  collapseToggle.addEventListener("click", () => {
    sidebar.classList.toggle("is-collapsed");
    safeSetStorage(
      SIDEBAR_STATE_KEY,
      sidebar.classList.contains("is-collapsed").toString()
    );
  });

  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("is-open");
  });
}

function setupModeSwitch() {
  const button = document.getElementById("switch-simple");
  if (!button) {
    return;
  }
  button.addEventListener("click", () => {
    if (!confirmModeSwitch("simple")) {
      return;
    }
    setMode("simple");
    window.location.assign("/");
  });
}

function init() {
  ensureAdvancedMode();
  applyStoredTheme();
  initThemeSelector(document.getElementById("theme-select"));
  setActiveNav();
  setupSidebarControls();
  setupModeSwitch();
}

document.addEventListener("DOMContentLoaded", init);

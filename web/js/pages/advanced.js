import { applyStoredTheme, initThemeSelector } from "../theme.js";
import { confirmModeSwitch, ensureAdvancedMode, setMode } from "../mode.js";

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
  const sidebarToggle = document.getElementById("sidebar-toggle");

  if (!sidebar || !sidebarToggle) {
    return;
  }

  sidebarToggle.addEventListener("click", () => {
    const isOpen = sidebar.classList.toggle("is-open");
    sidebarToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });

  document.addEventListener("click", (e) => {
    if (
      sidebar.classList.contains("is-open") &&
      !sidebar.contains(e.target) &&
      e.target !== sidebarToggle &&
      !sidebarToggle.contains(e.target)
    ) {
      sidebar.classList.remove("is-open");
      sidebarToggle.setAttribute("aria-expanded", "false");
    }
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

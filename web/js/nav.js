const Nav = (() => {
  const SIDEBAR_ID = "sidebar";
  const TOGGLE_SELECTOR = ".nav-mobile-toggle";
  const OVERLAY_SELECTOR = ".nav-overlay";
  const BREAKPOINT = 1024;

  let sidebar, toggle, overlay, focusableElements;

  function open() {
    sidebar.classList.add("is-open");
    overlay.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    sidebar.removeAttribute("aria-hidden");
    trapFocus();
    const iconMenu = toggle.querySelector(".icon-menu");
    const iconClose = toggle.querySelector(".icon-close");
    if (iconMenu) iconMenu.classList.add("hidden");
    if (iconClose) iconClose.classList.remove("hidden");
  }

  function close() {
    sidebar.classList.remove("is-open");
    overlay.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    sidebar.setAttribute("aria-hidden", "true");
    releaseFocus();
    const iconMenu = toggle.querySelector(".icon-menu");
    const iconClose = toggle.querySelector(".icon-close");
    if (iconMenu) iconMenu.classList.remove("hidden");
    if (iconClose) iconClose.classList.add("hidden");
    toggle.focus();
  }

  function trapFocus() {
    focusableElements = sidebar.querySelectorAll(
      'a, button, input, select, [tabindex]:not([tabindex="-1"])'
    );
    if (focusableElements.length) focusableElements[0].focus();
    sidebar.addEventListener("keydown", handleFocusTrap);
  }

  function releaseFocus() {
    sidebar.removeEventListener("keydown", handleFocusTrap);
  }

  function handleFocusTrap(e) {
    if (e.key !== "Tab" || !focusableElements.length) return;
    const first = focusableElements[0];
    const last = focusableElements[focusableElements.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function isDesktop() {
    return window.innerWidth >= BREAKPOINT;
  }

  function init() {
    sidebar = document.getElementById(SIDEBAR_ID);
    toggle = document.querySelector(TOGGLE_SELECTOR);
    overlay = document.querySelector(OVERLAY_SELECTOR);

    if (!sidebar || !toggle || !overlay) return;

    if (!isDesktop()) {
      sidebar.setAttribute("aria-hidden", "true");
    }

    toggle.addEventListener("click", () => {
      const isOpen = sidebar.classList.contains("is-open");
      isOpen ? close() : open();
    });

    overlay.addEventListener("click", close);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && sidebar.classList.contains("is-open")) {
        close();
      }
    });

    window.addEventListener("resize", () => {
      if (isDesktop() && sidebar.classList.contains("is-open")) {
        sidebar.classList.remove("is-open");
        overlay.classList.remove("is-open");
        sidebar.removeAttribute("aria-hidden");
        toggle.setAttribute("aria-expanded", "false");
        releaseFocus();
        const iconMenu = toggle.querySelector(".icon-menu");
        const iconClose = toggle.querySelector(".icon-close");
        if (iconMenu) iconMenu.classList.remove("hidden");
        if (iconClose) iconClose.classList.add("hidden");
      }
    });
  }

  return { init, open, close };
})();

document.addEventListener("DOMContentLoaded", () => Nav.init());

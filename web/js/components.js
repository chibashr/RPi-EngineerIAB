export function initTabs(container) {
  if (!container) {
    return;
  }
  const tabButtons = container.querySelectorAll("[data-tab-target]");
  const searchRoot = container.parentElement || document;
  const tabPanels = searchRoot.querySelectorAll("[data-tab-panel]");

  if (!tabButtons.length || !tabPanels.length) {
    return;
  }

  const activateTab = (target) => {
    tabButtons.forEach((button) => {
      const isActive = button.dataset.tabTarget === target;
      button.classList.toggle("tab-button-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    tabPanels.forEach((panel) => {
      panel.hidden = panel.dataset.tabPanel !== target;
    });
  };

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activateTab(button.dataset.tabTarget);
    });
  });

  activateTab(tabButtons[0].dataset.tabTarget);
}

export function createStatusItem(label, value) {
  const item = document.createElement("li");
  item.className = "status-item";
  const labelEl = document.createElement("span");
  labelEl.className = "status-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("span");
  valueEl.className = "status-value";
  valueEl.textContent = value || "--";
  item.appendChild(labelEl);
  item.appendChild(valueEl);
  return item;
}

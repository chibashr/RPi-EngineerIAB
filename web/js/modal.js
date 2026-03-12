/**
 * In-page modal dialogs. Replaces browser prompt/confirm so all input
 * happens inside the app (no native popups).
 *
 * - modalConfirm(message) → Promise<boolean>
 * - modalPrompt(message, defaultValue, options?) → Promise<string|null>
 * - modalForm(fields, title) → Promise<Record<string, string>|null>
 */

const CONTAINER_ID = "rpi-modal-container";

/**
 * @returns {HTMLElement}
 */
function getContainer() {
  let el = document.getElementById(CONTAINER_ID);
  if (!el) {
    el = document.createElement("div");
    el.id = CONTAINER_ID;
    el.className = "modal-container";
    el.setAttribute("aria-hidden", "true");
    document.body.appendChild(el);
  }
  return el;
}

/**
 * @param {HTMLElement} overlay
 * @param {() => void} onClose
 */
function bindEscape(overlay, onClose) {
  const handler = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      document.removeEventListener("keydown", handler);
    }
  };
  document.addEventListener("keydown", handler);
}

/**
 * Focus trap: keep focus inside the dialog while open.
 * @param {HTMLElement} dialog
 */
function trapFocus(dialog) {
  const focusables = dialog.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (!first) return;

  const trap = (e) => {
    if (e.key !== "Tab") return;
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };
  dialog.addEventListener("keydown", trap);
  first.focus();
}

/**
 * Show a confirm dialog (OK / Cancel).
 * @param {string} message
 * @returns {Promise<boolean>}
 */
export function modalConfirm(message) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "modal-confirm-title");

  let resolveRef;
  const promise = new Promise((resolve) => {
    resolveRef = resolve;
  });

  const close = (value) => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
    resolveRef(value);
  };

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-confirm">
      <h2 id="modal-confirm-title" class="modal-title">Confirm</h2>
      <p class="modal-message">${escapeHtml(message)}</p>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
        <button type="button" class="btn btn-primary modal-ok">OK</button>
      </div>
    </div>
  `;

  overlay.querySelector(".modal-cancel").addEventListener("click", () => close(false));
  overlay.querySelector(".modal-ok").addEventListener("click", () => close(true));
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close(false);
  });

  bindEscape(overlay, () => close(false));
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));

  return promise;
}

/**
 * Show a single-input prompt dialog.
 * @param {string} message
 * @param {string} defaultValue
 * @param {{ label?: string, inputType?: string }} [options]
 * @returns {Promise<string|null>}
 */
export function modalPrompt(message, defaultValue = "", options = {}) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "modal-prompt-title");

  const label = options.label != null ? options.label : "Value";
  const inputType = options.inputType === "password" ? "password" : "text";
  const inputId = "modal-prompt-input";

  let resolveRef;
  const promise = new Promise((resolve) => {
    resolveRef = resolve;
  });

  const close = (value) => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
    resolveRef(value);
  };

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-prompt">
      <h2 id="modal-prompt-title" class="modal-title">${escapeHtml(message)}</h2>
      <div class="field">
        <label class="field-label" for="${inputId}">${escapeHtml(label)}</label>
        <input type="${escapeHtml(inputType)}" id="${inputId}" class="modal-input" value="${escapeHtml(defaultValue)}" />
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
        <button type="button" class="btn btn-primary modal-ok">OK</button>
      </div>
    </div>
  `;

  const input = overlay.querySelector(`#${inputId}`);

  const submit = () => {
    close(input.value.trim());
  };

  overlay.querySelector(".modal-cancel").addEventListener("click", () => close(null));
  overlay.querySelector(".modal-ok").addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  });
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close(null);
  });

  bindEscape(overlay, () => close(null));
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));
  input.focus();
  input.select();

  return promise;
}

/**
 * @typedef {{ name: string, label: string, default?: string|boolean, type?: string, placeholder?: string, options?: { value: string, label: string }[] }} ModalField
 */

/**
 * Show a form modal with multiple fields. Submit returns an object of field names to values; Cancel returns null.
 * @param {ModalField[]} fields
 * @param {string} title
 * @param {{ onOpen?: (overlay: HTMLElement) => void }} options
 * @returns {Promise<Record<string, string>|null>}
 */
export function modalForm(fields, title, options = {}) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "modal-form-title");

  let resolveRef;
  const promise = new Promise((resolve) => {
    resolveRef = resolve;
  });

  const close = (value) => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
    resolveRef(value);
  };

  const formRows = fields
    .map((f) => {
      const id = `modal-form-${f.name}`;
      const type = f.type || "text";
      const def = f.default != null ? escapeHtml(String(f.default)) : "";
      const ph = f.placeholder != null ? ` placeholder="${escapeHtml(f.placeholder)}"` : "";
      const label = f.label ? `<label class="field-label" for="${id}">${escapeHtml(f.label)}</label>` : "";

      if (type === "select") {
        const optionsMarkup = (f.options || [])
          .map((opt) => {
            const selected = opt.value === f.default ? " selected" : "";
            return `<option value="${escapeHtml(opt.value)}"${selected}>${escapeHtml(opt.label)}</option>`;
          })
          .join("");
        return `
        <div class="field" data-field-name="${escapeHtml(f.name)}">
          ${label}
          <select id="${id}" name="${escapeHtml(f.name)}" class="modal-input">${optionsMarkup}</select>
        </div>
      `;
      }

      if (type === "textarea") {
        return `
        <div class="field" data-field-name="${escapeHtml(f.name)}">
          ${label}
          <textarea id="${id}" name="${escapeHtml(f.name)}" class="modal-input" rows="8">${def}</textarea>
        </div>
      `;
      }

      if (type === "checkbox") {
        const checked = f.default === true || f.default === "true" ? " checked" : "";
        return `
        <div class="field checkbox-field" data-field-name="${escapeHtml(f.name)}">
          <input type="checkbox" id="${id}" name="${escapeHtml(f.name)}"${checked} />
          <label class="field-label" for="${id}">${escapeHtml(f.label || "")}</label>
        </div>
      `;
      }

      if (type === "display") {
        return `
        <div class="field" data-field-name="${escapeHtml(f.name)}">
          ${label}
          <div class="modal-value" id="${id}">${def || "--"}</div>
        </div>
      `;
      }

      return `
        <div class="field" data-field-name="${escapeHtml(f.name)}">
          ${label}
          <input type="${escapeHtml(type)}" id="${id}" name="${escapeHtml(f.name)}" class="modal-input" value="${def}"${ph} />
        </div>
      `;
    })
    .join("");

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-form">
      <h2 id="modal-form-title" class="modal-title">${escapeHtml(title)}</h2>
      <form class="modal-form" id="modal-form-form">
        ${formRows}
        <div class="modal-actions">
          <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
          <button type="submit" class="btn btn-primary">Submit</button>
        </div>
      </form>
    </div>
  `;

  const form = overlay.querySelector("#modal-form-form");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const result = {};
    fields.forEach((f) => {
      if (f.type === "display") {
        return;
      }
      const input = overlay.querySelector(`#modal-form-${f.name}`);
      if (!input) {
        result[f.name] = "";
        return;
      }
      if (f.type === "checkbox") {
        result[f.name] = input.checked ? "true" : "false";
        return;
      }
      result[f.name] = input.value.trim();
    });
    close(result);
  });

  overlay.querySelector(".modal-cancel").addEventListener("click", () => close(null));
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close(null);
  });

  bindEscape(overlay, () => close(null));
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));
  const firstInput = overlay.querySelector(".modal-input");
  if (firstInput) {
    firstInput.focus();
    firstInput.select();
  }
  if (typeof options.onOpen === "function") {
    options.onOpen(overlay);
  }

  return promise;
}

/**
 * @typedef {{ recoveryTitle?: string, recoveryItems?: string[] }} ModalHelpOptions
 */

/**
 * Show a help/info modal with a title, numbered steps, and a close button at top right.
 * Optionally show a visually distinct recovery section (unnumbered list) below the steps.
 * @param {string} title
 * @param {string[]} steps - Plain-text step strings (will be escaped and shown as an ordered list)
 * @param {ModalHelpOptions} [options] - Optional recovery block: { recoveryTitle, recoveryItems }
 * @returns {Promise<void>}
 */
export function modalHelp(title, steps, options = {}) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "modal-help-title");

  const close = () => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
  };

  const stepsHtml =
    steps && steps.length
      ? "<ol class=\"modal-help-steps\">" +
        steps.map((s) => "<li>" + escapeHtml(s) + "</li>").join("") +
        "</ol>"
      : "";

  const recoveryTitle = options.recoveryTitle && options.recoveryItems?.length
    ? escapeHtml(options.recoveryTitle)
    : "";
  const recoveryHtml =
    recoveryTitle && options.recoveryItems?.length
      ? "<div class=\"modal-help-recovery\">" +
        "<h3 class=\"modal-help-recovery-title\">" + recoveryTitle + "</h3>" +
        "<ul class=\"modal-help-recovery-list\">" +
        options.recoveryItems.map((s) => "<li>" + escapeHtml(s) + "</li>").join("") +
        "</ul></div>"
      : "";

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-help">
      <div class="modal-header">
        <h2 id="modal-help-title" class="modal-title">${escapeHtml(title)}</h2>
        <button type="button" class="btn btn-ghost modal-close-top" aria-label="Close">×</button>
      </div>
      <div class="modal-help-body">${stepsHtml}${recoveryHtml}</div>
    </div>
  `;

  overlay.querySelector(".modal-close-top").addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  bindEscape(overlay, close);
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));

  return Promise.resolve();
}

/**
 * Show a help modal with a title, multiple subsections (each with its own heading and numbered steps), and close at top right.
 * @param {string} title - Modal title
 * @param {{ title: string, steps: string[] }[]} sections - Array of { title, steps }; each step string is escaped
 * @returns {Promise<void>}
 */
export function modalHelpSections(title, sections) {
  const container = getContainer();
  container.setAttribute("aria-hidden", "false");
  container.innerHTML = "";

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "modal-help-title");

  const close = () => {
    overlay.remove();
    if (container.children.length === 0) {
      container.setAttribute("aria-hidden", "true");
    }
  };

  const sectionsHtml =
    sections && sections.length
      ? sections
          .map(
            (sec) =>
              "<div class=\"modal-help-section\">" +
              "<h3 class=\"modal-help-section-title\">" +
              escapeHtml(sec.title) +
              "</h3>" +
              (sec.steps && sec.steps.length
                ? "<ol class=\"modal-help-steps\">" +
                  sec.steps.map((s) => "<li>" + escapeHtml(s) + "</li>").join("") +
                  "</ol>"
                : "") +
              "</div>"
          )
          .join("")
      : "";

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-help">
      <div class="modal-header">
        <h2 id="modal-help-title" class="modal-title">${escapeHtml(title)}</h2>
        <button type="button" class="btn btn-ghost modal-close-top" aria-label="Close">×</button>
      </div>
      <div class="modal-help-body">${sectionsHtml}</div>
    </div>
  `;

  overlay.querySelector(".modal-close-top").addEventListener("click", close);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  bindEscape(overlay, close);
  container.appendChild(overlay);
  trapFocus(overlay.querySelector(".modal-dialog"));

  return Promise.resolve();
}

function escapeHtml(str) {
  if (str == null) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

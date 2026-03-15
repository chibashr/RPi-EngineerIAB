const TOKEN_KEY = "admin_token";
const EXPIRY_KEY = "admin_token_expiry";

export function getToken() {
  try {
    const expiry = sessionStorage.getItem(EXPIRY_KEY);
    if (expiry) {
      const t = parseInt(expiry, 10);
      if (!Number.isNaN(t) && Date.now() < t) {
        return sessionStorage.getItem(TOKEN_KEY);
      }
    }
    return null;
  } catch {
    return null;
  }
}

export function setToken(token, expiresIn) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    const expiry = Date.now() + (Number(expiresIn) || 0) * 1000;
    sessionStorage.setItem(EXPIRY_KEY, String(expiry));
  } catch {
    // ignore
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(EXPIRY_KEY);
  } catch {
    // ignore
  }
}

export function isAdmin() {
  return getToken() !== null;
}

export function showLoginModal() {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "login-overlay";
    overlay.style.cssText =
      "position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;";

    const card = document.createElement("div");
    card.className = "login-card";
    card.style.cssText =
      "background:var(--surface, #fff);padding:1.5rem;border-radius:8px;box-shadow:0 4px 20px rgba(0,0,0,0.15);min-width:280px;max-width:90vw;";

    const heading = document.createElement("h2");
    heading.textContent = "Admin Login";
    heading.style.cssText = "margin:0 0 1rem;font-size:1.25rem;";

    const form = document.createElement("form");
    form.style.cssText = "display:flex;flex-direction:column;gap:0.75rem;";

    const label = document.createElement("label");
    label.textContent = "Password";
    label.setAttribute("for", "login-password");
    const input = document.createElement("input");
    input.id = "login-password";
    input.type = "password";
    input.autocomplete = "current-password";
    input.placeholder = "Admin password";
    input.style.cssText =
      "padding:0.5rem;border:1px solid #ccc;border-radius:4px;font-size:1rem;";

    const errorSpan = document.createElement("span");
    errorSpan.className = "login-error";
    errorSpan.style.cssText = "color:var(--error,#b91c1c);font-size:0.875rem;display:none;";

    const submitBtn = document.createElement("button");
    submitBtn.type = "submit";
    submitBtn.textContent = "Log in";
    submitBtn.style.cssText =
      "padding:0.5rem 1rem;background:var(--primary,#2563eb);color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1rem;";

    form.appendChild(label);
    form.appendChild(input);
    form.appendChild(errorSpan);
    form.appendChild(submitBtn);
    card.appendChild(heading);
    card.appendChild(form);
    overlay.appendChild(card);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errorSpan.style.display = "none";
      errorSpan.textContent = "";
      const password = input.value;

      try {
        const url = new URL("/api/v1/auth/login", window.location.origin);
        const response = await fetch(url.toString(), {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ password }),
        });
        const data = await response.json().catch(() => ({}));

        if (response.ok && data?.token) {
          setToken(data.token, data.expires_in ?? 0);
          overlay.remove();
          resolve();
        } else {
          errorSpan.textContent = "Incorrect password";
          errorSpan.style.display = "block";
        }
      } catch {
        errorSpan.textContent = "Incorrect password";
        errorSpan.style.display = "block";
      }
    });

    document.body.appendChild(overlay);
    input.focus();
  });
}

export function requireAdmin(callback) {
  if (isAdmin()) {
    callback();
    return;
  }
  showLoginModal().then(callback);
}

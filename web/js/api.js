const DEFAULT_TIMEOUT_MS = 8000;

function withTimeout(promise, timeoutMs = DEFAULT_TIMEOUT_MS) {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      reject(new Error("Request timed out"));
    }, timeoutMs);

    promise
      .then((value) => {
        clearTimeout(timeoutId);
        resolve(value);
      })
      .catch((error) => {
        clearTimeout(timeoutId);
        reject(error);
      });
  });
}

function normalizeEndpoint(endpoint) {
  if (typeof endpoint !== "string" || !endpoint.startsWith("/")) {
    throw new Error("Invalid endpoint");
  }
  if (endpoint.startsWith("//")) {
    throw new Error("Invalid endpoint");
  }
  return endpoint;
}

export async function apiGet(endpoint, options = {}) {
  const safeEndpoint = normalizeEndpoint(endpoint);
  const url = new URL(safeEndpoint, window.location.origin);
  const response = await withTimeout(
    fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
      ...options,
    })
  );

  if (!response.ok) {
    const message = `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function apiPost(endpoint, body, options = {}) {
  const safeEndpoint = normalizeEndpoint(endpoint);
  const url = new URL(safeEndpoint, window.location.origin);
  const response = await withTimeout(
    fetch(url.toString(), {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
      ...options,
    })
  );

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.error?.message && typeof payload.error.message === "string") {
        message = payload.error.message;
      }
    } catch {
      // ignore non-JSON or parse errors
    }
    throw new Error(message);
  }

  return response.json();
}

export async function apiPut(endpoint, body, options = {}) {
  const safeEndpoint = normalizeEndpoint(endpoint);
  const url = new URL(safeEndpoint, window.location.origin);
  const response = await withTimeout(
    fetch(url.toString(), {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
      ...options,
    })
  );

  if (!response.ok) {
    const message = `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function apiDelete(endpoint, options = {}) {
  const safeEndpoint = normalizeEndpoint(endpoint);
  const url = new URL(safeEndpoint, window.location.origin);
  const response = await withTimeout(
    fetch(url.toString(), {
      method: "DELETE",
      headers: { Accept: "application/json" },
      ...options,
    })
  );

  if (!response.ok) {
    const message = `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export async function apiUpload(endpoint, formData, options = {}) {
  const safeEndpoint = normalizeEndpoint(endpoint);
  const url = new URL(safeEndpoint, window.location.origin);
  const response = await withTimeout(
    fetch(url.toString(), {
      method: "POST",
      body: formData,
      ...options,
    })
  );

  if (!response.ok) {
    const message = `Request failed (${response.status})`;
    throw new Error(message);
  }

  return response.json();
}

export function extractData(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  return payload.data ?? payload;
}

const DEFAULT_RETRY_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

class WebSocketClient {
  constructor(url, options = {}) {
    this.url = url;
    this.autoReconnect = options.autoReconnect !== false;
    this.socket = null;
    this.retryIndex = 0;
    this.handlers = new Map();
    this.heartbeatId = null;
    this.statusCallback = null;
    this.rawMessageHandler = null;
  }

  on(type, handler) {
    this.handlers.set(type, handler);
  }

  onStatus(callback) {
    this.statusCallback = callback;
  }

  setRawMessageHandler(handler) {
    this.rawMessageHandler = typeof handler === "function" ? handler : null;
  }

  connect() {
    this.socket = new WebSocket(this.url);
    this.notifyStatus("connecting");

    this.socket.addEventListener("open", () => {
      this.retryIndex = 0;
      this.startHeartbeat();
      this.notifyStatus("connected");
    });

    this.socket.addEventListener("close", () => {
      this.stopHeartbeat();
      this.notifyStatus("disconnected");
      this.scheduleReconnect();
    });

    this.socket.addEventListener("error", () => {
      this.notifyStatus("error");
    });

    this.socket.addEventListener("message", (event) => {
      try {
        const message = JSON.parse(event.data);
        if (this.rawMessageHandler) {
          this.rawMessageHandler(message);
        }
        const handler = this.handlers.get(message.type);
        if (handler) {
          handler(message);
        }
      } catch (error) {
        // Ignore malformed messages.
      }
    });
  }

  startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatId = window.setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  stopHeartbeat() {
    if (this.heartbeatId) {
      window.clearInterval(this.heartbeatId);
      this.heartbeatId = null;
    }
  }

  scheduleReconnect() {
    if (!this.autoReconnect) {
      return;
    }
    const delay =
      DEFAULT_RETRY_DELAYS[this.retryIndex] ||
      DEFAULT_RETRY_DELAYS[DEFAULT_RETRY_DELAYS.length - 1];
    this.retryIndex = Math.min(
      this.retryIndex + 1,
      DEFAULT_RETRY_DELAYS.length - 1
    );
    window.setTimeout(() => this.connect(), delay);
  }

  notifyStatus(status) {
    if (this.statusCallback) {
      this.statusCallback(status);
    }
  }

  send(payload) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }

  close() {
    if (this.socket) {
      this.autoReconnect = false;
      this.stopHeartbeat();
      this.socket.close();
    }
  }
}

export function createWebSocketClient(path, options) {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const safePath = path.startsWith("/") ? path : `/${path}`;
  const url = `${protocol}://${window.location.host}${safePath}`;
  return new WebSocketClient(url, options);
}

const statusHandlers = new Map();
const statusConnectionCallbacks = [];
let statusClient = null;

function statusKey(source, type) {
  return `${source || ""}:${type || ""}`;
}

function ensureStatusClient() {
  if (statusClient) {
    return;
  }
  statusClient = createWebSocketClient("/ws/status", { autoReconnect: true });
  statusClient.setRawMessageHandler((message) => {
    const { source, type, data } = message || {};
    if (!source || !type) {
      return;
    }
    const handler = statusHandlers.get(statusKey(source, type));
    if (handler) {
      handler(data, message);
    }
  });
  statusClient.onStatus((status) => {
    statusConnectionCallbacks.forEach((cb) => {
      try {
        cb(status);
      } catch (_err) {
        // Ignore handler errors
      }
    });
  });
  statusClient.connect();
}

export function registerStatusHandler(source, type, handler) {
  if (typeof handler !== "function") {
    return;
  }
  statusHandlers.set(statusKey(source, type), handler);
  ensureStatusClient();
}

export function onStatusConnection(callback) {
  if (typeof callback !== "function") {
    return;
  }
  statusConnectionCallbacks.push(callback);
  ensureStatusClient();
}

ensureStatusClient();

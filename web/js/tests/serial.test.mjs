// Fast, JS-level tests for serial.js using Jest + jsdom-style DOM.
// This file is intentionally self-contained; wire it into your test runner as needed.

/**
 * Suggested Jest config snippet (jest.config.cjs):
 *
 *   module.exports = {
 *     testEnvironment: "jsdom",
 *     roots: ["<rootDir>/web/js/tests"],
 *     transform: {},
 *   };
 *
 * Then run: npx jest web/js/tests/serial.test.mjs
 */

import { jest } from "@jest/globals";

// Fake xterm.js Terminal for tests (serial.js uses window.Terminal).
function createFakeTerminal() {
  class FakeTerminal {
    constructor() {
      this.written = "";
      this.dataHandler = null;
    }
    open(container) {
      this.container = container;
    }
    write(data) {
      this.written += data || "";
    }
    onData(cb) {
      this.dataHandler = cb;
    }
    focus() {}
    clear() {
      this.written = "";
    }
    dispose() {}
  }
  globalThis.Terminal = FakeTerminal;
  if (typeof window !== "undefined") window.Terminal = FakeTerminal;
}

// Minimal fake DOM factory for the parts serial.js expects.
function createSerialDom() {
  createFakeTerminal();
  document.body.innerHTML = `
    <div id="toast-region"></div>
    <ul id="serial-device-list">
      <li id="serial-list-placeholder" class="serial-list-placeholder">Loading devices...</li>
    </ul>
    <div id="serial-detail-empty">
      <button id="serial-empty-connect" hidden>Connect</button>
      <button id="serial-empty-configure" hidden>Configure</button>
    </div>
    <div id="serial-detail-content" hidden>
      <div id="serial-console-panels"></div>
    </div>
    <table>
      <tbody id="serial-logs-table-body"></tbody>
    </table>
    <button id="refresh-serial">Refresh</button>
    <button id="new-serial-session">New serial session</button>
  `;
}

// Mock API + websocket modules before importing serial.js so its top-level code sees the mocks.
jest.unstable_mockModule("../api.js", () => {
  const apiState = {
    devicesResponse: { devices: [] },
    sessionsResponse: { sessions: [] },
    createdSessions: [],
  };

  return {
    apiGet: jest.fn(async (endpoint) => {
      if (endpoint.startsWith("/api/v1/serial/devices")) {
        return { data: apiState.devicesResponse };
      }
      if (endpoint === "/api/v1/serial/sessions") {
        return { data: apiState.sessionsResponse };
      }
      if (endpoint.startsWith("/api/v1/serial/logs")) {
        return { data: { logs: [] } };
      }
      throw new Error(`Unexpected apiGet endpoint: ${endpoint}`);
    }),
    apiPost: jest.fn(async (endpoint, body) => {
      if (endpoint === "/api/v1/serial/sessions") {
        const sessionId = `sess-${apiState.createdSessions.length + 1}`;
        apiState.createdSessions.push({ session_id: sessionId, device_id: body.device_id });
        apiState.sessionsResponse.sessions.push({ session_id: sessionId, device_id: body.device_id });
        return { data: { session_id: sessionId, device_id: body.device_id } };
      }
      if (endpoint === "/api/v1/serial/logs/export") {
        return { data: { archive: "/tmp/archive.zip" } };
      }
      throw new Error(`Unexpected apiPost endpoint: ${endpoint}`);
    }),
    apiPut: jest.fn(async () => ({ data: {} })),
    apiDelete: jest.fn(async () => ({ data: {} })),
    extractData: (payload) => payload.data ?? payload,
    __apiState: apiState,
  };
});

jest.unstable_mockModule("../websocket.js", () => {
  class FakeWebSocketClient {
    constructor(url, options = {}) {
      this.url = url;
      this.options = options;
      this.statusHandler = null;
      this.handlers = new Map();
      this.connected = false;
    }
    on(type, handler) {
      this.handlers.set(type, handler);
    }
    onStatus(cb) {
      this.statusHandler = cb;
    }
    connect() {
      // Simulate async open.
      setTimeout(() => {
        this.connected = true;
        this.statusHandler?.("connected");
      }, 0);
    }
    send(payload) {
      if (!this.connected) return false;
      // In tests we don't need full behavior; just pretend send succeeds.
      const handler = this.handlers.get(payload.type);
      if (handler) {
        handler(payload);
      }
      return true;
    }
    close() {
      if (this.connected) {
        this.connected = false;
        this.statusHandler?.("disconnected");
      }
    }
  }

  return {
    createWebSocketClient: (path, options) =>
      new FakeWebSocketClient(path, options),
  };
});

// Import the module under test with the mocked dependencies.
const { __testHooks } = await import("../pages/serial.js");
const { state, connectDevice, loadDevices, loadSessions, switchTab, resetStateForTest } = __testHooks;

describe("serial.js fast JS-level behavior", () => {
  beforeEach(async () => {
    createSerialDom();
    resetStateForTest();
    const { __apiState } = await import("../api.js");
    __apiState.devicesResponse = { devices: [] };
    __apiState.sessionsResponse = { sessions: [] };
    __apiState.createdSessions = [];
  });

  test("connecting to first device clears 'Connecting…' and creates a tab", async () => {
    const { __apiState, apiGet } = (await import("../api.js"));
    __apiState.devicesResponse = {
      devices: [
        { id: "dev1", path: "/dev/ttyTEST0", friendly_name: "Test Dev 1", chipset: "TestChip", status: "available" },
      ],
    };

    await loadDevices();
    await loadSessions();
    const deviceList = document.getElementById("serial-device-list");
    expect(deviceList).toBeTruthy();

    // Render devices then simulate clicking connect via direct call.
    await connectDevice("dev1");

    // Allow microtasks + setTimeout(0) in FakeWebSocketClient to run.
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(state.connectingDeviceId).toBeNull();
    expect(state.activeSessions.length).toBeGreaterThanOrEqual(1);

    const panels = document.querySelectorAll(".console-tab-panel");
    expect(panels.length).toBe(1);
  });

  test("connecting a second device adds a second session and keeps the first", async () => {
    const { __apiState } = (await import("../api.js"));
    __apiState.devicesResponse = {
      devices: [
        { id: "dev1", path: "/dev/ttyTEST0", friendly_name: "Test Dev 1", chipset: "Chip1", status: "available" },
        { id: "dev2", path: "/dev/ttyTEST1", friendly_name: "Test Dev 2", chipset: "Chip2", status: "available" },
      ],
    };

    await loadDevices();
    await loadSessions();
    await connectDevice("dev1");
    await new Promise((r) => setTimeout(r, 10));

    const firstSessions = [...state.activeSessions];
    expect(firstSessions.some((s) => s.device_id === "dev1")).toBe(true);

    // Connect second device.
    await connectDevice("dev2");
    await new Promise((r) => setTimeout(r, 10));

    const sessions = [...state.activeSessions];
    expect(sessions.some((s) => s.device_id === "dev1")).toBe(true);
    expect(sessions.some((s) => s.device_id === "dev2")).toBe(true);

    const panels = document.querySelectorAll(".console-tab-panel");
    expect(panels.length).toBe(2);
  });

  test("switching tabs focuses corresponding session terminal", async () => {
    const { __apiState } = (await import("../api.js"));
    __apiState.devicesResponse = {
      devices: [
        { id: "dev1", path: "/dev/ttyTEST0", friendly_name: "Dev1", chipset: "Chip1", status: "available" },
        { id: "dev2", path: "/dev/ttyTEST1", friendly_name: "Dev2", chipset: "Chip2", status: "available" },
      ],
    };

    await loadDevices();
    await loadSessions();
    await connectDevice("dev1");
    await connectDevice("dev2");
    await new Promise((r) => setTimeout(r, 10));

    const sessions = [...state.sessionMap.keys()];
    expect(sessions.length).toBe(2);

    const secondSessionId = sessions[1];
    switchTab(secondSessionId);

    const panel = document.querySelector(`.console-tab-panel[data-session-id="${secondSessionId}"]`);
    expect(panel).toBeTruthy();
    expect(panel.classList.contains("is-active")).toBe(true);
  });

  test("two concurrent sessions can send and receive data independently", async () => {
    const { __apiState } = (await import("../api.js"));
    __apiState.devicesResponse = {
      devices: [
        { id: "dev1", path: "/dev/ttyTEST0", friendly_name: "Dev1", chipset: "Chip1", status: "available" },
        { id: "dev2", path: "/dev/ttyTEST1", friendly_name: "Dev2", chipset: "Chip2", status: "available" },
      ],
    };

    await loadDevices();
    await loadSessions();
    await connectDevice("dev1");
    await connectDevice("dev2");
    await new Promise((r) => setTimeout(r, 10));

    const sessions = [...state.sessionMap.keys()];
    expect(sessions.length).toBe(2);
    const [session1, session2] = sessions;

    const state1 = state.sessionMap.get(session1);
    const state2 = state.sessionMap.get(session2);
    expect(state1).toBeTruthy();
    expect(state2).toBeTruthy();

    // Helper to type into a session via xterm's onData (simulating user input).
    // FakeWebSocketClient echoes sent data back through the "data" handler, which
    // calls term.write(), so we check state.xtermInstance.written.
    async function typeIntoSession(sessionState, text) {
      const term = sessionState.xtermInstance;
      expect(term).toBeTruthy();
      expect(term.dataHandler).toBeTruthy();
      for (const ch of text) {
        term.dataHandler(ch);
      }
      await new Promise((r) => setTimeout(r, 5));
    }

    // Type distinct text into each session.
    await typeIntoSession(state1, "AAA");
    await typeIntoSession(state2, "BBB");

    const term1 = state1.xtermInstance;
    const term2 = state2.xtermInstance;
    expect(term1).toBeTruthy();
    expect(term2).toBeTruthy();

    const text1 = term1.written || "";
    const text2 = term2.written || "";

    // Each tab should reflect its own traffic and not be polluted by the other.
    expect(text1).toContain("AAA");
    expect(text2).toContain("BBB");
  });
});


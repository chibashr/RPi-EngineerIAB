# Frontend

<!-- Generated: 2026-03-13 | Files scanned: 180+ | Token estimate: ~500 -->

## Page Tree

- **/** — Simple mode: `web/index.html` (landing, nav to features)
- **/advanced/** — Advanced mode: `web/advanced/index.html`; subpages: system, network, serial, capture, updates, backup, logs, modules, remote, fileshare, docs, snmp, syslog
- **/docs/** — User docs (HTML): quick-start, first-serial-session, first-capture, features/*, devices/*, troubleshooting/*, reference/*

## Component Hierarchy

- Static HTML per page; no SPA framework.
- Shared: `web/js/api.js` (API base URL, fetch helpers), `web/js/websocket.js`, `web/js/notifications.js`, `web/js/theme.js`, `web/js/modal.js`, `web/js/components.js`, `web/js/mode.js`
- Pages: `web/js/pages/*.js` — dashboard, simple, network, serial, capture, updates, system, modules, logs, advanced, docs, fileshare
- Module UIs: `modules/<name>/web/component.html`, `modules/<name>/web/module.js`; loaded via /modules/<id>/ when module enabled

## State Management

- No global store. Per-page JS holds state; API calls and WebSockets update DOM.
- Theme: `localStorage` key `rpi-theme` (light/dark/auto).
- Connection status: banner when API unreachable (e.g. simple-connection-banner).

## Data Flow

- Page load → fetch /api/v1/<group>/... for initial data
- WebSocket /ws/status for live dashboard/status (currently stubbed)
- Forms → POST/PUT to /api/v1/... → UI refresh or WebSocket follow-up
- Module assets: /modules/<module_id>/<path> served by gateway via module_manager.resolve_web_asset

## Key Files

- `web/index.html`, `web/advanced/index.html`
- `web/js/api.js`, `web/js/websocket.js`, `web/js/pages/dashboard.js`
- `web/css/base.css`, `web/css/theme.css`, `web/css/layout.css`, `web/css/components.css`

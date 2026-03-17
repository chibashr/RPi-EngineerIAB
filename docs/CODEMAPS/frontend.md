# Frontend

<!-- Reworked: 2026-03-17 | Supersedes prior frontend.md -->

## Page Tree

- **/** — Simple mode: `web/index.html` (landing, nav to features)
- **/advanced/** — Advanced mode: `web/advanced/index.html`; nav and subpages rendered dynamically based on enabled modules
- **/docs/** — User docs (HTML): quick-start, first-serial-session, first-capture, features/*, devices/*, troubleshooting/*, reference/*

## Component Hierarchy

- Static HTML per page; no SPA framework.
- Shared: `web/js/api.js` (API base URL, fetch helpers, Authorization header), `web/js/auth.js` (login modal, sessionStorage token), `web/js/websocket.js`, `web/js/notifications.js`, `web/js/theme.js`, `web/js/modal.js`, `web/js/components.js`, `web/js/mode.js`
- Pages: `web/js/pages/*.js` — dashboard, simple, network, system, updates, backup, logs, modules, advanced, docs
- **Module UIs**: `modules/<n>/web/component.html`, `modules/<n>/web/module.js`; injected into /advanced/ when module is enabled. Nav item and subpage only rendered if module present in /api/v1/modules/list response.

## Dynamic Nav

On load, `web/advanced/index.html` calls `GET /api/v1/dashboard` for initial state and `GET /api/v1/modules/list` for enabled module list. Nav items and subpages for modules are rendered only if that module appears in the list as enabled. Core nav items (system, network, logs, backup, updates, remote) are always rendered.

Nav item injection pattern:
```javascript
// web/js/mode.js (or advanced/index.js)
const { modules } = await api.get('/api/v1/modules/list');
modules.filter(m => m.enabled).forEach(m => injectModuleNav(m));
```

Module nav entries are injected in module registration order. Core nav entries always appear first.

## State Management

- No global store. Per-page JS holds state; API calls and WebSockets update DOM.
- Theme: `localStorage` key `rpi-theme` (light/dark/auto).
- Auth: token in sessionStorage; admin-only UI gated by login.
- Connection status: banner when API unreachable (e.g. simple-connection-banner).
- Module state: no local cache; always derived from /api/v1/modules/list on load.

## Data Flow

- Page load → `GET /api/v1/dashboard` for aggregated initial state (system, network, modules, sessions)
- WebSocket `/ws/status` takes over for live updates after initial render
- Module nav injected from dashboard/modules response
- Forms → POST/PUT to /api/v1/... → UI refresh or WebSocket follow-up
- Module assets: `/modules/<module_id>/<path>` served by gateway via module_manager.resolve_web_asset

## WebSocket: /ws/status

Single persistent connection for all live data. Message format:

```json
{
  "source": "system | network | <module_id>",
  "type": "<event_type>",
  "data": { ... }
}
```

Frontend dispatches on `source` + `type` to update the relevant page section. Replaces all per-page polling.

## Key Files

- `web/index.html`, `web/advanced/index.html`
- `web/js/api.js` — fetch helpers, base URL, auth header
- `web/js/websocket.js` — /ws/status connection, message dispatch
- `web/js/mode.js` — dynamic nav injection from modules list
- `web/js/pages/dashboard.js` — initial load from /api/v1/dashboard, then WS-driven updates
- `web/css/base.css`, `web/css/theme.css`, `web/css/layout.css`, `web/css/components.css`

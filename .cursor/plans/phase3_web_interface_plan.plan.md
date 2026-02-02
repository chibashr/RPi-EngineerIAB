---
name: Phase 3 - Web Interface Implementation Plan
overview: Detailed implementation plan for the full dual-mode web interface per WEB-INTERFACE-SPECIFICATION. Phase 3 delivers Simple mode, Advanced mode with shell/dashboard, all feature pages, real-time WebSocket integration, and polish. Depends on Phase 2 (Core Backend Services) being complete.
todos:
  - id: p3-3a-infra
    content: "3a: Create web/ structure, base layout, theme system, dark mode"
    status: pending
  - id: p3-3a-simple
    content: "3a: Implement Simple mode landing page (status, connection info, quick actions)"
    status: pending
  - id: p3-3a-mode-switch
    content: "3a: Implement mode switch (Simple ↔ Advanced) with persistence"
    status: pending
  - id: p3-3b-shell
    content: "3b: Implement Advanced mode shell (sidebar nav, collapsible)"
    status: pending
  - id: p3-3b-dashboard
    content: "3b: Implement Dashboard (metrics, network, services, captures, alerts)"
    status: pending
  - id: p3-3c-network
    content: "3c: Implement Network Management page (5 tabs)"
    status: pending
  - id: p3-3c-serial
    content: "3c: Implement Serial Console page (devices, sessions, xterm.js, logs)"
    status: pending
  - id: p3-3c-capture
    content: "3c: Implement Packet Capture page (start/stop, BPF, live view, list)"
    status: pending
  - id: p3-3c-system
    content: "3c: Implement System Management page (4 tabs)"
    status: pending
  - id: p3-3c-updates
    content: "3c: Implement Updates & Maintenance page (3 tabs)"
    status: pending
  - id: p3-3c-modules
    content: "3c: Implement Modules page (installed, available)"
    status: pending
  - id: p3-3c-logs
    content: "3c: Implement Logs & Monitoring page (3 tabs)"
    status: pending
  - id: p3-3c-docs
    content: "3c: Implement Documentation page (embedded docs per DOCUMENTATION-GUIDELINES)"
    status: pending
  - id: p3-3d-websocket
    content: "3d: Implement WebSocket clients (serial, capture live, status)"
    status: pending
  - id: p3-3d-polish
    content: "3d: Loading/error states, WCAG 2.1 Level A, performance <3s"
    status: pending
isProject: false
---

# Phase 3: Web Interface Implementation Plan

This plan implements the full dual-mode web interface per [WEB-INTERFACE-SPECIFICATION](.planning/WEB-INTERFACE-SPECIFICATION.md) (~2800 lines). It references [API-REFERENCE](.planning/API-REFERENCE.md), [DOCUMENTATION-GUIDELINES](.planning/DOCUMENTATION-GUIDELINES.md), [NETWORK-MANAGEMENT-SPECIFICATION](.planning/NETWORK-MANAGEMENT-SPECIFICATION.md), [SERIAL-CONSOLE-SPECIFICATION](.planning/SERIAL-CONSOLE-SPECIFICATION.md), and [PACKET-CAPTURE-SPECIFICATION](.planning/PACKET-CAPTURE-SPECIFICATION.md).

**Prerequisites**: Phase 2 complete (System, Network, Serial, Capture, Remote APIs + WebSocket endpoints).

---

## Document References Summary

| Document | Key Sections for Phase 3 |
|----------|--------------------------|
| **WEB-INTERFACE-SPECIFICATION** | Interface Overview, Design Principles, User Modes, Page Specifications (§4), Component Library (§5), Navigation (§6), Responsive Design (§7), Real-Time Updates (§8), Accessibility (§9), Performance (§10) |
| **API-REFERENCE** | Network, Serial, Capture, System, Updates, Logs, Modules, Remote, WebSocket APIs |
| **DOCUMENTATION-GUIDELINES** | User Documentation Structure, Embedded Documentation Format, docs/ folder layout |
| **NETWORK-MANAGEMENT-SPECIFICATION** | Interface CRUD, VLANs, Routing, Profiles, Hotspot |
| **SERIAL-CONSOLE-SPECIFICATION** | Device detection, sessions, WebSocket console, logging |
| **PACKET-CAPTURE-SPECIFICATION** | Start/stop, BPF filters, live stream, storage |

---

## Phase 3a: Infrastructure and Simple Mode

**Goal**: Static assets under `web/`, base layout, theme (including dark mode), responsive/mobile-first. Simple mode landing page with status, connection info, quick actions, and mode switch.

### 3a.1 Repository and Asset Structure

- [ ] Create `web/` directory structure:
  - `web/index.html` – Simple mode landing (default)
  - `web/advanced/` – Advanced mode pages
  - `web/css/` – Styles (base, theme, components)
  - `web/js/` – Application logic (modular)
  - `web/docs/` – Embedded documentation (per DOCUMENTATION-GUIDELINES)
  - `web/assets/` – Images, icons, fonts
- [ ] Add `requirements.txt` entry for static file serving if needed
- [ ] Ensure API gateway serves `web/` at root (or configure nginx/static server)

**Reference**: WEB-INTERFACE-SPECIFICATION §1 Core Requirements (offline, no CDN), §10 Performance (asset sizes).

### 3a.2 Base Layout and Theme System

- [ ] Implement base HTML template with:
  - Semantic structure: `<header>`, `<main>`, `<footer>`
  - `lang` attribute, unique `<title>` per page
  - Skip link: "Skip to main content" (first tab stop)
- [ ] Create CSS variables for theme:
  - Light mode: background, foreground, primary, accent, status colors (green/yellow/red)
  - Dark mode: same variables, inverted
  - Media query: `prefers-color-scheme` for auto
- [ ] Implement theme toggle (Light / Dark / Auto) stored in `localStorage`
- [ ] Respect `prefers-reduced-motion` for animations

**Reference**: WEB-INTERFACE-SPECIFICATION §2 Design Principles, §5 Component Library, §9 Accessibility.

### 3a.3 Responsive Breakpoints

- [ ] Define breakpoints: Mobile (0–639px), Tablet (640–1023px), Desktop (1024px+)
- [ ] Mobile-first CSS with min-width media queries
- [ ] Touch targets: minimum 44×44px (WCAG)
- [ ] Tables: card layout on mobile, full table on desktop

**Reference**: WEB-INTERFACE-SPECIFICATION §7 Responsive Design.

### 3a.4 Simple Mode Landing Page

**URL**: `/` or `/index.html`

- [ ] **Header**: Logo "RPi Engineer-in-a-Box", mode badge "Simple Mode", mode switch button
- [ ] **System Status Card** (per spec §4 Simple Mode Landing Page):
  - Health indicator: checkmark (green), warning (yellow), error (red)
  - Metrics grid: CPU, Memory, Temperature, Storage (icons, bars)
  - Network status: "WAN Connected via [interface]" or "No WAN Connection"
  - Expandable: interfaces, service summary, recent alerts
- [ ] **Connection Info Card**:
  - WiFi: SSID, password (show/hide), copy button
  - Remote: service name, ID, status dot, copy button
  - Privacy toggle to hide card
- [ ] **Quick Action Buttons** (large cards):
  - Capture Packets (disabled if no interfaces)
  - Serial Console (show device count)
  - View Logs (show alert badge if any)
  - Documentation
- [ ] **Mode Switch Section**: "Need advanced features?" + "Switch to Advanced Mode" button
- [ ] **Footer**: Version, last update timestamp, link to Advanced

**API calls**: `GET /api/v1/system/status`, `GET /api/v1/network/interfaces`, `GET /api/v1/remote/status` (or equivalent from Phase 2).

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Simple Mode Landing Page (lines 265–343).

### 3a.5 Mode Switch and Persistence

- [ ] Mode switch: Simple ↔ Advanced
- [ ] Persist Advanced mode in `localStorage` (survives refresh)
- [ ] Reset to Simple on reboot (no server-side persistence for mode)
- [ ] Confirmation/explanation when switching to Advanced

**Reference**: WEB-INTERFACE-SPECIFICATION §3 User Modes (lines 212–218).

### 3a.6 Component Library (Initial)

- [ ] Primary, Secondary, Danger buttons (44×44px min)
- [ ] Status Card, Action Card, Information Card
- [ ] Toast notifications (success, info, warning, error)
- [ ] Loading spinner, skeleton screens
- [ ] Form controls: text input, dropdown, toggle, checkbox

**Reference**: WEB-INTERFACE-SPECIFICATION §5 Component Library (lines 1540–1790).

---

## Phase 3b: Advanced Mode – Shell and Dashboard

**Goal**: Sidebar navigation, collapsible shell, dashboard with system metrics, network status, service status, active captures, recent alerts.

### 3b.1 Advanced Mode Shell

- [ ] Create `web/advanced/` layout with:
  - **Sidebar** (200px, collapsible to icons-only):
    - Logo at top
    - Nav items: Dashboard, Network, Serial, Capture, System, Updates, Modules, Logs, Documentation
    - Divider, "Switch to Simple Mode" at bottom
    - Collapse toggle button
  - **Main content area**: page title, breadcrumbs, action toolbar, content
- [ ] Mobile: hamburger menu, sidebar overlays content
- [ ] Active page highlighted in nav
- [ ] Breadcrumbs: `Dashboard > Network > Interface Configuration`

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Advanced Mode Structure (lines 239–258).

### 3b.2 Dashboard Page

**URL**: `/dashboard.html` or `/advanced/`

- [ ] **System Metrics** (top row cards):
  - CPU: percentage, 60s line chart, threshold colors
  - Memory: used/total, progress bar, breakdown
  - Temperature: value, trend, warning
  - Storage: root/data partitions, cleanup button
- [ ] **Network Status Panel**: table (Interface, Status, IP, Type, Speed), summary stats, quick actions
- [ ] **Service Status Panel**: list/table, status dots, Start/Stop/Restart, filters
- [ ] **Active Captures Panel**: running captures with Stop/View/Download; empty state + "Start Capture"
- [ ] **Recent Alerts Panel**: last 5 alerts, severity icons, "View All Logs"
- [ ] **Quick Actions Toolbar**: Start Capture, Open Serial, Check Updates, View Logs

**API calls**: System status, network interfaces, services list, capture list, logs/alerts.

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Advanced Mode Dashboard (lines 345–333).

---

## Phase 3c: Advanced Mode – Feature Pages

**Goal**: Implement all 8+ feature pages per spec. Order can be parallelized where pages are independent.

### 3c.1 Network Management Page

**URL**: `/advanced/network.html`

**Tabs**: Interfaces, VLANs, Routing, Profiles, Hotspot

- [ ] **Interfaces Tab**: Interface cards, configure modal (DHCP/Static, IP, gateway, DNS, MTU, metric), test connectivity
- [ ] **VLANs Tab**: VLAN list, Add/Edit modal (parent, VLAN ID, IP config)
- [ ] **Routing Tab**: Routes table, default gateway, add route, interface priority (failover)
- [ ] **Profiles Tab**: Saved profiles list, save current, load with preview
- [ ] **Hotspot Tab**: SSID, password, security, channel, DHCP range, connected clients
- [ ] **Factory Reset** section (bottom): warning, preserve hotspot checkbox, confirmations

**API**: `GET/PUT /api/v1/network/interfaces`, `network/routes`, `network/profiles`, `network/hotspot` (per API-REFERENCE, NETWORK-MANAGEMENT-SPECIFICATION).

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Network Management Page (lines 335–477).

### 3c.2 Serial Console Page

**URL**: `/advanced/serial.html`

- [ ] **Detected Devices**: Device cards (path, chipset, status), "Open Console", "Configure Settings"
- [ ] **Device Settings Modal**: Baud (9600–115200), data bits, parity, stop bits, flow control
- [ ] **Serial Console Modal**: xterm.js terminal, ANSI colors, scrollback, copy/paste
- [ ] **Controls**: Connect/Disconnect, Clear, Send/Receive file, settings (echo, wrap, font)
- [ ] **Footer**: duration, bytes Rx/Tx, logging status, Pause/Resume/Save Log
- [ ] **Active Sessions**: list with Switch/Close
- [ ] **Session Logs**: list, filters, View/Download/Delete, bulk export

**API**: `GET /api/v1/serial/devices`, `serial/sessions`, WebSocket for console I/O.

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Serial Console Page (lines 479–579), SERIAL-CONSOLE-SPECIFICATION.

### 3c.3 Packet Capture Page

**URL**: `/advanced/capture.html`

- [ ] **New Capture Modal**: name, interface, duration/size limits, BPF filter (with validate), simple filter GUI, advanced options (promiscuous, snapshot, buffer)
- [ ] **Active Captures**: real-time cards (duration, packets, size, rate), View Live, Pause/Stop/Download
- [ ] **Live Capture Viewer**: packet list, details tree, hex dump; filter bar, view options
- [ ] **Completed Captures**: filters, table, Analyze/Download/Delete, bulk actions
- [ ] **Capture Analyzer Modal**: packet list, details, hex, statistics (conversations, endpoints, protocol hierarchy)

**API**: `POST /api/v1/capture/captures`, `capture/stats`, WebSocket for live stream.

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Packet Capture Page (lines 581–733), PACKET-CAPTURE-SPECIFICATION.

### 3c.4 System Management Page

**URL**: `/advanced/system.html`

**Tabs**: Services, Power Management, Settings, System Information

- [ ] **Services Tab**: table (name, status, uptime, auto-start), Start/Stop/Restart, filters, bulk actions, details modal
- [ ] **Power Tab**: Shutdown/Restart (countdown, confirm), low power toggle, power status
- [ ] **Settings Tab**: hostname, timezone, NTP; web defaults (mode, theme, locale); notification thresholds; advanced (API, logging, storage)
- [ ] **System Info Tab**: hardware, software, network, USB, serial, health, export

**API**: `GET /api/v1/system/status`, `system/services`, `system/power`, etc.

**Reference**: WEB-INTERFACE-SPECIFICATION §4 System Management Page (lines 735–941).

### 3c.5 Updates & Maintenance Page

**URL**: `/advanced/updates.html`

**Tabs**: Software Updates, Configuration Backup, Data Management

- [ ] **Updates Tab**: current version, check for updates, install flow (progress modal), rollback, update history
- [ ] **Backup Tab**: create backup, backup list, restore modal, automatic backup settings
- [ ] **Data Tab**: storage overview, captures/logs/backups management, cleanup wizard, factory reset

**API**: `GET/POST /api/v1/updates/check`, `updates/apply`, `backup/*` (per API-REFERENCE, UPDATE-MAINTENANCE-SPECIFICATION).

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Updates & Maintenance Page (lines 943–1171).

### 3c.6 Modules Page

**URL**: `/advanced/modules.html`

**Tabs**: Installed Modules, Available Modules

- [ ] **Installed Tab**: module cards (icon, name, version, status), Configure, Enable/Disable, Uninstall
- [ ] **Available Tab**: catalog, search/filter, Install, module details modal
- [ ] **Upload Custom Module**: drag-drop, validate, install
- [ ] **Configure/Uninstall modals** with confirmations

**API**: `GET /api/v1/modules/list`, `modules/install`, `modules/uninstall` (Module Manager from Phase 4; stub if not yet implemented).

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Modules Page (lines 1173–1319), MODULE-SYSTEM-SPECIFICATION.

### 3c.7 Logs & Monitoring Page

**URL**: `/advanced/logs.html`

**Tabs**: System Logs, Performance Metrics, Alerts History

- [ ] **Logs Tab**: filter (level, service, time, search), table (timestamp, level, service, message), export
- [ ] **Metrics Tab**: time range, charts (CPU, Memory, Temperature, Disk, Network, Disk I/O)
- [ ] **Alerts Tab**: list (timestamp, severity, type, message, status), filters, details modal, acknowledge/resolve

**API**: `GET /api/v1/logs/system`, `logs/export`, Monitor/Logging service endpoints.

**Reference**: WEB-INTERFACE-SPECIFICATION §4 Logs & Monitoring Page (lines 1321–1498).

### 3c.8 Documentation Page

**URL**: `/docs/` or `/advanced/docs.html`

- [ ] **Layout**: left sidebar (ToC), main content, right sidebar ("On this page" anchors)
- [ ] **ToC structure** per WEB-INTERFACE-SPECIFICATION §4 Documentation Page (lines 1500–1610):
  - Getting Started, User Guides, Network, Serial, Packet Capture, System, Updates, Modules, Troubleshooting, Technical Reference, FAQ
- [ ] **Content**: Markdown rendered to HTML, syntax highlighting, copyable code blocks
- [ ] **Search**: full-text search across docs (future: can defer to Phase 6)
- [ ] **Docs source** in `web/docs/` per DOCUMENTATION-GUIDELINES (getting-started/, features/, troubleshooting/, devices/, reference/)

**Reference**: DOCUMENTATION-GUIDELINES §2 User Documentation Structure, §4 Embedded Documentation Format.

---

## Phase 3d: Real-Time and Polish

**Goal**: WebSocket clients for serial, capture live, optional status/events. Loading and error states. Accessibility (WCAG 2.1 Level A). Performance target <3s load.

### 3d.1 WebSocket Client Infrastructure

- [ ] Connect to `ws://{host}/ws/` on page load
- [ ] Heartbeat: ping/pong every 30s
- [ ] Reconnection: exponential backoff (1s, 2s, 4s, 8s, max 30s)
- [ ] Fallback: HTTP polling every 5s if WebSocket fails
- [ ] Message routing: `system_metrics`, `network_status`, `service_status`, `alert`, `capture_progress`, `serial_data`, `log_entry`

**Reference**: WEB-INTERFACE-SPECIFICATION §8 Real-Time Updates.

### 3d.2 WebSocket Integration by Feature

- [ ] **Serial Console**: `serial_data` → append to xterm.js, throttle if needed
- [ ] **Capture Live**: `capture_progress` → update packet list, stats
- [ ] **Dashboard/Status**: `system_metrics`, `network_status`, `service_status`, `alert` → update cards/panels
- [ ] **Logs page**: `log_entry` when active, else fetch on load

**Reference**: WEB-INTERFACE-SPECIFICATION §8 Update Frequencies.

### 3d.3 Loading and Error States

- [ ] Loading spinners for operations >500ms
- [ ] Skeleton screens for initial page load
- [ ] Error toasts with retry where applicable
- [ ] Empty states with helpful messages and CTAs
- [ ] "Reconnecting..." banner when WebSocket down

**Reference**: WEB-INTERFACE-SPECIFICATION §2 Design Principles (Immediate Feedback).

### 3d.4 Accessibility (WCAG 2.1 Level A)

- [ ] Keyboard: Tab order, Enter/Space/Esc, arrow keys in lists/tabs
- [ ] Focus indicators: visible, high-contrast
- [ ] ARIA: labels, live regions, roles where needed
- [ ] Color: never rely on color alone; use icons + text
- [ ] Contrast: 4.5:1 normal text, 3:1 large text
- [ ] `prefers-reduced-motion`: reduce/disable animations

**Reference**: WEB-INTERFACE-SPECIFICATION §9 Accessibility.

### 3d.5 Performance

- [ ] Target: <3s load on RPi 4
- [ ] Asset budget: HTML <50KB, CSS <100KB, JS <500KB, total <2MB
- [ ] Minify CSS/JS, gzip
- [ ] Lazy load images, defer non-critical JS
- [ ] Throttle UI updates (max 1/s for metrics)
- [ ] Test on RPi 4, Lighthouse >90

**Reference**: WEB-INTERFACE-SPECIFICATION §10 Performance Requirements.

---

## Exit Criteria

- [ ] Simple mode: landing page with status, connection info, quick actions, mode switch
- [ ] Advanced mode: sidebar, dashboard, all 8+ feature pages
- [ ] All pages consume Phase 2 APIs correctly
- [ ] WebSocket: serial console, capture live, status updates
- [ ] Works offline (no CDN), mobile and desktop usable
- [ ] WCAG 2.1 Level A, performance <3s load target

---

## Suggested Execution Order

1. **3a** (Infrastructure + Simple Mode) – foundation for everything
2. **3b** (Shell + Dashboard) – Advanced mode skeleton
3. **3c** – Feature pages (can parallelize):
   - Network, Serial, Capture (core field-use features)
   - System, Updates, Logs (operations)
   - Modules (depends on Phase 4; can stub)
   - Documentation (can use placeholder content initially)
4. **3d** (Real-time + Polish) – after pages exist

---

## Risks and Assumptions

- **Phase 4 dependencies**: Modules page may need stubs if Module Manager not ready; Updates/Logs may need stubs if those services deferred.
- **xterm.js**: Include locally (no CDN); verify license compatibility.
- **Charts**: Use lightweight library (e.g. Chart.js, lightweight-charts) or CSS-only where possible for RPi performance.
- **Assumption**: API gateway and Phase 2 services are running; WebSocket endpoints are available.

---

## Related Documents

- [Full Implementation Plan](full_implementation_plan_e49592f8.plan.md)
- [WEB-INTERFACE-SPECIFICATION](../../.planning/WEB-INTERFACE-SPECIFICATION.md)
- [API-REFERENCE](../../.planning/API-REFERENCE.md)
- [DOCUMENTATION-GUIDELINES](../../.planning/DOCUMENTATION-GUIDELINES.md)
- [NETWORK-MANAGEMENT-SPECIFICATION](../../.planning/NETWORK-MANAGEMENT-SPECIFICATION.md)
- [SERIAL-CONSOLE-SPECIFICATION](../../.planning/SERIAL-CONSOLE-SPECIFICATION.md)
- [PACKET-CAPTURE-SPECIFICATION](../../.planning/PACKET-CAPTURE-SPECIFICATION.md)

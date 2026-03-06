# Frontend UI Audit

**Scope:** All HTML under `web/`, CSS under `web/css/`, and related JS.  
**Inputs:** `web/css/base.css`, `web/css/theme.css`, `web/css/components.css`, `web/css/layout.css`.  
**Note:** `frontend.md` was not found at the repo root; audit is based on codebase inspection only.

---

## 1. CDN dependency scan

**Search performed:** Every HTML file under `web/` for:
- `<script src="http`
- `<link href="http`
- Strings: `cdn`, `cdnjs`, `jsdelivr`, `unpkg`, `googleapis` in any `src`/`href`

**Result:** **No CDN or external resource loading found.**

| File | Library | Version | CDN URL | Has local fallback? |
|------|---------|---------|---------|----------------------|
| *(none)* | — | — | — | — |

All `<script>` and `<link rel="stylesheet">` references are **local**:
- **CSS:** Relative paths like `css/base.css`, `css/theme.css`, … or absolute like `/css/base.css`, `/css/pages/advanced.css`, etc.
- **JS:** Relative like `js/pages/simple.js` or absolute like `/js/pages/advanced.js`, `/js/pages/serial.js`, and module paths like `/modules/syslog_receiver/module.js`.

The only occurrences of `http` in HTML are **prose** in docs (e.g. "http://192.168.50.1", "http_code") and curl examples—not resource loading.

**Conclusion:** The frontend is already offline-friendly from a CDN perspective; no vendoring of external scripts or styles is required for offline use.

---

## 2. xterm.js audit

**Search:** All HTML and JS under `web/` for "xterm" and related terminal/addon usage.

**Findings:**

- **No xterm.js library** is loaded anywhere. No `<script>` or `import` references to xterm, xterm.js, or xterm.css.
- **Serial console** is implemented with **custom DOM + CSS** in `web/js/pages/serial.js`:
  - Functions like `ensureTerminalLine`, `updateTerminalForSession`, `setupTerminalInputForSession` operate on a custom terminal buffer and a `.console-window` element.
  - Output is rendered as HTML with syntax highlighting (e.g. `.sh-prompt`, `.sh-error`, `.sh-command`) and a transparent overlay for input.
- **No FitAddon or other xterm addon** is used.
- **No xterm.css** is linked; styling is in `web/css/pages/serial.css` (e.g. `.console-window`, `.console-window-wrapper`, `.console-input-overlay`).

| Question | Answer |
|----------|--------|
| xterm.js loaded from CDN or locally? | **Not used.** |
| Version in use? | **N/A.** |
| Which pages load it? | **None.** |
| xterm CSS loaded? | **No.** |
| FitAddon or other addon? | **No.** |

**Conclusion:** The serial page uses a custom terminal UI, not xterm.js. No xterm-related changes or vendoring are required for this audit.

---

## 3. Icon library audit

**Search:** Font Awesome (`fa-`, `fas-`, `far-`, `fab-`), Material Icons, Heroicons, Feather, Lucide, `<i class="...">` icon patterns, SVG sprite usage.

**Results:**

- **No** Font Awesome, Material Icons, Heroicons, Feather, or Lucide class names or references.
- **No** `<i class="...">` icon elements found in `web/` HTML.
- **No** SVG sprite or `<use>`/symbol patterns found.

**Conclusion:** No third-party icon library is used. Icons are either absent or implemented via text/labels (e.g. "Menu", "Copy", "Show") or inline/basic HTML. No icon vendoring or replacement is required.

---

## 4. Per-page CSS class audit

### 4.1 CSS files linked in `<head>` by page

| Page | CSS links (order) | Inline `<style>` |
|------|-------------------|-------------------|
| **web/index.html** | base.css, theme.css, layout.css, components.css, pages/simple.css | None |
| **web/advanced/index.html** | base, theme, layout, components, pages/advanced.css, pages/dashboard.css | None |
| **web/advanced/network.html** | base, theme, layout, components, pages/advanced.css, pages/network.css | None |
| **web/advanced/serial.html** | base, theme, layout, components, pages/advanced.css, pages/serial.css | None |
| **web/advanced/capture.html** | base, theme, layout, components, pages/advanced.css, pages/capture.css | None |
| **web/advanced/snmp.html** | base, theme, layout, components, pages/advanced.css, pages/snmp.css | None |
| **web/advanced/syslog.html** | base, theme, layout, components, pages/advanced.css, pages/syslog.css | None |
| **web/advanced/fileshare.html** | base, theme, layout, components, pages/advanced.css, pages/fileshare.css | None |
| **web/advanced/system.html** | base, theme, layout, components, pages/advanced.css, pages/system.css | None |
| **web/advanced/updates.html** | base, theme, layout, components, pages/advanced.css, pages/updates.css | None |
| **web/advanced/modules.html** | base, theme, layout, components, pages/advanced.css, pages/modules.css | None |
| **web/advanced/logs.html** | base, theme, layout, components, pages/advanced.css, pages/logs.css | None |
| **web/advanced/docs.html** | base, theme, layout, components, pages/advanced.css, pages/docs.css | None |

**Note:** `web/docs/*.html` (e.g. `docs/index.html`, `docs/getting-started/quick-start.html`) are **content fragments** (no `<head>`, no CSS); they are loaded into `web/advanced/docs.html` and styled by the docs shell’s CSS.

**Difference:** `web/index.html` uses **relative** paths (`css/...`, `js/...`); all `web/advanced/*.html` use **absolute** paths (`/css/...`, `/js/...`). Order of core CSS (base → theme → layout → components) is consistent; only the last one or two files are page-specific.

**No inline `<style>` blocks** were found in any of these HTML files.

### 4.2 Sample of interactive elements (10) and component class usage

| Page | Element | Markup / classes | Uses defined component classes? |
|------|---------|-------------------|----------------------------------|
| index.html | Theme select | `<select id="theme-select" class="select">` | Yes (`.select`) |
| index.html | Switch to Advanced | `<button class="btn btn-secondary" id="switch-advanced">` | Yes (`.btn`, `.btn-secondary`) |
| index.html | Copy WiFi | `<button class="btn btn-ghost btn-copy" …>` | Yes (`.btn`, `.btn-ghost`) |
| index.html | Toggle password | `<button class="btn btn-ghost" id="toggle-wifi-password">` | Yes |
| advanced/index.html | Sidebar toggle | `<button class="btn btn-ghost" id="sidebar-toggle" …>` | Yes (`.btn`, `.btn-ghost`) |
| advanced/index.html | Theme select | `<select id="theme-select" class="select">` | Yes (`.select`) |
| advanced/index.html | Start new capture | `<a class="btn btn-secondary btn-sm" href="…">` | Yes (`.btn`, `.btn-secondary`, `.btn-sm`) |
| advanced/network.html | Tab buttons | `<button class="tab-button" data-tab-target="interfaces">` | Yes (`.tab-button` from components.css) |
| advanced/serial.html | Refresh | `<button class="btn btn-secondary btn-sm" id="refresh-serial">` | Yes |
| advanced/capture.html | Theme select | `<select id="theme-select" class="select">` | Yes (`.select`) |

**Conclusion:** Sampled buttons, selects, and tab controls consistently use the design system classes (`.btn`, `.btn-primary`/`.btn-secondary`/`.btn-ghost`, `.btn-sm`, `.select`, `.tab-button`, `.field`, `.field-label`). No ad-hoc inline styles or unrelated class names were found on these elements.

### 4.3 CSS load order consistency

- **index.html (simple):** base → theme → layout → components → **pages/simple.css**. No advanced.css.
- **All advanced/*.html:** base → theme → layout → components → **pages/advanced.css** → **pages/<page>.css**.

**Flag:** **web/advanced/fileshare.html** does **not** load `advanced.js`. It loads only `fileshare.js`, `theme.js`, `mode.js`, and `components.js`. As a result, **sidebar toggle (Menu)** and **theme selector** are not initialized on that page (advanced.js contains `setupSidebarControls()` and `initThemeSelector()`). CSS order is the same; the inconsistency is script loading, not CSS.

---

## 5. Navigation structure audit

**Location:** Nav lives in every `web/advanced/*.html` page (and `web/advanced/index.html`) as repeated markup; not a single shared file.

**Structure:**

- **Layout:** `app-shell` (grid) contains:
  - **Sidebar** (`<aside class="sidebar" id="sidebar">`): fixed width 240px (full height on desktop).
  - **Shell content** (`<div class="shell-content">`): **topbar** + **main**.
- **Sidebar contents:**
  - `sidebar-header`: brand (brand-mark "RPi", brand-title, brand-subtitle "Advanced Mode").
  - `sidebar-nav` (`<nav class="sidebar-nav" aria-label="Primary">`): links with `.nav-item`, `href` and `data-page` (dashboard, network, serial, capture, snmp, syslog, fileshare, system, updates, modules, logs, docs).
  - `sidebar-footer`: single button "Switch to Simple Mode" (`.btn`, `.btn-secondary`, `id="switch-simple"`).
- **Topbar:** `header.topbar` with:
  - **Menu button:** `<button class="btn btn-ghost" id="sidebar-toggle" aria-expanded="false" aria-controls="sidebar">Menu</button>`.
  - **Breadcrumb:** `<div class="breadcrumb" id="breadcrumb">` (text set by JS).
  - **Topbar actions:** theme `<label class="field theme-field">` and `<select id="theme-select" class="select">` (Light/Dark/Auto).

**Mobile / hamburger:** Yes. In `web/css/pages/advanced.css`, at `@media (max-width: 1023px)`:
- `.sidebar` is positioned off-canvas (`left: -260px`), transitions to `left: 0` when `.sidebar.is-open`.
- Toggle is the "Menu" button; `web/js/pages/advanced.js` implements `setupSidebarControls()`: click toggles `is-open`, sets `aria-expanded`, and click-outside closes the sidebar.

**JS controlling nav:** `web/js/pages/advanced.js`:
- `setActiveNav()`: sets `.nav-item.active` and breadcrumb text from current path.
- `setupSidebarControls()`: sidebar toggle and outside-click close.
- `setupModeSwitch()`: "Switch to Simple Mode" → confirm and redirect.

**Summary:** Sidebar + top nav; hamburger implemented via CSS (off-canvas) and advanced.js. **fileshare.html** does not load advanced.js, so its Menu and theme controls are non-functional on that page.

---

## 6. Responsive breakpoint audit

**All `@media` in `web/css`:**

| File | Breakpoint | What it controls |
|------|------------|-------------------|
| **theme.css** | `prefers-color-scheme: dark` | Dark theme variables for `[data-theme="auto"]` |
| **theme.css** | `prefers-reduced-motion: reduce` | Disables animations/transitions globally |
| **layout.css** | `min-width: 640px` | Container padding increase |
| **layout.css** | `min-width: 1024px` | Further container padding |
| **pages/simple.css** | `min-width: 768px` | Simple header row, connection grid 2-col, mode-switch row layout |
| **pages/advanced.css** | `max-width: 1023px` | App shell single column; sidebar off-canvas + `.is-open`; main padding |
| **pages/docs.css** | `max-width: 1023px` | Docs layout single column; sidebar/TOC static |

**Breakpoints in use:** 640px, 768px, 1023px, 1024px (plus preference queries).

**Files with no `@media` (no layout/visibility breakpoints):**

- **base.css** — reset/layout basics only.
- **components.css** — buttons, fields, modals, toasts, etc.; no breakpoints.
- **layout.css** — only container padding at 640/1024; grid classes (e.g. `.grid-2`) use `auto-fit`/`minmax` so they are fluid but not media-query-driven.
- **pages/dashboard.css**, **pages/network.css**, **pages/serial.css**, **pages/capture.css**, **pages/snmp.css**, **pages/syslog.css**, **pages/fileshare.css**, **pages/system.css**, **pages/updates.css**, **pages/modules.css**, **pages/logs.css** — no `@media` in any of these.

**Responsive gaps:**

1. **Serial page:** `.serial-split` is a flex row (device list + console). There is no breakpoint to stack or resize this on narrow viewports; small screens may get horizontal scroll or cramped columns. Relies only on app-shell sidebar behavior from advanced.css.
2. **Dashboard / panels:** Dashboard grid and panel layout are not adjusted by media queries; they depend on layout.css’s generic grid and advanced.css for the shell.
3. **Capture, Network, SNMP, etc.:** Forms and tables have no dedicated responsive rules; may overflow or feel tight on small screens.
4. **components.css:** Buttons, inputs, modals have no size/stacking rules at different widths (e.g. modal actions could wrap; already use flex-wrap in some places).

**Summary:** Core responsive behavior is in **theme.css** (preferences), **layout.css** (container), **simple.css** (768px), **advanced.css** (1023px sidebar/topbar), and **docs.css** (1023px). All other page CSS files have **no** responsive behavior; serial split layout and dense forms/tables are the main gaps.

---

## Offline blockers

**No CDN dependencies were found.** All scripts and styles are served from the same origin (local paths). Nothing needs to be vendored for the refactor purely to restore offline use.

If the project later adds:
- Any `<script src="https://...">` or `<link href="https://...">` for JS/CSS,
- Or references to cdnjs, jsdelivr, unpkg, googleapis, etc.,

those would need to be replaced with vendored assets and listed here as offline blockers. As of this audit, **the list is empty.**

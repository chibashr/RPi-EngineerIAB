# UI Refactor Plan

**Status:** DRAFT — awaiting confirmation before implementation.  
**Inputs:** `.claude/analysis/ui-audit.md`, `docs/CODEMAPS/frontend.md`, `web/css/base.css`, `web/css/theme.css`, `web/css/components.css`, `web/css/layout.css`.  
**Output:** This plan only. No code changes until approved.

---

## Summary

The audit found **no CDN dependencies** and **no xterm.js** (serial uses a custom DOM terminal). The refactor therefore focuses on: (1) confirming offline-first and documenting a vendoring process for future deps; (2) adding Tailwind and enforcing a single CSS load order; (3) filling design-system gaps in `components.css`; (4) standardizing mobile nav with new breakpoint and accessibility; (5) per-page HTML and script consistency; (6) terminal styling and optional future xterm alignment.

---

## 1. Vendor all CDN dependencies (offline-first, BLOCKING)

**Audit result:** No CDN or external script/stylesheet references exist. All resources are local.

**Plan:**

1. **No vendoring work** — Nothing to download or commit for existing code.
2. **Document the rule** — Add a short note to the plan or to a frontend doc: "All JS/CSS must be local (e.g. `web/vendor/<lib>/`). No `<script src="https://...">` or `<link href="https://...">` for runtime assets. If a library is added later, vendor it under `web/vendor/<library>/` and reference local paths."
3. **Optional:** Create `web/vendor/` directory with a README describing the vendoring process (priority order: xterm.js + addons, then icon libs, then other JS/CSS) so future additions are consistent.
4. **If xterm.js or an icon library is introduced later:** Follow the same process: download/build, commit under `web/vendor/<name>/`, update HTML/JS to use local paths only; remove any CDN fallback patterns.

**Deliverables:**

- No code changes for current CDN state.
- Optional: `web/vendor/README.md` (or equivalent) describing offline-first and vendoring steps.
- Checklist for future: (a) xterm.js + xterm.css + addons, (b) icon library, (c) other libs.

---

## 2. Add Tailwind CSS pre-built to vendor

**Goal:** Add Tailwind v3 full build as a vendored file and load it first in every HTML `<head>` so utilities are available for one-off layout without overriding component classes.

**Steps:**

1. **Obtain Tailwind v3 pre-built full CSS** (~3.8MB). Source: official Tailwind v3 full build (e.g. from Tailwind releases or documented CDN build), saved as a single file.
2. **Commit as:** `web/vendor/tailwind/tailwind.min.css` (or `tailwind.css` if unminified).
3. **Define canonical CSS load order** for every HTML page that has a `<head>`:

   | Order | File | Purpose |
   |-------|------|--------|
   | 1 | `web/vendor/tailwind/tailwind.min.css` | Tailwind utilities (load first) |
   | 2 | `web/css/theme.css` | CSS custom properties (tokens) |
   | 3 | `web/css/base.css` | Resets and base |
   | 4 | `web/css/layout.css` | Grid and container |
   | 5 | `web/css/components.css` | Named component classes |
   | 6 | Page-specific CSS (e.g. `pages/simple.css`, `pages/advanced.css`, `pages/<page>.css`) | Loads last, highest priority |

   This order ensures component classes override Tailwind utilities on named components; Tailwind remains available for ad-hoc layout in HTML.

4. **Update all HTML files** that currently link CSS:
   - **web/index.html** — Use relative paths: `vendor/tailwind/tailwind.min.css`, then `css/theme.css`, `css/base.css`, `css/layout.css`, `css/components.css`, `css/pages/simple.css`.
   - **web/advanced/*.html** (index, network, serial, capture, snmp, syslog, fileshare, system, updates, modules, logs, docs) — Use absolute paths: `/vendor/tailwind/tailwind.min.css`, then `/css/theme.css`, `/css/base.css`, `/css/layout.css`, `/css/components.css`, then `/css/pages/advanced.css`, then `/css/pages/<page>.css` where applicable.

5. **Do not** change the order of theme/base/layout/components relative to each other beyond inserting Tailwind at position 1.

**Deliverables:**

- `web/vendor/tailwind/tailwind.min.css` present and committed.
- Every relevant HTML `<head>` uses the 6-step order above; no page loads Tailwind in a different position.

---

## 3. Design system gaps in components.css

**Goal:** Add missing component classes and tokens so all pages can use a single design system. No removal of existing behavior until migration is done.

**3a) Navigation component classes**

- Add to `web/css/components.css`:
  - **.nav-sidebar** — Sidebar container (visual and layout; can align with current `.sidebar` behavior).
  - **.nav-item** — Single nav link (already in `pages/advanced.css`; move or duplicate into components and have advanced.css depend on it or remove duplicate).
  - **.nav-item-active** — Active state (replace or alias `.nav-item.active` for consistency).
  - **.nav-section-label** — Optional section heading inside nav.
  - **.nav-mobile-toggle** — Hamburger button (replaces or aliases current sidebar-toggle for semantics).
  - **.nav-overlay** — Mobile backdrop (full-screen overlay that closes sidebar on click).

- **Migration:** Update `web/css/pages/advanced.css` to use these class names where appropriate, or import/override from components so that existing HTML can be updated to use `.nav-sidebar`, `.nav-mobile-toggle`, `.nav-overlay` without breaking layout. Existing `.sidebar`, `.sidebar-nav`, `.nav-item` can be kept as aliases initially, then phased to the new names in HTML in step 5.

**3b) Table classes**

- Add to `components.css`:
  - **.table-container** — Wrapper with overflow (e.g. `overflow-x: auto`) for horizontal scroll.
  - **.table** — Base table (border-collapse, width, etc.).
  - **.table th**, **.table td** — Consistent cell padding and alignment.
  - **.table-row-hover** — Row hover state (e.g. background change).
  - **.table-empty** — Empty state row (e.g. centered text, colspan).

**3c) Form group patterns**

- Add to `components.css`:
  - **.form-row** — Horizontal label + input pair (e.g. flex row).
  - **.form-section** — Grouped fields with a heading.
  - **.input-group** — Input with inline button (e.g. input + "Copy").
  - **.input-prefix**, **.input-suffix** — Slots for icons/text inside input (e.g. for future icons).
  - **.checkbox**, **.radio** — Styled checkbox/radio (replace native appearance where needed).
  - **.toggle** — iOS-style toggle switch (for boolean settings).

**3d) Consistent focus ring**

- In `components.css` (or `base.css` if preferred for global scope), add:
  - **Global:** `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }`
- Remove or reduce **duplicate** per-component `:focus-visible` / `:focus` rules in `components.css` (e.g. on `.btn`, `.select`, `.input`, `.modal-input`) so the global rule applies unless a component explicitly needs a different ring. Prefer one canonical focus style.

**3e) Terminal area**

- Add to `components.css`:
  - **.terminal-container** — Wraps the terminal instance (custom DOM or future xterm.js).
  - **.terminal-toolbar** — Bar above terminal (baud/port controls).
  - **.terminal-status** — Connection status bar below or beside terminal.
- Ensure any terminal background/foreground use `var(--color-bg)` and `var(--color-fg)` (or tokens that theme.css defines) so dark/light theme applies. Current serial page uses `.console-window` in `serial.css`; these new classes can be applied to the same structure or used when migrating.

**3f) Empty states**

- Add **.empty-state** — Centered message for empty tables/lists (e.g. "No data"). Reuse or replace existing `.empty-state` in `serial.css` if present; ensure it lives in `components.css` for reuse.

**3g) Loading states**

- Add to `components.css`:
  - **.loading-overlay** — Full-card overlay with spinner (e.g. position absolute, centered).
  - **.spinner** — CSS-only spinner (no image/SVG dependency; e.g. border-based animation).

**3h) surface-muted token**

- **theme.css:** Add `--color-surface-muted` in `:root` and in `[data-theme="dark"]`, and in the `@media (prefers-color-scheme: dark)` block for `[data-theme="auto"]`. Choose values that fit the existing palette (e.g. slightly muted surface for read-only areas).
- **components.css** and **network.css** already reference `var(--color-surface-muted)` (modal-value, network panels); after adding the token, no further change needed there.

**Deliverables:**

- All of the above classes and token added; duplicate focus rules reduced to a single canonical pattern.
- No breaking change to existing pages until step 5 (per-page HTML audit) migrates markup to new table/form/nav classes where applicable.

---

## 4. Mobile navigation implementation

**Goal:** Hamburger menu that collapses the sidebar below 768px, with overlay, ESC, and focus trap; sidebar not persisted (closed on load on mobile).

**4.1 HTML pattern**

- **Hamburger button:**  
  `<button class="nav-mobile-toggle" aria-label="Open menu" aria-expanded="false" aria-controls="sidebar">`  
  Content: **inline hamburger SVG** (three lines), no external icon library.
- **Sidebar:**  
  `<nav id="sidebar" class="nav-sidebar" aria-hidden="true">` (or keep `<aside>` with role="navigation" if preferred; ensure `id="sidebar"` and class `.nav-sidebar` for styling).
- **Overlay:**  
  `<div class="nav-overlay" aria-hidden="true"></div>` (positioned fixed, full viewport; visible only when sidebar open on mobile).

**4.2 Behavior (JS)**

- Implement in **web/js/pages/advanced.js** (or a new **web/js/nav.js** that advanced.js imports):
  - Toggle **aria-expanded** on the hamburger button when opening/closing.
  - Toggle **aria-hidden** on sidebar and overlay (e.g. `false` when open, `true` when closed).
  - **Click overlay** → close sidebar and update aria states.
  - **ESC key** → close sidebar and update aria states (keydown listener).
  - **Focus trap:** When sidebar is open (mobile), trap focus inside sidebar (e.g. first/last focusable, Tab cycles within sidebar). When closed, restore focus to the toggle button. Use a small helper or inline logic; no new framework.
  - **State:** Sidebar open/closed state is **not** persisted (e.g. no localStorage). On every page load, sidebar starts closed on mobile.

**4.3 Breakpoints (CSS)**

- **&lt; 768px:**  
  Sidebar hidden by default (e.g. off-canvas or display none). Hamburger (`.nav-mobile-toggle`) visible. Clicking hamburger shows sidebar as overlay; `.nav-overlay` visible. Sidebar slides in (e.g. transform or left).
- **≥ 768px:**  
  Sidebar always visible (e.g. in flow or fixed). Hamburger hidden. No overlay. Existing desktop layout unchanged.

**4.4 Alignment with current code**

- Current breakpoint in `advanced.css` is **1023px**. **Change to 768px** for this refactor so mobile nav behavior applies from 768px down. Update `pages/advanced.css` media query from `max-width: 1023px` to `max-width: 767px` (or `max-width: 768px` if design prefers 768 as breakpoint). Ensure docs layout (`docs.css`) remains consistent (either keep 1023px for docs or align to 768px; recommend keeping 1023px for docs layout unless product decision is to match).
- Ensure **fileshare.html** loads **advanced.js** (or the new nav.js) so that sidebar toggle and theme selector work on that page (see audit flag).

**Deliverables:**

- Inline hamburger SVG in every advanced page (or in a shared snippet/template if one is introduced).
- `.nav-mobile-toggle`, `.nav-overlay` in use; `.nav-sidebar` (or equivalent) styled in components/advanced.
- JS: open/close, overlay click, ESC, focus trap, no persistence.
- CSS: 768px breakpoint for advanced shell; hamburger visible &lt; 768px, sidebar visible ≥ 768px.

---

## 5. Per-page HTML audit and standardization

**Goal:** Every HTML page under `web/` (index + advanced/*) uses design-system classes and correct CSS/script order; no ad-hoc styling or duplicate styles.

**Pages in scope (from audit):**

- web/index.html  
- web/advanced/index.html  
- web/advanced/network.html  
- web/advanced/serial.html  
- web/advanced/capture.html  
- web/advanced/snmp.html  
- web/advanced/syslog.html  
- web/advanced/fileshare.html  
- web/advanced/system.html  
- web/advanced/updates.html  
- web/advanced/modules.html  
- web/advanced/logs.html  
- web/advanced/docs.html  

**Per page:**

1. **Buttons** — Replace any ad-hoc button styling with `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-sm` as appropriate.
2. **Selects** — Use `.select` on `<select>` elements.
3. **Inputs** — Use `.input` on text-like `<input>` elements.
4. **Labels** — Wrap label + input (or select) in `.field`; use `.field-label` for the label.
5. **Tables** — Wrap `<table>` in `.table-container`; add `.table` to the table; use `.table-empty` for empty state rows where applicable; ensure `th`/`td` are styled via `.table th`, `.table td` (or existing status-table if kept, but prefer design-system names where possible).
6. **Remove** any `<style>` blocks that duplicate component or layout rules (audit found none; verify again during implementation).
7. **CSS load order** — Already defined in step 2; verify each page has the exact order (Tailwind → theme → base → layout → components → page-specific).
8. **Scripts:** Ensure **web/advanced/fileshare.html** loads **advanced.js** (in addition to fileshare.js, theme, mode, components) so sidebar toggle and theme selector work. Normalize script order across advanced pages if needed (e.g. advanced.js first, then page script).

**Deliverables:**

- All listed pages updated; no ad-hoc button/input/table styling; correct CSS and script order; fileshare.html fixed for nav/theme.

---

## 6. xterm.js / terminal standardization

**Audit result:** The serial console does **not** use xterm.js. It uses a custom DOM implementation (`.console-window`, overlay input, syntax highlighting in `serial.js`).

**Plan:**

**Option A (recommended for this refactor):**  
- **Do not introduce xterm.js** in this phase.  
- Apply **design-system terminal classes** to the existing custom terminal: wrap the existing console UI in **.terminal-container**; add **.terminal-toolbar** for the baud/port controls above the console; add **.terminal-status** for the connection status.  
- Ensure the existing `.console-window` (or equivalent) uses theme tokens (`--color-bg`, `--color-fg`) so dark/light theme is consistent.  
- No FitAddon or ResizeObserver required for the current custom implementation unless the product decides to add a true terminal instance later.

**Option B (if xterm.js is introduced in a later phase):**  
- Vendor xterm.js + xterm.css (and FitAddon if needed) under `web/vendor/xterm/`.  
- Load xterm.css in the serial page (local path only).  
- Wrap each xterm instance in `.terminal-container`; add `.terminal-toolbar` and `.terminal-status`.  
- Configure the Terminal theme via options using `getComputedStyle` to read `--color-bg` / `--color-fg` (or equivalent).  
- Use FitAddon with ResizeObserver on the container for window resize.  

**Deliverables for this refactor:**

- Option A: Serial page markup and serial.css updated to use `.terminal-container`, `.terminal-toolbar`, `.terminal-status`; theme tokens applied to existing console area; no xterm.js.  
- If Option B is deferred: Document in plan or frontend doc that future xterm.js adoption must follow Option B steps and vendor under `web/vendor/xterm/`.

---

## Risk assessment

| Risk | Level | Mitigation |
|------|--------|------------|
| CDN vendoring | HIGH (if libs were present) | Audit shows none; only process/doc added. If a future lib cannot be self-hosted (license), choose an alternative or get permission. |
| Tailwind + existing CSS conflicts | MEDIUM | Enforce strict load order: Tailwind first, then theme/base/layout/components, then page. Component classes will override utilities. Test key pages after change. |
| Mobile nav focus trap / a11y | MEDIUM | Implement focus trap and ESC; test with keyboard and one screen reader if possible. Keep logic in one place (advanced.js or nav.js). |
| CSS token (surface-muted) | LOW | Add variable in theme.css only; existing usages already reference it. |
| Per-page HTML standardization | LOW | Mechanical replacement and fileshare script fix; audit already shows most pages use component classes. |

---

## Implementation order (recommended)

1. **Theme token** — Add `--color-surface-muted` to theme.css (unblocks components that reference it).
2. **Design system (components.css)** — Add nav, table, form, focus, terminal, empty, loading classes and global focus-visible.
3. **Tailwind** — Add vendor file; update CSS load order in all HTML (Tailwind first, then theme → base → layout → components → page).
4. **Mobile nav** — Add nav classes and overlay; implement 768px breakpoint; add hamburger SVG and JS (toggle, overlay, ESC, focus trap); fix fileshare.html to load advanced.js.
5. **Per-page HTML** — Replace ad-hoc styling with component classes; wrap tables; ensure `.field`/`.select`/`.input`; verify script order.
6. **Terminal (Option A)** — Apply `.terminal-container`, `.terminal-toolbar`, `.terminal-status` to serial page; align colors with theme tokens.
7. **Optional** — Add `web/vendor/README.md` and any future-xterm/icon vendoring checklist.

---

## Sign-off

**Plan saved to:** `.claude/plan/ui-refactor.md`  
**No code has been written.** Awaiting confirmation before implementation.

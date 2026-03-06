# Vendored frontend dependencies

All JS/CSS used by the web UI is served from this directory so the app works **fully offline**. No `<script src="https://...">` or `<link href="https://...">` for runtime assets.

## Layout

- **tailwind/** — Tailwind CSS v3 (pre-built from project content). Load first in every page `<head>`.
- **xterm/** — xterm.js and addons for terminal UIs (e.g. serial). Not yet used by the serial page (custom DOM); ready for future use.

## Adding a new library

1. Download or build the asset(s) (e.g. from GitHub releases or npm/CDN).
2. Place under `web/vendor/<name>/` (and `addons/` if needed).
3. Add `web/vendor/<name>/VERSION.txt` with the version.
4. Update HTML/JS to reference only local paths (e.g. `/vendor/<name>/file.js`).
5. Do not add CDN fallbacks or `onerror` loaders that hit the network.

## Binary handling

`.gitattributes` marks `web/vendor/**/*.min.css` and `web/vendor/**/*.min.js` as binary to avoid line-ending churn.

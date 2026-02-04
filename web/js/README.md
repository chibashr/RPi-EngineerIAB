# Frontend scripts

## modal.js

In-page modals replace browser `prompt()` / `confirm()` so all user input happens inside the app.

- **`modalConfirm(message)`** → `Promise<boolean>` — OK/Cancel dialog.
- **`modalPrompt(message, defaultValue, options?)`** → `Promise<string|null>` — Single text input; optional `{ label }`.
- **`modalForm(fields, title)`** → `Promise<Record<string, string>|null>` — Multi-field form. `fields`: `{ name, label, default?, type?, placeholder? }[]`.

The modal container is created on first use. Esc closes the dialog; focus is trapped inside while open. Styles live in `web/css/components.css` (`.modal-container`, `.modal-overlay`, `.modal-dialog`, etc.).

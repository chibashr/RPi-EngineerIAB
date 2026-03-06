# Logging Audit Report

**Date:** 2026-03-06  
**Scope:** services/, modules/, lib/module_logger.py, routes, websockets, logs API, env vars

---

## Task A — Logger Adoption Scan

### Search Results

Searched `services/` and `modules/` for:
- `get_service_logger` / `get_module_logger` / `logging.getLogger` / `print(`

**Findings:**
- **No** `logging.getLogger(__name__)` bypasses in services/ or modules/
- **No** bare `print()` calls in services/ or modules/
- All services and modules that use logging import from `lib.module_logger`

### Logger Adoption Table

| File | Logger type | Compliant | Issues |
|------|-------------|-----------|--------|
| **Services** | | | |
| services/api_gateway/main.py | get_service_logger | Yes | None |
| services/api_gateway/websockets.py | get_service_logger | Yes | None |
| services/api_gateway/routes/backup.py | get_service_logger | Yes | None |
| services/api_gateway/routes/capture.py | get_service_logger | Yes | None |
| services/api_gateway/routes/logs.py | get_service_logger | Yes | None |
| services/api_gateway/routes/modules.py | get_service_logger | Yes | None |
| services/api_gateway/routes/network.py | get_service_logger | Yes | None |
| services/api_gateway/routes/remote.py | none | Partial | No logger; no logging in handlers |
| services/api_gateway/routes/serial.py | get_service_logger | Yes | None |
| services/api_gateway/routes/system.py | get_service_logger | Yes | None |
| services/api_gateway/routes/updates.py | get_service_logger | Yes | None |
| services/capture_manager/manager.py | get_service_logger | Yes | None |
| services/logging_service/manager.py | get_service_logger | Yes | Only in _daemon_main(); main class has no logger |
| services/module_manager/manager.py | get_service_logger | Yes | None |
| services/monitor_service/manager.py | get_service_logger | Yes | None |
| services/network_manager/manager.py | get_service_logger | Yes | None |
| services/remote_access_manager/manager.py | get_service_logger | Yes | None |
| services/serial_manager/manager.py | get_service_logger | Yes | None |
| services/system_manager/manager.py | get_service_logger | Yes | None |
| services/update_manager/manager.py | get_service_logger | Yes | None |
| services/update_manager/_backup.py | get_service_logger | Yes | None |
| services/update_manager/_version.py | get_service_logger | Yes | None |
| **Modules** | | | |
| modules/example_module/main.py | get_module_logger | Yes | None |
| modules/example_module/api.py | none | Partial | No logger; minimal API |
| modules/file_share/main.py | get_module_logger | Yes | None |
| modules/file_share/api.py | get_module_logger | Yes | None |
| modules/file_share/user_store.py | none | Partial | No logger; data store only |
| modules/file_share/server_ftp.py | none | Partial | No logger |
| modules/file_share/server_sftp.py | (not scanned) | — | — |
| modules/syslog_receiver/receiver.py | get_module_logger | Yes | None |
| modules/syslog_receiver/api.py | none | Partial | No logger; delegates to receiver |
| modules/syslog_receiver/main.py | none | Partial | Lifecycle only; no logging |
| modules/snmp_trap_receiver/receiver.py | get_module_logger | Yes | None |
| modules/snmp_trap_receiver/api.py | none | Partial | No logger; delegates to receiver |
| modules/snmp_trap_receiver/main.py | none | Partial | Lifecycle only; no logging |

---

## Task B — Route Handler Logging Scan

### Request Logging (Before/After Hooks)

- **No** before-request or after-request middleware for HTTP request logging
- **No** global request/response logging (method, path, status, duration)
- SecurityHeadersMiddleware and CORSMiddleware exist; no logging middleware

### Logger Instantiation

All route files that perform non-trivial work use `get_service_logger(__name__)`:
- backup, capture, logs, modules, network, serial, system, updates

**Exception:** `routes/remote.py` — no logger, no log calls

### Explicit Log Calls

| Route file | Success path logging | Error path logging |
|------------|----------------------|--------------------|
| backup.py | No | Yes (warning, exception) |
| capture.py | Yes (info) | Yes (warning, exception, debug) |
| logs.py | Yes (info for export) | Yes (warning, exception) |
| modules.py | Yes (info) | Yes (warning, error, exception) |
| network.py | Yes (info) | Yes (warning, error, exception) |
| remote.py | No | No |
| serial.py | Yes (info) | Yes (warning, error) |
| system.py | Yes (info) | Yes (warning, error, exception) |
| updates.py | No | Yes (exception) |

**Baseline:** No per-request access logging (method, path, status, duration). Error and key-action logging exists in most route handlers.

---

## Task C — WebSocket Handler Logging Scan

**File:** `services/api_gateway/websockets.py`

### Connect/Disconnect Events

- **Connect:** Not logged. `await websocket.accept()` has no surrounding log.
- **Disconnect:** Not explicitly logged. `WebSocketDisconnect` is caught and `break`/`pass`; no log for normal disconnect.

### Errors

- **Status stream:** `logger.debug("Status WebSocket closed: %s", exc)` on exception (line 120)
- **Serial console:** `logger.warning("Serial open failed %s: %s", session_id[:8], exc)` (line 155); `logger.debug` for reader/writer errors (lines 175, 215)
- **Updates apply:** `logger.debug("Updates apply WebSocket closed: %s", exc)` (line 300)
- **Capture stream:** `logger.debug("Capture stream WebSocket closed: %s", exc)` (line 351)

### Per-Message Logging

- **None.** No logging of individual WebSocket messages (ping/pong, data, control, etc.).

**Summary:** Errors are logged at debug/warning. Connect/disconnect and per-message logging are absent.

---

## Task D — /api/v1/logs/system Endpoint Audit

### Handler

**File:** `services/api_gateway/routes/logs.py`  
**Function:** `list_system_logs(file, tail, level, search, service)`

### Behavior

1. **No `file` param:** Calls `logging_service.list_logs()` → returns `{"files": [...]}`
2. **`file=all`:** Calls `logging_service.read_all_logs(...)` → merged, sorted lines from all `*.log` files
3. **`file=<name>`:** Calls `logging_service.read_log(file, ...)` → lines from that file

### Data Source

- **File-based.** Reads from `RPI_ENGINEER_LOG_DIR` (default `/var/log/rpi-engineer`) or `repo_root/logs` fallback
- **Not** journald
- **Not** in-memory buffer

### Response Format

Wrapped by `success_response(payload)` → `{"data": payload, "meta": {"timestamp": "..."}}`

**Schema:**

- **List mode (no file):** `{"data": {"files": [{"name": str, "size": int, "modified": str}]}}`
- **Content mode (file or all):** `{"data": {"file": str, "tail": int, "lines": [str], "filters": {...}}}`

`lines` is an array of plain-text log lines (strings).

### Frontend Expectations

**File:** `web/js/pages/logs.js`

- `loadLogs()`: `GET /api/v1/logs/system` → `extractData(payload)` → `data.files` for dropdown
- `loadLogContent()`: `GET /api/v1/logs/system?file=...&tail=...&level=...&service=...&search=...` → `data.lines` for display

**extractData** (from `api.js`): `return payload.data ?? payload`

**Expected shape (critical):**
- List: `{ files: [{ name, size, modified }] }`
- Content: `{ file, tail, lines: string[], filters }`

**Display:** `renderLogContent(data.lines || [])` joins `lines` with `"\n"` and sets `textContent`.

**Conclusion:** Do not change the response schema. The frontend expects `data.files` and `data.lines` as documented above.

---

## Task E — Env Var Audit

### RPI_ENGINEER_LOG_DIR

| Location | Documented/Set |
|----------|----------------|
| lib/module_logger.py | Used (default `/var/log/rpi-engineer`) |
| services/logging_service/manager.py | Used (same default) |
| docs/ENV.md | **Not documented** |
| bin/install.sh | **Not set** for services. Script uses `LOG_DIR="/var/log/rpi-engineer"` for `mkdir`/`chown` but does not pass it as env to systemd units. Python code falls back to default path. |

### RPI_ENGINEER_DEBUG

| Location | Used |
|----------|------|
| docs/ENV.md | Documented (0/1, default 0) |
| .planning/DEVELOPMENT-GUIDE.md | Mentioned |
| Python codebase | **Not used** for log level or any behavior |

### RPI_ENGINEER_ENV

| Location | Used |
|----------|------|
| docs/ENV.md | Documented (e.g. development) |
| .planning/DEVELOPMENT-GUIDE.md | Mentioned |
| Python codebase | **Not used** for dev vs prod behavior |

### Other Log-Related Env Vars

- **RPI_ENGINEER_LOG_EXPORT_DIR** — used by logging_service (default `/var/lib/rpi-engineer/exports`)
- **RPI_ENGINEER_LOG_ROTATE_INTERVAL** — used by daemon (default 3600)
- **RPI_ENGINEER_LOG_MAX_SIZE_MB** — used by daemon (default 10)
- **RPI_ENGINEER_LOG_RETAIN_DAYS** — used by daemon (default 7)

These are used in code but **not** listed in docs/ENV.md.

---

## Gaps to Address

1. **RPI_ENGINEER_LOG_DIR**
   - Add to docs/ENV.md
   - Optionally set in systemd units (e.g. `Environment=RPI_ENGINEER_LOG_DIR=/var/log/rpi-engineer`) so install path is explicit

2. **RPI_ENGINEER_DEBUG**
   - Either wire it to log level (e.g. DEBUG when 1) in `lib/module_logger.py`, or remove from docs if unused

3. **RPI_ENGINEER_ENV**
   - Either use for dev vs prod (e.g. log level, console vs file) or remove from docs

4. **Log-related env vars**
   - Document in docs/ENV.md: RPI_ENGINEER_LOG_DIR, RPI_ENGINEER_LOG_EXPORT_DIR, RPI_ENGINEER_LOG_ROTATE_INTERVAL, RPI_ENGINEER_LOG_MAX_SIZE_MB, RPI_ENGINEER_LOG_RETAIN_DAYS

5. **Request logging**
   - No HTTP access logging (method, path, status, duration). Add middleware if needed for ops/debugging.

6. **WebSocket logging**
   - No connect/disconnect logging. Consider INFO for connect/disconnect and session_id where relevant.
   - Per-message logging is intentionally absent; keep as-is unless required.

7. **routes/remote.py**
   - Add `get_service_logger` and log errors if handlers can fail.

8. **Module API routes**
   - example_module/api.py, syslog_receiver/api.py, snmp_trap_receiver/api.py have no logger. Low risk if they delegate to receivers that log; add logger if they need their own error logging.

9. **file_share submodules**
   - user_store.py, server_ftp.py, server_sftp.py have no logger. Add if they need operational/error logging.

10. **/api/v1/logs/system**
    - Preserve response schema: `{ data: { files | file, tail, lines, filters } }` so the frontend continues to work.

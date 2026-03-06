# Logging Enhancements Plan

**Date:** 2026-03-06  
**Status:** DRAFT — awaiting confirmation  
**Scope:** lib/module_logger.py, request middleware, WebSocket logging, manager events, logs API

---

## Overview

Enhance logging across the RPi Engineer-in-a-Box codebase without breaking existing callers. All changes are additive or drop-in compatible unless explicitly noted.

**Reference:** `.claude/analysis/logging-audit.md` — baseline and frontend contract for `/api/v1/logs/system`.

---

## Phase 1: lib/module_logger.py Enhancements

**File:** `lib/module_logger.py`  
**Constraint:** `get_service_logger()` and `get_module_logger()` signatures must not change. All current callers continue working without modification.

### 1a) Rotating File Handler

| Item | Value |
|------|-------|
| Change | Replace `logging.FileHandler` with `logging.handlers.RotatingFileHandler` |
| maxBytes | `10 * 1024 * 1024` (10 MB) |
| backupCount | 5 |
| Effect | Each service keeps up to 50 MB of logs (10 MB × 5 rotated files) |
| Risk | LOW — drop-in replacement |

**Implementation notes:**
- Import: `from logging.handlers import RotatingFileHandler`
- Use same `log_path`, `encoding="utf-8"` as current FileHandler
- Fallback path (OSError/PermissionError) remains: StreamHandler to console

### 1b) Stdout Handler (Always On)

| Item | Value |
|------|-------|
| Change | Add `logging.StreamHandler(sys.stdout)` in addition to file handler |
| Placement | Both handlers active simultaneously; do not replace file handler |
| Formatter | Same `ModuleFormatter` (or `JSONFormatter` when active) as file handler |
| Effect | systemd captures stdout to journald automatically |
| Risk | LOW — additive |

**Implementation notes:**
- Add handler after file handler in `_get_app_logger()`
- When file handler fails (fallback path), current code already uses StreamHandler; ensure we don’t double-add
- Order: file handler first, then stdout handler

### 1c) Log Level from Environment

| Item | Value |
|------|-------|
| Env var | `RPI_ENGINEER_LOG_LEVEL` |
| Default | `INFO` |
| Valid values | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| Scope | Applied to both file and stdout handlers (and logger’s `setLevel`) |
| Risk | LOW |

**Implementation notes:**
- Parse once per logger setup; invalid value → fallback to INFO
- `logger.setLevel(parsed_level)` and `handler.setLevel(parsed_level)` for both handlers

### 1d) JSON Format Mode for Production

| Item | Value |
|------|-------|
| Trigger | `RPI_ENGINEER_ENV=production` OR `RPI_ENGINEER_LOG_FORMAT=json` |
| Default (dev) | Plain text via `ModuleFormatter` — unchanged behavior |
| New class | `JSONFormatter` alongside `ModuleFormatter` |
| Output | One JSON object per line (JSONL-style) |

**JSON schema per record:**
```json
{
  "timestamp": "2026-03-06T14:30:00.123Z",
  "level": "INFO",
  "service": "network_manager",
  "message": "...",
  "exc_info": null
}
```

- `exc_info`: `null` when no exception; string (formatted traceback) when present
- `service` maps to `display_name` (module_name or service_name)

**Implementation notes:**
- Add `JSONFormatter(display_name)` class
- In `_get_app_logger()`, choose formatter based on env before creating handlers
- Dev default: `ModuleFormatter` (no behavior change for existing deployments)

### 1e) Add get_api_logger()

| Item | Value |
|------|-------|
| Function | `get_api_logger(module_path: str, log_file: Optional[str] = None) -> logging.Logger` |
| Signature | Same pattern as `get_service_logger` |
| Log file | `api_gateway.log` (or override via `log_file`) |
| Use case | Request logging middleware |
| Risk | LOW — new function, no impact on existing code |

**Implementation notes:**
- Can be implemented as `get_service_logger("services.api_gateway.main", "api_gateway.log")` or a dedicated helper that ensures api_gateway.log
- If routes/websockets already use `get_service_logger(__name__)`, they map to `api_gateway` per `_get_service_name`. The middleware may need a dedicated logger to avoid handler duplication — use `get_api_logger(__name__)` which writes to `api_gateway.log`

---

## Phase 2: FastAPI Request Logging Middleware

**New file:** `services/api_gateway/middleware/request_logger.py`

### Middleware Class

| Item | Value |
|------|-------|
| Base | `BaseHTTPMiddleware` (Starlette) or `Middleware` with `dispatch` pattern |
| Logger | `get_api_logger(__name__)` |
| Captures | method, path, status_code, duration_ms |

### Log Format

**Plain text (ModuleFormatter):**
```
2026-03-06 14:30:00,123 INFO [api_gateway] POST /api/v1/serial/sessions 201 45ms
```

**JSON (JSONFormatter):**
```json
{"timestamp":"2026-03-06T14:30:00.123Z","level":"INFO","service":"api_gateway","type":"request","method":"POST","path":"/api/v1/serial/sessions","status":201,"duration_ms":45}
```

### Log Level by Status

| Status range | Level |
|--------------|-------|
| 2xx, 3xx | INFO |
| 4xx | WARNING |
| 5xx | ERROR |

### Exclusions

| Path pattern | Reason |
|--------------|--------|
| `/health` | Too noisy |
| Static files under `/` (e.g. `/`, `/advanced/`, `/index.html`, `/css/...`) | High volume |
| `/modules/<id>/<path>` | Static module assets |

### Inclusions

| Path pattern |
|--------------|
| All `/api/v1/*` |
| All `/ws/*` |

**Implementation notes:**
- Use `request.url.path` to match; exclude when `path == "/health"` or `path.startswith("/")` and not `path.startswith("/api/")` and not `path.startswith("/ws/")` — refine as needed for static vs API
- Record start time before `call_next`, compute duration after
- On exception in handler, status may be 500; ensure middleware catches and logs
- Register: `app.add_middleware(RequestLoggerMiddleware)` — order matters: add after CORS, before SecurityHeaders (or per FastAPI middleware stack)

### Package Structure

Create `services/api_gateway/middleware/` with:
- `__init__.py` (export `RequestLoggerMiddleware`)
- `request_logger.py` (middleware class)

**Registration in main.py:**
```python
from services.api_gateway.middleware import RequestLoggerMiddleware
app.add_middleware(RequestLoggerMiddleware)
```

**Risk:** MEDIUM — must not affect response timing; must handle handler exceptions without breaking response

---

## Phase 3: WebSocket Event Logging

**File:** `services/api_gateway/websockets.py`  
**Existing:** `logger = get_service_logger(__name__)` — keep as-is

### Events to Log

| Event | Level | Message pattern |
|-------|-------|-----------------|
| Connect | INFO | `WS connect path=%s client=%s` |
| Disconnect | INFO | `WS disconnect path=%s client=%s duration_s=%.1f` |
| Error/exception | ERROR | `WS error path=%s error=%s` (with `exc_info=True`) |
| Session summary (on disconnect) | INFO | `WS session summary path=%s messages_rx=%d messages_tx=%d` |

### Implementation Notes

- **path:** e.g. `/ws/status`, `/ws/serial/{session_id}`, `/ws/updates/apply`, `/ws/capture/{id}`
- **client:** `websocket.client.host` or similar; handle missing
- **duration_s:** Time from accept to disconnect
- **messages_rx/tx:** Count messages; requires per-connection counters

**Per-WebSocket handlers:**
1. **status_stream:** path=`/ws/status`; no rx/tx (server pushes only) — duration only
2. **serial_console:** path=`/ws/serial/{session_id}`; track rx/tx in reader/writer
3. **updates_apply_stream:** path=`/ws/updates/apply`; track progress messages
4. **capture_stream:** path=`/ws/capture/{id}`; track packet messages

**Risk:** LOW — additive only

---

## Phase 4: Manager-Level Event Logging

**Reference:** Audit Task A — all managers already use `get_service_logger`. This phase ensures key domain events are logged.

### serial_manager

| Event | Level | When |
|-------|-------|------|
| Device connect | INFO | When device detected/added |
| Device disconnect | INFO | When device removed |
| Session start | INFO | Session created, device_id |
| Session stop | INFO | Session released |
| Errors | ERROR/WARNING | Open failure, read/write errors |

### capture_manager

| Event | Level | When |
|-------|-------|------|
| Capture start | INFO | interface, filter |
| Capture stop | INFO | capture_id, packet count |
| Errors | ERROR | Start/stop failures |

### network_manager

| Event | Level | When |
|-------|-------|------|
| Interface up/down | INFO | State change |
| Profile load | INFO | profile name |
| Hotspot start/stop | INFO | SSID, state |

### system_manager

| Event | Level | When |
|-------|-------|------|
| Service restart | INFO | service name |
| Power command | INFO | action (reboot, shutdown) |

### update_manager

| Event | Level | When |
|-------|-------|------|
| Update check result | INFO | available/current |
| Apply start | INFO | — |
| Apply complete | INFO | success |
| Apply fail | ERROR | error details |

### module_manager

| Event | Level | When |
|-------|-------|------|
| Module load | INFO | module_id |
| Module unload | INFO | module_id |
| Route registration | DEBUG | module_id, prefix (optional, may be noisy) |

**Implementation notes:**
- Audit each manager; add log calls at the listed points
- Prefer structured messages: `logger.info("Session started device_id=%s session_id=%s", ...)`
- **Risk:** LOW — additive; verify no missing logger (audit shows all have it)

---

## Phase 5: /api/v1/logs/system Endpoint Enhancement

**Constraint (from audit Task D):** Frontend `web/js/pages/logs.js` expects:
- List: `{ data: { files: [{ name, size, modified }] } }`
- Content: `{ data: { file, tail, lines: string[], filters } }`

**Display:** `renderLogContent(data.lines || [])` joins `lines` with `"\n"`.

### Backward Compatibility Strategy

**Preserve existing behavior by default.**

| Query params | Behavior | Response shape |
|--------------|----------|----------------|
| (none) | List log files | `{ data: { files: [...] } }` — unchanged |
| `file=all` or `file=<name>` | Tail lines from file(s) | `{ data: { file, tail, lines, filters } }` — unchanged |
| `format=structured` (new) | New structured format | `{ data: { entries, services } }` |

### New Parameters (when format=structured)

| Param | Default | Max | Description |
|-------|---------|-----|-------------|
| service | all | — | `all` or specific service name (api_gateway, serial_manager, etc.) |
| lines | 200 | 1000 | Tail lines per service (capped) |
| level | (none) | — | Filter by min level: DEBUG, INFO, WARNING, ERROR |

### New Response Shape (format=structured)

```json
{
  "data": {
    "entries": [
      {
        "timestamp": "2026-03-06T14:30:00.123Z",
        "level": "INFO",
        "service": "serial_manager",
        "message": "Session started device_id=/dev/ttyUSB0"
      }
    ],
    "services": ["api_gateway", "serial_manager", "network_manager", ...]
  }
}
```

### Implementation Notes

- **logging_service** must support:
  - Parsing plain-text log lines into `{timestamp, level, service, message}` for structured mode
  - Service filter: read only matching `{service}.log` files
  - Level filter: include only records >= specified level
- **Route handler** in `routes/logs.py`:
  - If `format=structured`: call new `logging_service.read_structured(...)` and return `{ entries, services }`
  - Else: existing `list_logs()` / `read_log()` / `read_all_logs()` — no change
- **Frontend:** No change required for current UI. Future UI can add a "Structured view" that uses `format=structured` and renders `entries` as a table.

**Parameter naming:** Current API uses `tail`; scope uses `lines`. Support both: `lines` as primary, `tail` as alias for backward compatibility when `format != structured`.

**Risk:** MEDIUM — frontend contract must not break; new code path must be well-tested

---

## Implementation Order

| Phase | Description | Dependencies |
|-------|-------------|--------------|
| 1 | lib/module_logger.py enhancements | None |
| 2 | Request logging middleware | Phase 1e (get_api_logger) |
| 3 | WebSocket event logging | Phase 1 |
| 4 | Manager-level event logging | Phase 1 |
| 5 | logs/system endpoint enhancement | Phase 1, logging_service |

**Recommended sequence:** 1 → 2 → 3 → 4 → 5

---

## Risk Summary

| Change | Risk | Mitigation |
|-------|------|------------|
| RotatingFileHandler | LOW | Drop-in replacement |
| Stdout handler | LOW | Additive |
| RPI_ENGINEER_LOG_LEVEL | LOW | Env-controlled, default INFO |
| JSON formatter | LOW | Env-controlled, dev default unchanged |
| get_api_logger | LOW | New function |
| Request middleware | MEDIUM | Exclude noisy paths; handle exceptions; test timing |
| WebSocket logging | LOW | Additive |
| Manager logging | LOW | Additive |
| logs/system enhancement | MEDIUM | Preserve default response; new format opt-in |

---

## Environment Variables (New/Updated)

| Variable | Purpose | Default |
|----------|---------|---------|
| RPI_ENGINEER_LOG_LEVEL | Log level for file and stdout | INFO |
| RPI_ENGINEER_LOG_FORMAT | `json` or `text` | (derived from RPI_ENGINEER_ENV) |
| RPI_ENGINEER_ENV | `production` → JSON format | (none) |

**docs/ENV.md:** Add RPI_ENGINEER_LOG_LEVEL, RPI_ENGINEER_LOG_FORMAT; document RPI_ENGINEER_ENV for logging.

---

## Out of Scope (Deferred)

- Per-message WebSocket logging (too noisy)
- routes/remote.py logger (low priority; add in Phase 4 if time)
- Module API routes (example, syslog, snmp) — delegates to receivers
- file_share submodules (user_store, server_ftp, server_sftp) — add only if operational need arises

---

## Confirmation Checklist

Before implementation:

- [ ] Plan reviewed and approved
- [ ] Backward compatibility strategy for logs/system confirmed
- [ ] Parameter naming (`lines` vs `tail`) confirmed
- [ ] Middleware exclusion rules (health, static) confirmed
- [ ] docs/ENV.md update scope confirmed

---

*Plan saved. Awaiting confirmation before any code changes.*

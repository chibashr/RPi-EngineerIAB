# Pre-Flight Findings: Flask → FastAPI Migration

**Generated:** 2026-03-06  
**Purpose:** Pre-flight investigation before code changes. Output for planning and migration subagents.

---

## Task A — Async Compatibility Scan

### Gevent Usage

| File | Line | What it does | Migration complexity |
|------|------|--------------|----------------------|
| `services/api_gateway/websockets.py` | 10 | `import gevent` | **MEDIUM** — Used for `gevent.sleep` and `gevent.spawn` in serial console reader |
| `services/api_gateway/websockets.py` | 12 | `from gevent.event import Event as GeventEvent` | **MEDIUM** — Stop event for serial reader greenlet |
| `services/api_gateway/websockets.py` | 177 | `gevent.sleep(read_poll_interval)` | **MEDIUM** — Non-blocking sleep in serial reader loop; replace with `asyncio.sleep` |
| `services/api_gateway/websockets.py` | 203 | `greenlet = gevent.spawn(reader)` | **MEDIUM** — Spawns reader as greenlet; replace with `asyncio.create_task` or run in executor |
| `services/api_gateway/main.py` | 130–133 | `gevent.monkey.patch_all()`, `gevent.pywsgi.WSGIServer` | **SIMPLE** — Remove; FastAPI uses uvicorn/ASGI |
| `services/serial_manager/manager.py` | 31 | `from gevent.threadpool import ThreadPool` | **MEDIUM** — Used for `_threadpool.apply()`; replace with `asyncio.to_thread` or `run_in_executor` |

### Threading.Thread Usage (Potential asyncio Conflict)

| File | Line | What it does | Migration complexity |
|------|------|--------------|----------------------|
| `services/api_gateway/websockets.py` | 87 | `threading.Thread(target=receiver, daemon=True)` | **MEDIUM** — Status stream: receiver thread for ping/pong; can use asyncio task |
| `services/api_gateway/websockets.py` | 283 | `threading.Thread(target=run_apply, daemon=True)` | **MEDIUM** — Update apply: runs blocking `update_manager.apply_update()`; wrap in `run_in_executor` |
| `services/capture_manager/manager.py` | 98, 102 | `threading.Thread` for tcpdump capture jobs | **SIMPLE** — Manager-internal; already isolated; keep or wrap in executor if called from async |

### Blocking I/O in Route Handlers (Not in Executor)

| File | Line | What it does | Migration complexity |
|------|------|--------------|----------------------|
| `services/api_gateway/routes/capture.py` | 84 | `send_file(str(job.file_path))` | **SIMPLE** — File send; FastAPI `FileResponse` or `StreamingResponse` |
| `services/api_gateway/routes/backup.py` | 23 | `send_file(...)` | **SIMPLE** — Same as above |
| `services/api_gateway/routes/serial.py` | 185 | `send_file(...)` | **SIMPLE** — Same as above |
| `services/api_gateway/routes/logs.py` | 24–28, 54 | `logging_service.read_all_logs()`, `read_log()`, `send_file()` | **MEDIUM** — File reads in service; route delegates; wrap service calls in executor if blocking |
| `services/api_gateway/main.py` | 33–38, 83–93, 98–113 | `send_file()` for module assets, index, web assets | **SIMPLE** — Replace with FastAPI `FileResponse` |

**Note:** Route handlers themselves mostly delegate to managers. Blocking I/O is in managers (subprocess, file reads, serial). Under FastAPI, long-running manager calls should be wrapped in `run_in_executor` or moved to background tasks.

### Flask.g / Application Context

| Finding |
|---------|
| **No `flask.g` usage** found in `services/`. |
| **No Flask application context dependencies** that lack a direct FastAPI equivalent. |

---

## Task B — WebSocket Protocol Audit

### Handler: `/ws/status`

| Aspect | Details |
|--------|---------|
| **Library** | flask-sock (`Sock`) |
| **Pattern** | Loop with `ws.send()` / `ws.receive()`; no generator |
| **Client → Server** | `{"type": "ping"}` (JSON text) |
| **Server → Client** | `{"type": "pong"}` on ping; periodic `{"type": "system_metrics", "data": {...}}`, `{"type": "network_status", "data": {...}}`, `{"type": "network_interfaces", "data": [...]}`, `{"type": "monitor_status", "data": {...}}` every 2 seconds |
| **Frames** | Text only (JSON) |
| **Lifecycle** | No explicit on_connect; receiver runs in `threading.Thread`; `stop_event` on receive failure or `None`; main loop exits when `stop_event` set |
| **Notes** | Uses `threading.Event`, `threading.Lock`, `time.sleep(2)` in main loop |

### Handler: `/ws/serial/<session_id>`

| Aspect | Details |
|--------|---------|
| **Library** | flask-sock |
| **Pattern** | Main loop `ws.receive()`; reader runs as `gevent.spawn(reader)` |
| **Client → Server** | `{"type": "ping"}` → `{"type": "pong"}`; `{"type": "data", "data": "<string>"}` → write to serial; `{"type": "control", "action": "pause_logging"|"resume_logging"|"break", "duration": 0.25}` |
| **Server → Client** | `{"type": "error", "message": "..."}`; `{"type": "data", "data": "<string>"}` (serial RX); `{"type": "status", "bytes_tx": N, "bytes_rx": N}` (periodic) |
| **Frames** | Text only (JSON) |
| **Lifecycle** | On connect: validate session, open serial; reader greenlet; on close: `stop_event.set()`, `greenlet.join()`, close serial, release session |
| **Notes** | Uses `gevent.sleep`, `gevent.spawn`, `GeventEvent`; serial I/O is blocking |

### Handler: `/ws/updates/apply`

| Aspect | Details |
|--------|---------|
| **Library** | flask-sock |
| **Pattern** | Spawns `threading.Thread` for `run_apply()`; main handler `thread.join(timeout=180)` |
| **Client → Server** | None expected (one-way progress stream) |
| **Server → Client** | `{"type": "progress", "line": "..."}`; `{"type": "done", "result": {...}}`; `{"type": "error", "message": "..."}` |
| **Frames** | Text only (JSON) |
| **Lifecycle** | No on_connect; handler blocks until apply completes or times out |
| **Notes** | Blocking `update_manager.apply_update()` in thread |

### Handler: `/ws/capture/<capture_id>`

| Aspect | Details |
|--------|---------|
| **Library** | flask-sock |
| **Pattern** | `subprocess.Popen`; iterates `proc.stdout` with `for line in proc.stdout`; `ws.send()` per line |
| **Client → Server** | None expected |
| **Server → Client** | `{"type": "error", "message": "..."}`; `{"type": "packet", "summary": "<line>"}` |
| **Frames** | Text only (JSON) |
| **Lifecycle** | No on_connect; on close `proc.terminate()`, `proc.wait()` |
| **Notes** | Blocking `subprocess.Popen` + synchronous iteration; no generator pattern |

---

## Task C — Module Plugin Interface Audit

### How `register_module_routes()` Works

1. **Entry:** `module_manager.register_module_routes(app)` is called from `services/api_gateway/routes/__init__.py` inside `register_routes(app)`.
2. **Flow:**
   - `attach_app(app)` — stores app reference; if app changes, clears `routes_registered` for all records.
   - For each `ModuleRecord` in registry: `_register_module_api_routes(record)`.
   - For each enabled record: `_start_module(record)` (calls `main.initialize()`).
3. **`_register_module_api_routes(record)`:**
   - Skips if `routes_registered` or no `_app`.
   - Imports `{module_id}.api`.
   - Calls `module.register_routes(self._app)` if present.
   - Modules call `app.register_blueprint(bp)`.

### When Routes Are Mounted

- **Startup:** When `register_routes(app)` runs (during `create_app()`), which calls `module_manager.register_module_routes(app)`.
- **Runtime:** When `enable_module(module_id)` is called and `record.routes_registered` is False, `_register_module_api_routes(record)` runs again.

### Modules That Register Routes

| Module | api.py | Flask-specific APIs |
|--------|--------|---------------------|
| `example_module` | Yes | `Blueprint`, `error_response`, `success_response`, `app.register_blueprint` |
| `syslog_receiver` | Yes | `Blueprint`, `request`, `request.args`, `request.get_json()`, `error_response`, `success_response`, `app.register_blueprint` |
| `snmp_trap_receiver` | Yes | Same as syslog |
| `file_share` | Yes | `Blueprint`, `request`, `request.files`, `request.form`, `request.args`, `request.get_json()`, `error_response`, `success_response`, `app.register_blueprint` |

### Module API Dependencies

All modules use:

- `flask.Blueprint`
- `flask.request` (args, get_json, files, form)
- `services.api_gateway.response.success_response` / `error_response` (Flask `jsonify`-based)
- `app.register_blueprint(bp)`

**Migration:** Each module's `register_routes(app)` must be updated to accept a FastAPI app and use `app.include_router(router, prefix=...)` instead of `app.register_blueprint(bp)`. Request access changes from `request.args` / `request.get_json()` to FastAPI `Depends()` / `Query()` / `Body()`.

---

## Task D — Frontend API Contract Audit

### REST Response Envelope

| Source | Format | Notes |
|--------|--------|-------|
| `services/api_gateway/response.py` | Success: `{"data": <any>, "meta": {"timestamp": "..."}}` | `jsonify(payload)` |
| | Error: `{"error": {"code": "...", "message": "...", "details": {...}}}` | |
| `web/js/api.js` | `extractData(payload)` returns `payload.data ?? payload` | Handles both wrapped and raw |
| `web/js/api.js` (error) | `payload?.error?.message` for POST error message | Expects `error.message` |
| Pages | `extractData(payload) \|\| {}` | Prefer `data`; fallback to raw |

**Conclusion:** Frontend expects `{ data: ... }` for success and `{ error: { message: ... } }` for errors. `extractData()` tolerates raw JSON (`payload.data ?? payload`). **Changing to raw JSON would break** pages that rely on `data`; keeping the envelope is safe.

### WebSocket Message Format

| Source | Expectation |
|--------|-------------|
| `web/js/websocket.js` | `JSON.parse(event.data)`; `message.type` used to dispatch to handlers |
| `web/js/websocket.js` | Client sends `{ type: "ping" }` every 30s |
| `web/js/pages/dashboard.js`, `simple.js` | Handlers for `system_metrics`, `network_status`, `network_interfaces`, `monitor_status` |
| `web/js/pages/serial.js` | Handlers for `data`, `status`, `error`, `pong` |
| `web/js/pages/capture.js` | Handlers for `packet`, `error` |
| `web/js/pages/updates.js` | Handlers for `progress`, `done`, `error` |

**Conclusion:** WebSocket protocol is type-based JSON. **No changes needed** if server keeps sending `{ type: "...", data?: ..., ... }`.

### Breaking Changes If Response Format Changes

| Change | Impact |
|--------|--------|
| Remove `data` wrapper | **BREAKS** — All pages use `extractData()` which prefers `payload.data` |
| Change `error.message` to `error.detail` | **BREAKS** — `apiPost` and `updates.js` read `payload?.error?.message` |
| Change WebSocket `type` semantics | **BREAKS** — Handlers keyed by `message.type` |

---

## Task E — lib/ Compatibility Check

| File | Flask imports | Gevent imports | Verdict |
|------|---------------|----------------|----------|
| `lib/common.py` | None | None | **Untouched** — Empty stub |
| `lib/module_logger.py` | None | None | **Untouched** — Standard logging only |
| `lib/api_client.py` | None | None | **Untouched** — `urllib` HTTP client |
| `lib/utils.py` | None | None | **Untouched** — Empty stub |

**Conclusion:** All `lib/` files are framework-agnostic. **No changes required** for migration.

---

## Blockers Before Migration Can Start

### Critical (Must Resolve First)

1. **WebSocket stack:** flask-sock + gevent + threading must be replaced with native FastAPI/Starlette WebSockets. Serial console handler is the most complex (gevent greenlet + blocking serial I/O).

2. **Module API contract:** All four modules (`example_module`, `syslog_receiver`, `snmp_trap_receiver`, `file_share`) use Flask Blueprint + `request` + gateway `success_response`/`error_response`. A shared adapter or updated `register_routes(app)` signature is needed before migration.

3. **Response helpers:** `services/api_gateway/response.py` uses `flask.jsonify`. FastAPI equivalent must preserve `{ data, meta }` and `{ error: { code, message, details } }` so the frontend stays compatible.

### High (Plan Before Implementation)

4. **gevent.ThreadPool in serial_manager:** `_threadpool.apply()` used for device scanning. Replace with `asyncio.to_thread` or `run_in_executor` when called from async context.

5. **Blocking manager calls:** Network, system, update, capture, serial, and other managers use `subprocess.run`, `path.read_text()`, and synchronous I/O. Route handlers that call these should run them in an executor or the managers should expose async interfaces.

6. **Main entry point:** `main.py` uses `gevent.pywsgi.WSGIServer` or `app.run()`. Replace with uvicorn/hypercorn for ASGI.

### Medium (Can Defer)

7. **send_file usage:** Multiple routes use `flask.send_file`. Straightforward to replace with FastAPI `FileResponse` or `StreamingResponse`.

8. **CORS and security headers:** Implement equivalent middleware in FastAPI.

---

## Summary Table

| Task | Key Findings |
|------|--------------|
| A | 6 gevent usages, 3 threading usages, no flask.g; blocking I/O in managers and WebSocket handlers |
| B | 4 WebSocket handlers; all use flask-sock send/receive; text frames only; serial uses gevent |
| C | `register_module_routes` at startup + on enable; 4 modules with Flask Blueprint + request |
| D | Frontend expects `{ data }` / `{ error: { message } }`; WebSocket `type`-based; envelope must stay |
| E | lib/ has no Flask or gevent; safe to leave unchanged |

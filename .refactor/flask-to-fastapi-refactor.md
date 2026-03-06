# Flask → FastAPI Refactor Plan

**Author:** chibashr  
**Scope:** API Gateway migration from Flask to FastAPI  
**Status:** WAITING FOR CONFIRMATION

---

## Executive Summary

Migrate the RPi Engineer-in-a-Box API gateway from Flask + flask-cors + flask-sock + gevent to FastAPI + uvicorn[standard], preserving all route paths, WebSocket behavior, and frontend compatibility. The refactor is phased to minimize risk and enable incremental validation.

---

## Phase 1: Dependency Swap

### Files Affected
- `requirements.txt`

### Changes
| Current | Target |
|---------|--------|
| Flask | FastAPI |
| flask-cors | (built-in middleware) |
| flask-sock | (native Starlette WebSockets) |
| gevent | (removed; uvicorn handles concurrency) |
| — | uvicorn[standard] |

### Stays the Same
- psutil, pyserial, pyudev (unchanged)
- requirements-dev.txt (pytest; add httpx for async tests if needed)

### Risk Level
**LOW**

### Estimated Complexity
Low — single file change; no code yet.

### Test Strategy
- Run `pip install -r requirements.txt` in venv; verify no conflicts.
- Ensure existing tests still import (they will fail until Phase 2; that is expected).

---

## Phase 2: App Factory Migration (`api_gateway/main.py`)

### Files Affected
- `services/api_gateway/main.py`

### Changes
- Replace `Flask(__name__, static_folder=None)` with `FastAPI()`.
- Replace `CORS(app, resources={...})` with `CORSMiddleware` (allow_origin_regex for LAN patterns).
- Replace `@app.after_request` with `@app.middleware("http")` or lifespan for security headers.
- Replace `@app.get(...)` with `@app.get(...)` (FastAPI uses same decorator names).
- Replace `send_file` with `FileResponse` from starlette.
- Replace `abort(404)` with `HTTPException(status_code=404)`.
- Remove `Sock(app)` and gevent/WSGIServer logic; WebSockets registered in Phase 5.
- Add `if __name__ == "__main__"`: run via `uvicorn.run(app, host=..., port=...)`.

### Stays the Same
- Route paths: `/`, `/advanced`, `/advanced/`, `/health`, `/modules/<module_id>/<path>`, `/<path>`.
- Security headers (X-Content-Type-Options, X-Frame-Options, CSP).
- REPO_ROOT, web_root, module_asset logic.

### Risk Level
**MEDIUM** — CORS regex must match exactly; security headers must be preserved.

### Estimated Complexity
Medium — core app structure change.

### Test Strategy
- Unit test: `create_app()` returns FastAPI instance.
- Integration: `GET /health` returns 200 with `{"data":{"status":"healthy"}}`.
- Integration: `GET /` serves index.html.
- Verify CORS: request from allowed origin gets Access-Control-Allow-Origin.

---

## Phase 3: Blueprint → APIRouter Migration (10 Routers)

### Files Affected
| Blueprint | File | Prefix |
|-----------|------|--------|
| dashboard | `services/api_gateway/routes/dashboard.py` | `/api/v1/dashboard` |
| system | `services/api_gateway/routes/system.py` | `/api/v1/system` |
| network | `services/api_gateway/routes/network.py` | `/api/v1/network` |
| serial | `services/api_gateway/routes/serial.py` | `/api/v1/serial` |
| capture | `services/api_gateway/routes/capture.py` | `/api/v1/capture` |
| updates | `services/api_gateway/routes/updates.py` | `/api/v1/updates` |
| backup | `services/api_gateway/routes/backup.py` | `/api/v1/backup` |
| logs | `services/api_gateway/routes/logs.py` | `/api/v1/logs` |
| modules | `services/api_gateway/routes/modules.py` | `/api/v1/modules` |
| remote | `services/api_gateway/routes/remote.py` | `/api/v1/remote` |

Also: `services/api_gateway/routes/__init__.py` — change `register_routes(app)` to `app.include_router(router, prefix=...)` for each.

### Changes (per route file)
- `Blueprint("name", __name__, url_prefix="...")` → `APIRouter(prefix="...", tags=["..."])`.
- `@bp.get("/path")` → `@router.get("/path")`.
- `request.get_json(silent=True)` → `await request.json()` or `Body(...)` (FastAPI dependency injection).
- `request.args.get("x")` → `Query(...)` or `request.query_params.get("x")`.
- `return success_response(data)` → `return JSONResponse(content=...)` or adapt `response.py` for FastAPI.
- `app.register_blueprint(bp)` → `app.include_router(router, prefix="...")`.

### Stays the Same
- Route paths (no renames).
- Manager calls (sync for now; see Phase 4).
- Response shape: `{"data": ..., "meta": {"timestamp": ...}}`.

### Risk Level
**LOW** per router — mechanical conversion.

### Estimated Complexity
Medium — 10 files; do one at a time, test after each.

### Test Strategy
- For each router: run existing `tests/unit/test_api_*.py` and `tests/integration/test_api*.py`.
- Ensure JSON response structure unchanged (frontend expects `data` key).

---

## Phase 4: Async Conversion Rules

### Manager Call Analysis

| Manager | Called From | Subprocess/Blocking | Await? |
|---------|-------------|---------------------|--------|
| system_manager | routes, websockets | subprocess.run (brief) | No — wrap in `run_in_executor` if needed |
| network_manager | routes, websockets | subprocess.run (ip, nmcli, etc.) | No — sync; use `run_in_executor` in WS if blocking |
| serial_manager | routes, websockets | ThreadPool, file I/O | No — sync |
| capture_manager | routes, websockets | subprocess.Popen, subprocess.run | No — sync |
| update_manager | routes, websockets | subprocess.run, git, file I/O | No — sync; `apply_update` is blocking |
| backup (config) | routes | file I/O | No |
| logging_service | routes, websockets | file I/O | No |
| module_manager | routes | importlib, file I/O | No |
| remote_access_manager | routes | subprocess.run | No |
| monitor_service | websockets | psutil, file I/O | No |

### Rule
- **Route handlers**: Keep sync initially. FastAPI runs sync handlers in a thread pool by default; no `await` required.
- **WebSocket handlers**: Must be `async def`. Blocking calls (e.g. `update_manager.apply_update`, `subprocess.Popen` iteration) → run in `asyncio.to_thread()` or `run_in_executor` to avoid blocking the event loop.
- **No manager changes** unless a manager is invoked from an async WebSocket and blocks for >100ms.

### Risk Level
**MEDIUM** — WebSocket handlers that block (updates/apply, capture stream) need careful async adaptation.

### Estimated Complexity
Low for routes; Medium for WebSocket handlers.

---

## Phase 5: WebSocket Handler Migration

### Files Affected
- `services/api_gateway/websockets.py` (major rewrite)
- `services/api_gateway/main.py` (wire WebSocket routes)
- `services/serial_manager/manager.py` (gevent.threadpool → asyncio/threading)

### Paths to Migrate
| Path | Purpose | Current Pattern |
|------|---------|-----------------|
| `/ws/status` | Live status stream | threading.Thread + time.sleep(2) loop |
| `/ws/serial/<session_id>` | Serial I/O | gevent.spawn(reader) + GeventEvent |
| `/ws/updates/apply` | Update progress | threading.Thread + update_manager.apply_update |
| `/ws/capture/<capture_id>` | Capture stream | subprocess.Popen + for line in proc.stdout |

### Changes

#### 5.1 `/ws/status`
- Replace `@sock.route` with `@app.websocket("/ws/status")`.
- Handler: `async def status_stream(websocket: WebSocket)`.
- Replace `ws.receive()` with `await websocket.receive_text()`.
- Replace `ws.send(json.dumps(...))` with `await websocket.send_json(...)`.
- Replace `time.sleep(2)` with `await asyncio.sleep(2)`.
- Replace `threading.Thread` for receiver with `asyncio.create_task` for a non-blocking receive loop.
- Manager calls (system_manager, network_manager, etc.) are sync — run in `asyncio.to_thread()` if they block, or keep in loop (they are fast).

#### 5.2 `/ws/serial/<session_id>`
- **Critical**: flask-sock uses `simple_websocket`; Starlette uses native `WebSocket`.
- Replace `gevent.spawn(reader)` with `asyncio.create_task(reader_coro)` or run reader in `asyncio.to_thread` (serial read is blocking).
- Replace `GeventEvent` with `asyncio.Event`.
- Replace `gevent.sleep(0.05)` with `await asyncio.sleep(0.05)`.
- Serial port read: blocking I/O → run in `asyncio.to_thread` or use a thread with queue.
- `ws.receive()` / `ws.send()` → `await websocket.receive_text()` / `await websocket.send_json()`.
- **Risk**: Serial streaming is the most complex; ensure no data loss or connection drops during migration.

#### 5.3 `/ws/updates/apply`
- Replace `threading.Thread` with `asyncio.to_thread(update_manager.apply_update, ...)`.
- `progress_callback` must be thread-safe; use `asyncio.run_coroutine_threadsafe` or a queue if callback needs to `await websocket.send_json`.
- Simpler: run entire `apply_update` in `asyncio.to_thread`, have callback push to a queue, main coroutine drains queue and sends.

#### 5.4 `/ws/capture/<capture_id>`
- `for line in proc.stdout` blocks. Use `asyncio.to_thread` to run a sync iterator, or `asyncio.create_subprocess_exec` with `stdout=asyncio.subprocess.PIPE` and `async for line in proc.stdout`.
- Prefer `asyncio.create_subprocess_exec` for native async subprocess.

### Stays the Same
- Message formats: `{"type": "system_metrics", "data": ...}`, etc.
- Client protocol: ping/pong, data, control, progress, done, error.

### Risk Level
**HIGH** for `/ws/serial/<session_id>` — gevent greenlets vs asyncio tasks; serial read loop is sensitive.  
**MEDIUM** for `/ws/updates/apply` and `/ws/capture/<capture_id>` — subprocess handling.  
**LOW** for `/ws/status`.

### Estimated Complexity
High for serial; Medium for updates/capture; Low for status.

### Test Strategy
- `tests/integration/test_serial_websocket.py` — verify serial WebSocket full flow.
- Manual: connect to each WS path, verify message flow.
- Load: multiple status clients; ensure no degradation.

---

## Phase 6: Module Manager Router Registration

### Files Affected
- `services/module_manager/manager.py`
- `modules/example_module/api.py`
- `modules/syslog_receiver/api.py`
- `modules/snmp_trap_receiver/api.py` (if exists)
- `modules/file_share/api.py`

### Current Behavior
- `register_module_routes(app)` receives Flask app.
- Each module's `register_routes(app)` calls `app.register_blueprint(bp)`.
- Modules can be enabled at runtime; routes registered on enable if not already.

### Target Behavior
- `register_module_routes(app)` receives FastAPI app.
- Each module's `register_routes(app)` calls `app.include_router(router, prefix="/api/v1/<module_id>")`.
- **Timing**: Plan says "at load time". Current design allows enable-at-runtime. Options:
  - **A**: Register all module routes at startup (enabled or not); `is_enabled` check in each handler. Matches "load time."
  - **B**: Keep runtime registration; FastAPI supports `app.include_router` at runtime (less common but valid).
- **Recommendation**: A — register all at startup; handlers return 409 if module disabled. Simpler, matches "load time."

### Changes
- Module `api.py`: `Blueprint` → `APIRouter`; `app.register_blueprint` → `app.include_router`.
- `module_manager._register_module_api_routes`: pass FastAPI app; modules call `app.include_router(router, prefix=...)`.
- `attach_app` / `_app`: store FastAPI app; same pattern.

### Stays the Same
- Module discovery, enable/disable, `resolve_web_asset`.
- Route paths: `/api/v1/example`, `/api/v1/syslog`, etc.

### Risk Level
**MEDIUM** — Module API contract change; all modules must be updated.

### Estimated Complexity
Medium — 4+ module api.py files + module_manager.

### Test Strategy
- Enable example_module, syslog, fileshare; hit `/api/v1/example/hello`, etc.
- Disable module; verify 409 or equivalent.

---

## Phase 7: lib/ Compatibility Check

### Files Affected
- `lib/common.py`
- `lib/module_logger.py`
- `lib/api_client.py`
- `lib/utils.py`
- `services/api_gateway/response.py`

### Analysis

| File | Flask Deps? | Changes |
|------|-------------|---------|
| common.py | No | None |
| module_logger.py | No | None |
| api_client.py | No (urllib) | None |
| utils.py | No | None |
| response.py | `from flask import jsonify` | Replace with FastAPI/Starlette: `JSONResponse(content=payload, status_code=...)` or `return payload` with FastAPI auto-JSON. |

### response.py Migration
- `success_response(data, meta, status_code)` → return `JSONResponse(content={"data": data, "meta": {...}}, status_code=status_code)`.
- `error_response(code, message, details, status_code)` → same pattern.
- Routes can use `return success_response(data)` if we keep the helper returning a Response object.

### Risk Level
**LOW**

### Estimated Complexity
Low — response.py only.

### Test Strategy
- `tests/unit/test_response.py` — verify payload structure.

---

## Phase 8: Frontend JS — api.js and websocket.js

### Files Affected
- `web/js/api.js`
- `web/js/websocket.js`

### Analysis
- **api.js**: Uses `fetch()` with relative URLs. No Flask-specific code. **No changes.**
- **websocket.js**: Uses `new WebSocket(url)` with `ws://` or `wss://`. Protocol is JSON `{type, data}`. **No changes** — WebSocket API is standard; server implementation change is transparent.

### Stays the Same
- All frontend code. Paths, message formats, and behavior unchanged.

### Risk Level
**LOW**

### Estimated Complexity
None.

### Test Strategy
- Manual E2E: load dashboard, status stream, serial console, capture stream, update apply. Verify no console errors.

---

## Phase 9: bin/install.sh and systemd Unit

### Files Affected
- `bin/install.sh` (or `bin/install-src/06-services.sh` if that is the source)
- `bin/start.sh`, `bin/stop.sh` (no change — they start/stop by service name)

### Changes

#### 9.1 API Service ExecStart
**Current:**
```
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/api_gateway/main.py
```
**Target:**
```
ExecStart=$INSTALL_DIR/venv/bin/uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 5000
```
Or, if main.py exposes `app` and we want configurable host/port:
```
ExecStart=$INSTALL_DIR/venv/bin/uvicorn services.api_gateway.main:app --host ${RPI_ENGINEER_API_HOST:-0.0.0.0} --port ${RPI_ENGINEER_API_PORT:-5000}
```

#### 9.2 Environment
- Remove `RPI_ENGINEER_USE_GEVENT=1` from api_env (gevent no longer used).
- Keep `RPI_ENGINEER_ROOT`, `RPI_ENGINEER_DRY_RUN`.

#### 9.3 install_python_dependencies
- After `pip install -r requirements.txt`, add check: `"$venv_path/bin/python" -c "import fastapi"` (or uvicorn) instead of flask.

### Stays the Same
- nginx proxy to 127.0.0.1:5000.
- All other services (network, serial, capture, etc.).

### Risk Level
**LOW**

### Estimated Complexity
Low — a few line changes in install script.

### Test Strategy
- Run install on clean system; verify `rpi-engineer-api` starts and serves /health.

---

## Phase 10: Test Strategy Summary

| Phase | Tests |
|-------|-------|
| 1 | pip install, import check |
| 2 | create_app, /health, /, CORS |
| 3 | All existing test_api_*.py, test_api_gateway |
| 4 | (Covered by 3 and 5) |
| 5 | test_serial_websocket, manual WS paths |
| 6 | test_api_modules, module routes |
| 7 | test_response |
| 8 | Manual E2E |
| 9 | Install + service start |

---

## Risk Assessment

### 1. flask-sock vs Starlette WebSocket API
- **Difference**: flask-sock wraps `simple_websocket`; Starlette uses native WebSocket. `receive()`/`send()` become `await websocket.receive_*()`/`await websocket.send_*()`.
- **Serial streaming**: Most sensitive. Blocking `ser.read()` in a loop must not block the event loop. Use `asyncio.to_thread` or a dedicated thread with queue.
- **Mitigation**: Implement serial WS with async-compatible pattern; test with real device.

### 2. gevent Removal — Manager Patterns
- **serial_manager**: Uses `gevent.threadpool.ThreadPool` for `_pyudev_scan_ports` and `_dev_glob_scan`. Replace with `concurrent.futures.ThreadPoolExecutor` or `asyncio.to_thread`.
- **websockets.py**: Uses `gevent.spawn`, `GeventEvent`, `gevent.sleep`. Replace with `asyncio.create_task`, `asyncio.Event`, `asyncio.sleep`.
- **No other managers** use gevent directly.

### 3. Module Plugin Route Mounting Timing
- **Current**: Routes registered when `register_module_routes(app)` is called (at startup), and again when a module is enabled at runtime if not yet registered.
- **Target**: Register all module routes at startup. Handlers check `module_manager.is_enabled(module_id)` and return 409 if disabled.
- **Risk**: Modules that assume routes only exist when enabled may break. Audit all module handlers.

### 4. Async Subprocess in capture_manager and update_manager
- **capture_manager**: `subprocess.Popen` for tcpdump; `for line in proc.stdout` blocks. Use `asyncio.create_subprocess_exec` with `async for line in proc.stdout`.
- **update_manager**: `apply_update` runs `subprocess.run`, `git`, file I/O. Called from WS handler. Run entire `apply_update` in `asyncio.to_thread`; progress callback uses thread-safe queue to send to WebSocket.
- **Mitigation**: Keep sync implementations; wrap in executor when called from async context.

### 5. LAN CORS Config
- **Current**: Regex origins for 127.0.0.1, localhost, 192.168.x.x, 10.x.x.x, 172.16–31.x.x.
- **FastAPI CORSMiddleware**: `allow_origin_regex=r"http://(127\.0\.0\.1|localhost|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"` — verify regex matches exactly.
- **Test**: Request from LAN IP; check `Access-Control-Allow-Origin` header.

---

## Execution Order

1. Phase 1 (deps)
2. Phase 7 (response.py) — needed for Phase 2/3
3. Phase 2 (main.py)
4. Phase 3 (routers, one by one)
5. Phase 6 (module_manager + module apis)
6. Phase 5 (WebSockets)
7. Phase 4 (async rules applied during Phase 5)
8. Phase 9 (install + systemd)
9. Phase 8 (verification only)

---

## Files Changed Summary

| Category | Files |
|----------|-------|
| Deps | requirements.txt |
| App | services/api_gateway/main.py |
| Routes | services/api_gateway/routes/*.py (10), routes/__init__.py |
| Response | services/api_gateway/response.py |
| WebSockets | services/api_gateway/websockets.py |
| Module | services/module_manager/manager.py |
| Modules | modules/*/api.py (example, syslog, snmp_traps, file_share) |
| Serial | services/serial_manager/manager.py (ThreadPool) |
| Deploy | bin/install.sh, bin/install-src/06-services.sh |
| Frontend | None |

---

**WAITING FOR CONFIRMATION**

Do not proceed with implementation until confirmed.

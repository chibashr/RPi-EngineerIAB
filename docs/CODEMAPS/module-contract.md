# Module Contract

<!-- Generated: 2026-03-17 -->

## Overview

All optional features are implemented as modules. Modules ship in the base repo under `modules/<id>/`. Enable/disable is controlled by `module.json` and takes effect on restart. All modules default to enabled.

Core services (auth, system, network, logs, backup, updates, remote_access) are never modules and are always loaded.

---

## Directory Structure

```
modules/
  <module_id>/
    module.json          # required
    main.py              # required
    api.py               # required
    manager.py           # domain logic (recommended, keeps api.py thin)
    web/
      component.html     # UI panel injected into /advanced/
      module.js          # page JS for this module
    data/                # optional; module-local SQLite or files
    README.md            # optional; module-specific docs
```

---

## module.json Schema

```json
{
  "id": "serial",
  "name": "Serial Console",
  "prefix": "serial",
  "version": "1.0.0",
  "enabled": true,
  "description": "Serial device management and console sessions",
  "has_websockets": true
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | string | yes | Unique, lowercase, underscores. Matches directory name. |
| name | string | yes | Display name in UI nav |
| prefix | string | yes | URL prefix: /api/v1/<prefix> |
| version | string | yes | Semver |
| enabled | bool | yes | Default true. Set false to disable. Restart required. |
| description | string | no | Shown in modules management UI |
| has_websockets | bool | no | Hint for module_manager; default false |

---

## main.py Interface

### initialize(app, status_queue) — required

Called once at startup by module_manager if `enabled: true`.

```python
from fastapi import FastAPI
import asyncio

def initialize(app: FastAPI, status_queue: asyncio.Queue) -> None:
    """
    Mount routes, start background tasks, optionally begin pushing
    status updates to status_queue.
    """
    from .api import router
    app.include_router(router, prefix="/api/v1/<prefix>", tags=["<id>"])
    # start background tasks, etc.
```

Rules:
- Must not raise. Exceptions during initialize() disable the module and log an error; they must not crash the app.
- Must not block. Start background tasks with asyncio, not synchronous loops.
- Must mount the APIRouter from api.py.

### register_websockets(app) — optional

Called by module_manager after initialize() if the method exists on the module.

```python
def register_websockets(app: FastAPI) -> None:
    from .websockets import register
    register(app)
```

Rules:
- Only implement if the module has WebSocket endpoints.
- All WS endpoints for this module are registered here and nowhere else.

---

## status_queue Protocol

`status_queue` is an `asyncio.Queue` instance, shared across all modules and core services. The `/ws/status` stream reads from it and broadcasts to all connected clients.

### Push format

```python
await status_queue.put({
    "source": "serial",          # must match module id
    "type": "session_activity",  # event type, module-defined
    "data": {                    # arbitrary dict
        "active_sessions": 2,
        "session_ids": ["abc", "def"]
    }
})
```

### Rules

- Push only when state changes or on a reasonable interval (suggest 5s max for polling-style updates).
- Do not push on every request or log line — this is a status feed, not an event log.
- `source` must exactly match the module `id` in module.json.
- `data` must be JSON-serializable.
- Never await status_queue.get() from a module. Modules are producers only.

---

## api.py Interface

Standard FastAPI APIRouter. Keep thin — domain logic lives in manager.py.

```python
from fastapi import APIRouter, Depends
from services.auth_service import require_admin

router = APIRouter()

@router.get("/status")
async def get_status():
    from .manager import get_status
    return get_status()
```

Rules:
- Do not call `app.include_router()` here. Route mounting is done in initialize().
- Do not import from other modules.
- Admin-gated routes use `require_admin` Depends from auth_service.

---

## lib/ Usage

Modules may import from lib/ freely. Shared patterns:

- `lib/module_logger.py` — `get_service_logger(module_id)` for consistent log formatting
- `lib/session_manager.py` — Base class for bidirectional WebSocket session management (serial, remote_console use this)
- `lib/common.py` — General helpers
- `lib/utils.py` — Utilities

Modules must not import from:
- Other modules (`modules/<other>/`)
- Core service internals (`services/<manager>/manager.py`) — use the REST API or lib/ abstractions instead

---

## lib/session_manager.py Contract

Shared by serial and remote_console modules. Provides bidirectional WebSocket session lifecycle.

```python
class SessionManager:
    def create_session(self, session_id: str, target: Any) -> Session
    def get_session(self, session_id: str) -> Session | None
    def close_session(self, session_id: str) -> None
    async def handle_websocket(self, websocket: WebSocket, session_id: str) -> None
```

Modules subclass or instantiate SessionManager. They do not reimplement session lifecycle logic.

---

## First-Party Modules

| Module ID | prefix | WS | Default |
|-----------|--------|----|---------|
| serial | serial | yes | enabled |
| capture | capture | yes | enabled |
| remote_console | remote-console | yes | enabled |
| syslog | syslog | no | enabled |
| snmp_traps | snmp_traps | no | enabled |
| fileshare | fileshare | no | enabled |

---

## module_manager Responsibilities

- Discover all modules by scanning `modules/*/module.json` at startup
- For each module where `enabled: true`: call `initialize(app, status_queue)`, then `register_websockets(app)` if defined
- Expose `GET /api/v1/modules/list` — returns all modules with id, name, enabled, status
- Expose `POST /api/v1/modules/enable/<id>` and `/disable/<id>` — writes enabled flag to module.json, triggers restart
- `resolve_web_asset(module_id, path)` — serves module web assets via /modules/<id>/<path>
- If initialize() raises, log the error, mark module as failed, continue startup

---

## Enable/Disable Flow

1. User toggles module in UI → POST /api/v1/modules/enable/<id> or /disable/<id>
2. module_manager writes `enabled` flag to module.json
3. API responds with `{ "restart_required": true }`
4. UI shows restart prompt
5. User confirms → POST /api/v1/system/power (restart action)
6. On next startup, module_manager reads updated module.json and loads accordingly

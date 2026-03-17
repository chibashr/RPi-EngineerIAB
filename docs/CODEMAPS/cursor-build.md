# Cursor Build — Module System Rework

<!-- Generated: 2026-03-17 -->

## Dependency Map

```
[Prompt 1: Scaffold + Contracts] ──────────────────────────────────────────┐
                                                                            ▼
[Prompt 2: Agent CORE — module_manager + status_queue + dashboard] ───► [Prompt 8: Integration]
[Prompt 3: Agent CORE — lib/session_manager + websockets refactor ] ───►       │
[Prompt 4: Agent MODULE — serial + capture migration             ] ───►        │
[Prompt 5: Agent MODULE — remote_console migration               ] ───►        │
[Prompt 6: Agent MODULE — syslog + snmp_traps + fileshare        ] ───►        ▼
[Prompt 7: Agent FRONTEND — dynamic nav + dashboard + ws/status  ] ───► [Prompt 9: Verify]

Parallel after Prompt 1: Prompts 2, 3 sequential (3 depends on 2 for status_queue shape).
Parallel after Prompt 3: Prompts 4, 5, 6, 7 can run simultaneously.
```

---

## Build Assumptions

These are documented here and will be written into AGENTS.md in Prompt 1:

- Enable/disable writes to module.json and returns `restart_required: true`; actual restart is triggered via existing POST /api/v1/system/power
- status_queue is an asyncio.Queue instantiated in create_app() and passed to all modules
- session_manager.py base class covers serial and remote_console; they subclass it
- Dashboard endpoint aggregates from system_manager, network_manager, module_manager; it does not add a new manager
- /ws/status message dispatch on frontend uses `source` + `type` fields per module-contract.md
- Existing manager.py files for serial, capture, remote_console are moved into their module directories without logic changes; only imports and paths change
- module_manager.discover_modules() scans modules/*/module.json at startup; no dynamic scanning at runtime

---

## Prompt 1 — Scaffold
**Mode:** Agent
**Files in scope:** entire repo root
**Depends on:** nothing

Create the following new files and directories. Do not implement logic yet — empty files only, except those listed under "Write in full."

New directories and empty files:
```
modules/serial/
  module.json
  main.py
  api.py
  manager.py        # move existing services/serial_manager/manager.py content here later
  web/
    component.html
    module.js

modules/capture/
  module.json
  main.py
  api.py
  manager.py
  web/
    component.html
    module.js

modules/remote_console/
  module.json
  main.py
  api.py
  manager.py
  web/
    component.html
    module.js

modules/syslog/
  module.json       # already exists; verify schema matches contract
  main.py           # already exists; will be updated in Prompt 6
  api.py
  manager.py

modules/snmp_traps/
  module.json
  main.py
  api.py
  manager.py

modules/fileshare/
  module.json
  main.py
  api.py
  manager.py

lib/session_manager.py    # new shared base

services/api_gateway/routes/dashboard.py    # replaces 501 stub
```

Write these files in full now:

**modules/serial/module.json**
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

**modules/capture/module.json**
```json
{
  "id": "capture",
  "name": "Packet Capture",
  "prefix": "capture",
  "version": "1.0.0",
  "enabled": true,
  "description": "Network packet capture and analysis",
  "has_websockets": true
}
```

**modules/remote_console/module.json**
```json
{
  "id": "remote_console",
  "name": "Remote Console",
  "prefix": "remote-console",
  "version": "1.0.0",
  "enabled": true,
  "description": "SSH and Telnet remote console sessions",
  "has_websockets": true
}
```

**modules/syslog/module.json**
```json
{
  "id": "syslog",
  "name": "Syslog",
  "prefix": "syslog",
  "version": "1.0.0",
  "enabled": true,
  "description": "Syslog receiver and viewer",
  "has_websockets": false
}
```

**modules/snmp_traps/module.json**
```json
{
  "id": "snmp_traps",
  "name": "SNMP Traps",
  "prefix": "snmp_traps",
  "version": "1.0.0",
  "enabled": true,
  "description": "SNMP trap receiver and viewer",
  "has_websockets": false
}
```

**modules/fileshare/module.json**
```json
{
  "id": "fileshare",
  "name": "File Share",
  "prefix": "fileshare",
  "version": "1.0.0",
  "enabled": true,
  "description": "File sharing service",
  "has_websockets": false
}
```

Write **AGENTS.md** in full:

```markdown
# AGENTS.md

## Build Assumptions
- Enable/disable writes to module.json; returns restart_required: true; restart via POST /api/v1/system/power
- status_queue is asyncio.Queue instantiated in create_app(), passed to all module initialize() calls
- lib/session_manager.py base covers serial and remote_console session lifecycle
- Dashboard endpoint aggregates from existing managers; no new manager added
- /ws/status frontend dispatch uses message source + type fields
- Existing manager.py logic for serial, capture, remote_console moves to modules/<id>/manager.py; imports updated, logic unchanged
- module_manager scans modules/*/module.json once at startup

## Agent: CORE
Scope: services/module_manager/, services/api_gateway/routes/dashboard.py, services/api_gateway/main.py, services/api_gateway/websockets.py, services/monitor_service/
Responsibilities: module_manager rework (discover, initialize, register_websockets, status_queue plumbing), dashboard aggregation endpoint, /ws/status multiplexed stream, startup sequence
Dependencies: Prompt 1
Must not touch: modules/, lib/session_manager.py, frontend
Output contract:
  - module_manager.discover_modules() → list of module metadata
  - module_manager passes (app, status_queue) to each enabled module's initialize()
  - module_manager calls register_websockets(app) if defined
  - GET /api/v1/dashboard returns { system, network, modules, active_sessions }
  - GET /api/v1/modules/list returns list of { id, name, enabled, status }
  - POST /api/v1/modules/enable/<id> and /disable/<id> write module.json, return { restart_required: true }
  - /ws/status streams { source, type, data } from status_queue to all clients
  - status_queue instance available for import by modules

## Agent: SESSION-LIB
Scope: lib/session_manager.py
Responsibilities: shared bidirectional WebSocket session base class used by serial and remote_console
Dependencies: Prompt 2 (needs status_queue shape confirmed)
Must not touch: any module, any service, any route
Output contract:
  - SessionManager class with: create_session(session_id, target), get_session(session_id), close_session(session_id), async handle_websocket(websocket, session_id)
  - Session dataclass or namedtuple with id, target, state fields

## Agent: MODULE-SERIAL-CAPTURE
Scope: modules/serial/, modules/capture/, services/serial_manager/ (read-only source), services/capture_manager/ (read-only source)
Responsibilities: migrate serial and capture to module contract; move manager logic; implement initialize(), register_websockets(), api.py routes, status_queue pushes, web stubs
Dependencies: Prompt 3 (session_manager base must exist)
Must not touch: modules/remote_console/, core services (write), frontend
Output contract:
  - modules/serial/main.py exports initialize(app, status_queue) and register_websockets(app)
  - modules/capture/main.py exports initialize(app, status_queue) and register_websockets(app)
  - All routes from backend.md serial and capture sections implemented in api.py
  - Serial pushes { source: "serial", type: "session_activity", data: { active_sessions, session_ids } }
  - Capture pushes { source: "capture", type: "capture_activity", data: { active_captures, capture_ids } }

## Agent: MODULE-REMOTE-CONSOLE
Scope: modules/remote_console/, services/remote_console_manager/ (read-only source)
Responsibilities: migrate remote_console to module contract using lib/session_manager base
Dependencies: Prompt 3 (session_manager base must exist)
Must not touch: modules/serial/, modules/capture/, core services (write), frontend
Output contract:
  - modules/remote_console/main.py exports initialize(app, status_queue) and register_websockets(app)
  - All routes from backend.md remote_console section implemented in api.py
  - Uses lib/session_manager.SessionManager (does not reimplement session lifecycle)
  - Pushes { source: "remote_console", type: "session_activity", data: { active_sessions, session_ids } }

## Agent: MODULE-SIMPLE
Scope: modules/syslog/, modules/snmp_traps/, modules/fileshare/
Responsibilities: apply module contract to existing syslog and snmp_traps; implement fileshare module contract; no logic changes to receivers
Dependencies: Prompt 2 (status_queue shape)
Must not touch: serial, capture, remote_console modules, core services, frontend
Output contract:
  - All three modules: initialize(app, status_queue) in main.py
  - Existing receiver.py logic untouched; api.py routes delegate to receiver
  - Syslog pushes { source: "syslog", type: "status", data: { running, stored_count } }
  - SNMP pushes { source: "snmp_traps", type: "status", data: { running, stored_count } }

## Agent: FRONTEND
Scope: web/advanced/index.html, web/js/mode.js, web/js/pages/dashboard.js, web/js/websocket.js, modules/*/web/
Responsibilities: dynamic nav from /api/v1/modules/list, dashboard page-load from /api/v1/dashboard, /ws/status message dispatch, module web stubs
Dependencies: Prompts 2–6 (API contracts must be final)
Must not touch: backend, lib/, services/, core HTML outside advanced/
Output contract:
  - Nav renders core items always; module items only if enabled in modules list
  - dashboard.js uses GET /api/v1/dashboard for initial render
  - websocket.js dispatches on { source, type } to per-module update handlers
  - Each module web/ has component.html and module.js (stub UI acceptable; no broken references)
```

Write **BUILD_ORDER.md** in full:

```markdown
# BUILD_ORDER.md

- [ ] 1. Scaffold (Prompt 1)
- [ ] 2. CORE agent — module_manager, status_queue, dashboard, /ws/status (Prompt 2)
- [ ] 3. SESSION-LIB agent — lib/session_manager.py (Prompt 3)
- [ ] 4. MODULE-SERIAL-CAPTURE agent (Prompt 4) [parallel with 5, 6, 7]
- [ ] 5. MODULE-REMOTE-CONSOLE agent (Prompt 5) [parallel with 4, 6, 7]
- [ ] 6. MODULE-SIMPLE agent (Prompt 6) [parallel with 4, 5, 7]
- [ ] 7. FRONTEND agent (Prompt 7) [parallel with 4, 5, 6]
- [ ] 8. Integration (Prompt 8)
- [ ] 9. Verify + Finalize (Prompt 9)
```

Do not explain what you did. Only write files.

---

## Prompt 2 — CORE Agent
**Mode:** Agent
**Files in scope:** services/module_manager/manager.py, services/api_gateway/main.py, services/api_gateway/websockets.py, services/api_gateway/routes/dashboard.py, services/api_gateway/routes/modules.py, services/monitor_service/monitor.py
**Depends on:** Prompt 1
**Parallel with:** none (Prompt 3 depends on this)

Context: You are Agent CORE as defined in AGENTS.md. Stay within your scope.

This module must export / implement:
- `module_manager.discover_modules()` scans `modules/*/module.json`, returns list of module metadata dicts
- `module_manager` calls `module.initialize(app, status_queue)` for each enabled module at startup, then `module.register_websockets(app)` if the method exists; exceptions are caught, logged, module marked failed, startup continues
- `status_queue` is `asyncio.Queue()` instantiated in `create_app()` in main.py and passed through
- `GET /api/v1/modules/list` returns `[{ id, name, enabled, status, version }]`
- `POST /api/v1/modules/enable/<id>` and `/disable/<id>` write the `enabled` field in the module's module.json, return `{ "restart_required": true }`; remove the existing `/available` and `/install-from-repo` endpoints
- `GET /api/v1/dashboard` aggregates: system status from system_manager, network status from network_manager, enabled modules from module_manager, active sessions from any module that exposes a `get_active_sessions()` method (optional interface)
- `/ws/status` WebSocket reads from status_queue in a loop and broadcasts each message as JSON to all connected clients; core system metrics are pushed to status_queue by monitor_service on a 5s interval
- monitor_service pushes `{ source: "system", type: "metrics", data: { cpu, memory, disk } }` and `{ source: "network", type: "interfaces", data: { ... } }` to status_queue

Startup sequence in main.py `create_app()`:
1. Register core routes
2. `module_manager.discover_and_initialize(app, status_queue)`
3. Register core websockets (/ws/status, /ws/updates/apply)
4. Mount static files

Acceptance criteria:
- [ ] module_manager reads all modules/*/module.json at startup
- [ ] enabled modules have initialize() called with (app, status_queue)
- [ ] register_websockets() called if method exists on module
- [ ] failed module initialize() does not crash app
- [ ] /api/v1/modules/list returns correct list
- [ ] /api/v1/modules/enable and /disable write module.json and return restart_required
- [ ] /available and /install-from-repo endpoints removed
- [ ] /api/v1/dashboard returns aggregated payload
- [ ] /ws/status streams status_queue messages as JSON
- [ ] monitor_service pushes system and network updates to status_queue on 5s interval
- [ ] No stubs, TODOs, or placeholder implementations

When done: mark step 2 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 3 — SESSION-LIB Agent
**Mode:** Agent
**Files in scope:** lib/session_manager.py
**Depends on:** Prompt 2
**Parallel with:** none (Prompts 4 and 5 depend on this)

Context: You are Agent SESSION-LIB as defined in AGENTS.md. Stay within your scope.

This file must export:
- `Session` dataclass: fields `id: str`, `target: Any`, `state: str` (values: "open", "closed")
- `SessionManager` class:
  - `create_session(session_id: str, target: Any) -> Session`
  - `get_session(session_id: str) -> Session | None`
  - `close_session(session_id: str) -> None`
  - `list_sessions() -> list[Session]`
  - `async handle_websocket(websocket: WebSocket, session_id: str, read_cb, write_cb) -> None`
    - `read_cb(data: bytes) -> None` — called when data arrives from client
    - `write_cb() -> AsyncIterator[bytes]` — async generator yielding data to send to client
    - Handles WebSocket lifecycle: accept, read/write loop, close on disconnect or session close

This is the shared base for serial and remote_console. It must not contain any serial- or SSH-specific logic.

Acceptance criteria:
- [ ] Session dataclass defined with id, target, state
- [ ] All four SessionManager methods implemented
- [ ] handle_websocket manages full WS lifecycle
- [ ] No serial, SSH, or protocol-specific imports or logic
- [ ] Importable as `from lib.session_manager import SessionManager, Session`
- [ ] No stubs or TODOs

When done: mark step 3 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 4 — MODULE-SERIAL-CAPTURE Agent
**Mode:** Agent
**Files in scope:** modules/serial/, modules/capture/
**Depends on:** Prompt 3
**Parallel with:** Prompts 5, 6, 7

Context: You are Agent MODULE-SERIAL-CAPTURE as defined in AGENTS.md. Stay within your scope.

Read `services/serial_manager/manager.py` and `services/capture_manager/manager.py` as source. Move their logic into `modules/serial/manager.py` and `modules/capture/manager.py` respectively. Update all internal imports. Do not modify the source files yet — leave them in place; they will be removed in the Integration prompt.

Each module must implement the full contract from module-contract.md:

**modules/serial/main.py:**
- `initialize(app, status_queue)`: mounts router from api.py, stores status_queue reference, starts background task that pushes `{ source: "serial", type: "session_activity", data: { active_sessions: int, session_ids: list } }` when session count changes
- `register_websockets(app)`: mounts `/ws/serial/{session_id}` using `lib.session_manager.SessionManager`

**modules/serial/api.py:** All routes from backend.md serial section. Delegates to manager.py.

**modules/capture/main.py:**
- `initialize(app, status_queue)`: mounts router, pushes `{ source: "capture", type: "capture_activity", data: { active_captures: int, capture_ids: list } }` when capture count changes
- `register_websockets(app)`: mounts `/ws/capture/{capture_id}`

**modules/capture/api.py:** All routes from backend.md capture section. Delegates to manager.py.

Both modules: use `lib.module_logger.get_service_logger(module_id)` for logging. No imports from other modules.

Acceptance criteria:
- [ ] modules/serial/main.py exports initialize() and register_websockets()
- [ ] modules/capture/main.py exports initialize() and register_websockets()
- [ ] All serial routes from backend.md implemented in api.py
- [ ] All capture routes from backend.md implemented in api.py
- [ ] Serial uses lib/session_manager for WS session lifecycle
- [ ] Both modules push correct status_queue messages
- [ ] No imports from other modules or core service internals
- [ ] No stubs or TODOs

When done: mark step 4 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 5 — MODULE-REMOTE-CONSOLE Agent
**Mode:** Agent
**Files in scope:** modules/remote_console/
**Depends on:** Prompt 3
**Parallel with:** Prompts 4, 6, 7

Context: You are Agent MODULE-REMOTE-CONSOLE as defined in AGENTS.md. Stay within your scope.

Read `services/remote_console_manager/manager.py` as source. Move logic to `modules/remote_console/manager.py`. Update imports. Do not modify source file.

**modules/remote_console/main.py:**
- `initialize(app, status_queue)`: mounts router from api.py, pushes `{ source: "remote_console", type: "session_activity", data: { active_sessions: int, session_ids: list } }` when session count changes
- `register_websockets(app)`: mounts `/ws/remote-console/{session_id}` using `lib.session_manager.SessionManager`

**modules/remote_console/api.py:** All routes from backend.md remote_console section. Delegates to manager.py.

Must use `lib.session_manager.SessionManager` for WebSocket session lifecycle. Must not reimplement session management. SSH and Telnet protocol handling stays in manager.py; session_manager handles only the WebSocket I/O loop.

Acceptance criteria:
- [ ] main.py exports initialize() and register_websockets()
- [ ] All remote_console routes from backend.md implemented
- [ ] Uses lib/session_manager — no duplicate session lifecycle code
- [ ] Pushes correct status_queue messages
- [ ] No imports from other modules
- [ ] No stubs or TODOs

When done: mark step 5 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 6 — MODULE-SIMPLE Agent
**Mode:** Agent
**Files in scope:** modules/syslog/, modules/snmp_traps/, modules/fileshare/
**Depends on:** Prompt 2
**Parallel with:** Prompts 4, 5, 7

Context: You are Agent MODULE-SIMPLE as defined in AGENTS.md. Stay within your scope.

**modules/syslog/main.py:**
- `initialize(app, status_queue)`: mount router from api.py; push `{ source: "syslog", type: "status", data: { running: bool, stored_count: int } }` on a 30s interval
- No register_websockets needed

**modules/syslog/api.py:** All routes from backend.md syslog section. Delegate to existing `modules/syslog/receiver.py`. Do not modify receiver.py.

Apply the same pattern to **snmp_traps**: initialize(), api.py delegating to existing receiver.py, push `{ source: "snmp_traps", type: "status", data: { running: bool, stored_count: int } }`.

**modules/fileshare/main.py:** initialize(app, status_queue). No status push needed (no meaningful live state).
**modules/fileshare/api.py:** All routes from backend.md fileshare section.
**modules/fileshare/manager.py:** Implement fileshare domain logic (status, config, user management, file listing, upload).

All three: use `lib.module_logger.get_service_logger(module_id)`. No imports from other modules.

Acceptance criteria:
- [ ] All three modules implement initialize()
- [ ] Syslog and snmp_traps api.py routes implemented, delegating to existing receivers
- [ ] Receivers not modified
- [ ] Fileshare manager.py implemented (no stubs)
- [ ] Syslog and snmp_traps push status to status_queue on interval
- [ ] No stubs or TODOs

When done: mark step 6 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 7 — FRONTEND Agent
**Mode:** Agent
**Files in scope:** web/advanced/index.html, web/js/mode.js, web/js/pages/dashboard.js, web/js/websocket.js, modules/serial/web/, modules/capture/web/, modules/remote_console/web/, modules/syslog/web/, modules/snmp_traps/web/, modules/fileshare/web/
**Depends on:** Prompts 2–6 (API contracts final)
**Parallel with:** Prompts 4, 5, 6

Context: You are Agent FRONTEND as defined in AGENTS.md. Stay within your scope.

**Dynamic nav (web/js/mode.js or advanced/index.html):**
- On load, call `GET /api/v1/modules/list`
- Core nav items (system, network, logs, backup, updates, remote) always rendered
- For each enabled module in the response, inject a nav item and load its component.html
- Nav injection order: core items first, then modules in list order

**Dashboard (web/js/pages/dashboard.js):**
- Initial render from `GET /api/v1/dashboard` response: populate system health, network summary, active sessions, module status cards
- After initial render, switch to /ws/status for live updates

**WebSocket (web/js/websocket.js):**
- Connect to /ws/status on page load
- Dispatch messages by `source` + `type`:
  - `source: "system", type: "metrics"` → update system stats in dashboard
  - `source: "network", type: "interfaces"` → update network section
  - `source: "<module_id>", type: "*"` → call registered handler for that module if present
- Expose `registerStatusHandler(source, type, handler)` so module JS can register its own handlers

**Module web stubs:** Each modules/<id>/web/ needs a working component.html (panel with module name and basic status) and module.js (registers a status handler via registerStatusHandler, updates the panel). Full UI is not required — no broken references or JS errors.

Acceptance criteria:
- [ ] Core nav always visible
- [ ] Module nav items appear only for enabled modules
- [ ] dashboard.js uses /api/v1/dashboard for initial render
- [ ] websocket.js dispatches by source + type
- [ ] registerStatusHandler() implemented and used by at least one module
- [ ] All module web/ directories have non-broken component.html and module.js
- [ ] No JS console errors on page load

When done: mark step 7 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 8 — Integration
**Mode:** Agent
**Files in scope:** services/api_gateway/main.py, all module main.py files, services/serial_manager/, services/capture_manager/, services/remote_console_manager/
**Depends on:** Prompts 2–7

Wire everything together and clean up superseded files.

1. Verify create_app() startup sequence per architecture.md: core routes → module_manager.discover_and_initialize() → core websockets → static files.
2. Verify every module's initialize() and register_websockets() are reachable and called correctly.
3. Remove `services/serial_manager/`, `services/capture_manager/`, `services/remote_console_manager/` — their logic now lives in the respective modules. Update any remaining imports.
4. Remove routes/serial.py, routes/capture.py, routes/remote_console.py from api_gateway — these are now owned by modules.
5. Verify no dangling imports reference removed files.
6. Start the application. Fix any startup errors until it runs without exceptions.

Acceptance criteria:
- [ ] App starts without errors
- [ ] All module routes reachable at /api/v1/<prefix>/...
- [ ] All module websockets reachable
- [ ] /api/v1/dashboard returns valid response
- [ ] /ws/status connects and streams messages
- [ ] services/serial_manager, capture_manager, remote_console_manager removed
- [ ] No unused imports or unresolved references

When done: mark step 8 complete in BUILD_ORDER.md.
Do not explain what you did. Only write code.

---

## Prompt 9 — Verify + Finalize
**Mode:** Agent
**Files in scope:** entire repo
**Depends on:** Prompt 8

1. Run all existing tests. Write new tests covering:
   - module_manager: discover_modules() returns correct list; enabled module gets initialize() called; disabled module does not; failed initialize() does not crash startup
   - status_queue: message pushed by a module is received by /ws/status
   - dashboard: GET /api/v1/dashboard returns system, network, modules, active_sessions keys
   - Each module: at least one route happy path per module
   - session_manager: create, get, close session; handle_websocket lifecycle
   Run tests. Fix failures until all pass.

2. Fix all lint and type errors.

3. Update README.md:
   - ## Installation — exact steps
   - ## Usage — how to run, enable/disable modules
   - ## Configuration — module.json fields explained
   - ## Architecture — module system, core vs module split, status_queue pattern

4. Verify every item in module-contract.md is implemented (no stubs, no TODOs).

5. Write DONE.md:
   - What was built
   - Assumptions from AGENTS.md
   - Known limitations

Acceptance criteria:
- [ ] All tests pass
- [ ] No lint or type errors
- [ ] README fully written
- [ ] DONE.md written
- [ ] App starts and runs in one command

Do not explain what you did. Only write code and files.

---

## Token Estimates

| Prompt | Estimate |
|--------|----------|
| Prompt 1 — Scaffold | ~900 tokens |
| Prompt 2 — CORE | ~700 tokens |
| Prompt 3 — SESSION-LIB | ~500 tokens |
| Prompt 4 — MODULE-SERIAL-CAPTURE | ~650 tokens |
| Prompt 5 — MODULE-REMOTE-CONSOLE | ~500 tokens |
| Prompt 6 — MODULE-SIMPLE | ~550 tokens |
| Prompt 7 — FRONTEND | ~600 tokens |
| Prompt 8 — Integration | ~400 tokens |
| Prompt 9 — Verify | ~450 tokens |
| **Total** | **~5,250 tokens** |

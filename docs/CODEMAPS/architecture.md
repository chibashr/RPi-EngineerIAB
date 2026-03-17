# Architecture

<!-- Reworked: 2026-03-17 | Supersedes prior architecture.md -->

## Project Type

Single application (Python FastAPI + static web). Deployed on Raspberry Pi. All features ship in the base repo; optional features are enabled/disabled via module flags. Enable/disable requires a service restart.

## High-Level Diagram

```
[Browser] <--HTTP/WS--> [API Gateway :5000] <--> [Core Services]
                              |                        |
                        web/ (static)           system_manager
                        /modules/<id>/          network_manager
                                               remote_access_manager
                                               update_manager
                                               module_manager --> [Modules]
                                               logging_service
                                               backup_service
                                               auth_service
                                               monitor_service
                                                     |
                                               [Status Queue]
                                                     |
                                         serial_module (default on)
                                         capture_module (default on)
                                         remote_console_module (default on)
                                         syslog_module (default on)
                                         snmp_traps_module (default on)
                                         fileshare_module (default on)
```

## Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| API + Web | `services/api_gateway/main.py` | FastAPI app (uvicorn); serves /, /advanced/, /api/v1/*, /ws/*, /health |
| Modules | `modules/<name>/main.py` | `initialize(app, status_queue)` called by module_manager at startup |

## Core vs Module Split

### Core (always loaded, always in nav)

| Service | Path | Purpose |
|---------|------|---------|
| api_gateway | services/api_gateway/ | Routes, middleware, static assets, WS registration |
| auth_service | services/auth_service/ | Login, token verification, require_admin |
| module_manager | services/module_manager/ | Discover, load, initialize modules at startup |
| system_manager | services/system_manager/ | System status, services, power, settings |
| network_manager | services/network_manager/ | Interfaces, routes, profiles, hotspot, VLANs |
| remote_access_manager | services/remote_access_manager/ | AnyDesk, TeamViewer, VNC, Pi Connect |
| update_manager | services/update_manager/ | Check, apply, rollback, reconfigure |
| logging_service | services/logging_service/ | System logs, export |
| backup_service | services/backup_service/ | Config export/restore |
| monitor_service | services/monitor_service/ | Feeds system metrics into status queue |

### Modules (default enabled, restart to change)

| Module | Path | WS Endpoints |
|--------|------|-------------|
| serial | modules/serial/ | /ws/serial/{session_id} |
| capture | modules/capture/ | /ws/capture/{capture_id} |
| remote_console | modules/remote_console/ | /ws/remote-console/{session_id} |
| syslog | modules/syslog/ | none |
| snmp_traps | modules/snmp_traps/ | none |
| fileshare | modules/fileshare/ | none |

## Module Contract

Every module must conform to this interface. All hooks are called once at startup by module_manager.

```
module.json          — metadata: id, name, prefix, enabled (bool), version
api.py               — APIRouter; routes mounted under /api/v1/<prefix>
main.py              — initialize(app, status_queue): required
                       register_websockets(app): optional
web/
  component.html     — UI panel injected into advanced/ page
  module.js          — page JS for this module
```

### initialize(app, status_queue)

Required. Called by module_manager if `enabled: true`. Responsibilities:
- Mount APIRouter from api.py onto app
- Start any background tasks
- Optionally begin pushing status dicts to status_queue

### register_websockets(app)

Optional. Called by module_manager after initialize() if the method exists. Mount all WebSocket endpoints for this module here.

### status_queue protocol

`status_queue` is an `asyncio.Queue` passed to every module at initialize(). Modules push dicts:

```python
await status_queue.put({
    "source": "<module_id>",   # e.g. "serial"
    "type": "<event_type>",    # e.g. "session_activity"
    "data": { ... }
})
```

The `/ws/status` stream reads this queue and multiplexes all messages to connected clients. Core services (system, network) push directly via monitor_service. Modules push via status_queue. Neither blocks the other.

## Data Flow

- REST: Client → Gateway → route handler → manager/module → (subprocess / filesystem / lib)
- WebSocket: Client → Gateway → core WS handler or module WS handler → manager/module
- Status stream: monitor_service + modules → status_queue → /ws/status → clients
- Version/updates: config/version or data/version (git ref); update_manager compares to remote ref

## Shared Library (lib/)

Cross-cutting concerns only. No module may import from another module. No core service imports from modules/.

| File | Purpose |
|------|---------|
| lib/common.py | Shared helpers |
| lib/module_logger.py | get_service_logger |
| lib/api_client.py | API client utilities |
| lib/utils.py | General utilities |
| lib/session_manager.py | Shared bidirectional WS session logic (used by serial, remote_console) |

## Dashboard

`GET /api/v1/dashboard` returns a single aggregated payload on page load:

```json
{
  "system": { ... },
  "network": { ... },
  "modules": [ { "id": "serial", "enabled": true, "status": { ... } } ],
  "active_sessions": { ... }
}
```

Frontend uses this for initial render, then switches to /ws/status for live updates.

## WebSocket: /ws/status

Streams a multiplexed feed of:
- System metrics (CPU, memory, disk) — from monitor_service
- Network interface status — from network_manager
- Active module status — from each enabled module via status_queue
- Capture/serial session activity — from respective modules via status_queue

Core and module streams are independent; a module pushing to status_queue cannot affect core stream reliability.

## Key Files

- `services/api_gateway/main.py` — create_app(), startup sequence, uvicorn
- `services/module_manager/manager.py` — discover, load, initialize, register_websockets per module
- `services/monitor_service/monitor.py` — pushes core status into status_queue on interval
- `services/api_gateway/websockets.py` — register_websockets for core WS; delegates to modules
- `services/api_gateway/routes/dashboard.py` — aggregation endpoint
- `lib/session_manager.py` — shared WS session base (serial + remote_console)
- `lib/module_logger.py` — get_service_logger
- `bin/install.sh` — installation and deploy

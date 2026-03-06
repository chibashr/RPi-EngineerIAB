# Architecture

<!-- Generated: 2026-03-05 | Files scanned: 140+ | Token estimate: ~600 -->

## Project Type

Single application (Python Flask API + static web). Deployed on Raspberry Pi; optional modules extend API and UI.

## High-Level Diagram

```
[Browser] <--HTTP/WS--> [API Gateway :5000] <--> [Managers]
                              |                        |
                        web/ (static)           system_manager
                        /modules/<id>/          network_manager
                                               serial_manager
                                               capture_manager
                                               update_manager
                                               module_manager --> [Modules]
                                               remote_access_manager
                                               logging_service
                                               monitor_service
```

## Entry Points

| Entry | Path | Purpose |
|-------|------|---------|
| API + Web | `services/api_gateway/main.py` | Flask app; serves /, /advanced/, /api/v1/*, /ws/*, /health |
| Modules | `modules/<name>/main.py` | Optional; `initialize()` called by module_manager |

## Service Boundaries

- **API Gateway**: Routes, CORS, security headers, static and module assets. No business logic.
- **Managers** (services/*_manager/, services/*_service/): One per domain (system, network, serial, capture, updates, backup, logs, remote, modules). In-process Python; no separate processes.
- **Modules**: Pluggable (module.json, api.py, main.py, web/). Registered at runtime; routes mounted under /api/v1/<module_prefix>.

## Data Flow

- REST: Client → Gateway → route handler → manager → (subprocess / filesystem / lib).
- WebSocket: Client → Gateway (flask_sock) → manager or module; used for status, serial stream, updates, capture.
- Version/updates: config/version or data/version (git ref); update_manager compares to remote ref.

## Key Files

- `services/api_gateway/main.py` — create_app(), route registration, gevent vs dev server
- `services/module_manager/manager.py` — discover, enable/disable, register_module_routes, resolve_web_asset
- `lib/module_logger.py` — get_service_logger
- `bin/install.sh` — installation and deploy

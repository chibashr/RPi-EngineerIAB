# Architecture

<!-- Generated: 2026-03-17 | Files scanned: 431 | Token estimate: ~610 -->

## Project Type

Single application (Python FastAPI + static web). Deployed on Raspberry Pi; optional modules extend API and UI.

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
| API + Web | `services/api_gateway/main.py` | FastAPI app (uvicorn); serves /, /advanced/, /api/v1/*, /ws/*, /health |
| Modules | `modules/<name>/main.py` | Optional; `initialize()` called by module_manager |

## Service Boundaries

- **API Gateway**: Routes, CORS, security headers, static and module assets. No business logic.
- **Managers** (services/*_manager/, services/*_service/): One per domain (system, network, serial, capture, updates, backup, logs, remote, modules). In-process Python; no separate processes.
- **Modules**: Pluggable (module.json, api.py, main.py, web/). Registration deferred (Phase 6); routes will mount under /api/v1/<module_prefix>.

## Data Flow

- REST: Client → Gateway → route handler → manager → (subprocess / filesystem / lib).
- WebSocket: Client → Gateway (FastAPI native) → manager or module; currently stubbed (Phase 3 migration).
- Version/updates: config/version or data/version (git ref); update_manager compares to remote ref.

## Key Files

- `services/api_gateway/main.py` — create_app(), route registration, uvicorn
- `services/module_manager/manager.py` — discover, enable/disable, register_module_routes (deferred), resolve_web_asset
- `lib/module_logger.py` — get_service_logger
- `bin/install.sh` — installation and deploy

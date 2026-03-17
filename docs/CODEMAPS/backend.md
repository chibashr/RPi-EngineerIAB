# Backend

<!-- Reworked: 2026-03-17 | Supersedes prior backend.md -->

## Routes

### Core (Gateway — always registered)

| Method | Path | Handler |
|--------|------|---------|
| GET | /health | health_check → success_response |
| GET | /modules/<module_id>/<path> | module_asset → module_manager.resolve_web_asset |
| GET | /<path> | StaticFiles (web/; html=True for /, /advanced/) |

### API v1 Routers — Core (prefix /api/v1/<group>)

**auth** — POST /login (returns token; admin-only routes use require_admin Depends)

**dashboard** — GET / (aggregated page-load payload: system health, network status, enabled modules list, active sessions)

**system** — GET /status, /services, /info, /cert-fingerprint; POST /services, /services/bulk, /power, /settings

**network** — GET /interfaces, /interfaces/<id>, /routes, /routes/current, /profiles, /status; PUT /interfaces/<id>, /interfaces/<id>/share-with-hotspot; POST /routes, /profiles, /profiles/<name>/load, /wan-priority, /reset, /vlans, /hotspot; PUT /profiles/<name>; DELETE /profiles/<name>

**updates** — GET /check; POST /apply, /reconfigure, /reinstall, /rollback

**backup** — GET /config; POST /restore

**logs** — GET /system, /export

**modules** — GET /list, /components; POST /enable/<id>, /disable/<id>; DELETE /uninstall/<id>

> Note: /available and /install-from-repo removed. Module enable/disable requires restart; these endpoints trigger a restart after writing the enabled flag to module.json.

**remote** — GET /status, /info; POST /password, /teamviewer/reset-password, /teamviewer/generate-password, /teamviewer/setup-account

### API v1 Routers — Modules (prefix /api/v1/<prefix>, mounted at startup if enabled)

**serial** (/api/v1/serial) — GET /devices, /devices/<id>, /sessions, /sessions/<id>, /logs, /logs/<id>/content, /logs/export/<name>; PUT /devices/configure, /devices/<id>, /sessions/<id>, /logs/<id>; POST /devices/<id>/test, /sessions, /logs/export; DELETE /sessions/<id>, /logs/<id>

**capture** (/api/v1/capture) — GET /interfaces, /active, /active/<id>, /completed, /completed/<id>, /completed/<id>/download, /<id>/stats|packets|conversations|protocols; POST /start, /active/<id>/stop; DELETE /completed/<id>

**remote_console** (/api/v1/remote-console) — GET /targets, /targets/<id>, /sessions, /sessions/<id>; POST /targets, /sessions; PUT /targets/<id>; DELETE /targets/<id>, /sessions/<id>

**syslog** (/api/v1/syslog) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart

**snmp_traps** (/api/v1/snmp_traps) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart

**fileshare** (/api/v1/fileshare) — GET /status, /config, /users, /files; POST /users, /upload

### WebSockets — Core

| Path | Purpose |
|------|---------|
| /ws/status | Multiplexed live stream: system metrics, network status, module status feeds, session activity |
| /ws/updates/apply | Update apply progress stream |

### WebSockets — Modules (registered by module at startup via register_websockets(app))

| Path | Module | Purpose |
|------|--------|---------|
| /ws/serial/{session_id} | serial | Serial session I/O (bidirectional) |
| /ws/capture/{capture_id} | capture | Packet capture stream (tshark -r -l) |
| /ws/remote-console/{session_id} | remote_console | SSH/Telnet session I/O (bidirectional) |

## Startup Sequence

```
create_app()
  → register core routes
  → module_manager.discover_modules()
      for each module where enabled == true:
        module.initialize(app, status_queue)
        if hasattr(module, 'register_websockets'):
          module.register_websockets(app)
  → register core websockets (status, updates)
  → mount static files
```

## Middleware / Pipeline

- CORS (FastAPI CORSMiddleware): localhost, LAN (192.168.x, 10.x, 172.16–31.x)
- SecurityHeadersMiddleware: X-Content-Type-Options, X-Frame-Options, Content-Security-Policy
- Admin routes use require_admin (Depends) from auth_service
- /ws/updates/apply verifies token query param

## Service → Route Mapping

### Core
- auth_router → routes/auth.py → auth_service
- dashboard_router → routes/dashboard.py → aggregates system_manager, network_manager, module_manager
- system_router → routes/system.py → system_manager
- network_router → routes/network.py → network_manager
- updates_router → routes/updates.py → update_manager
- backup_router → routes/backup.py → backup_service
- logs_router → routes/logs.py → logging_service
- modules_router → routes/modules.py → module_manager
- remote_router → routes/remote.py → remote_access_manager

### Modules (self-contained in modules/<name>/api.py)
- serial routes → modules/serial/api.py → modules/serial/manager.py
- capture routes → modules/capture/api.py → modules/capture/manager.py
- remote_console routes → modules/remote_console/api.py → modules/remote_console/manager.py
- syslog routes → modules/syslog/api.py → modules/syslog/receiver.py
- snmp_traps routes → modules/snmp_traps/api.py → modules/snmp_traps/receiver.py
- fileshare routes → modules/fileshare/api.py → modules/fileshare/manager.py

## Key Files

- `services/api_gateway/main.py` — create_app(), startup sequence
- `services/api_gateway/routes/__init__.py` — register_routes (core only)
- `services/api_gateway/routes/dashboard.py` — aggregation endpoint (replaces 501 stub)
- `services/api_gateway/websockets.py` — register core websockets; delegates module WS to module_manager
- `services/module_manager/manager.py` — discover, initialize, register_websockets per module
- `services/api_gateway/response.py` — success_response, error_response
- `lib/session_manager.py` — shared WS session base for serial and remote_console

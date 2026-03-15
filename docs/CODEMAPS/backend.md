# Backend

<!-- Generated: 2026-03-15 | Files scanned: 180+ | Token estimate: ~900 -->

## Routes

### Core (Gateway)

| Method | Path | Handler |
|--------|------|---------|
| GET | /health | health_check → success_response |
| GET | /modules/<module_id>/<path> | module_asset → module_manager.resolve_web_asset |
| GET | /<path> | StaticFiles (web/; html=True for /, /advanced/) |

### API v1 Routers (prefix /api/v1/<group>)

**auth** — POST /login (returns token; admin-only routes use require_admin Depends)
**dashboard** — STUB (501) — Phase 1 migration
**system** — GET /status, /services, /info, /cert-fingerprint; POST /services, /services/bulk, /power, /settings
**network** — GET /interfaces, /interfaces/<id>, /routes, /routes/current, /profiles, /status; PUT /interfaces/<id>, /interfaces/<id>/share-with-hotspot; POST /routes, /profiles, /profiles/<name>/load, /wan-priority, /reset, /vlans, /hotspot; PUT /profiles/<name>; DELETE /profiles/<name>
**serial** — GET /devices, /devices/<id>, /sessions, /sessions/<id>, /logs, /logs/<id>/content, /logs/export/<name>; PUT /devices/configure, /devices/<id>, /sessions/<id>, /logs/<id>; POST /devices/<id>/test, /sessions, /logs/export; DELETE /sessions/<id>, /logs/<id>
**capture** — GET /interfaces, /active, /active/<id>, /completed, /completed/<id>, /completed/<id>/download, /<id>/stats|packets|conversations|protocols; POST /start, /active/<id>/stop; DELETE /completed/<id>
**updates** — GET /check; POST /apply, /reconfigure, /reinstall, /rollback
**backup** — GET /config; POST /restore
**logs** — GET /system, /export
**modules** — GET /list, /components, /available, /updates; POST /install, /enable/<id>, /disable/<id>, /install-from-repo, /update/<id>; DELETE /uninstall/<id>
**remote** — GET /status, /info; POST /password, /teamviewer/reset-password, /teamviewer/generate-password, /teamviewer/setup-account

### Module APIs (deferred Phase 6)

- **example** (/api/v1/example) — GET /hello
- **syslog** (/api/v1/syslog) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart
- **snmp_traps** (/api/v1/snmp_traps) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart
- **fileshare** (/api/v1/fileshare) — GET /status, /config, /users, /files; POST /users, /upload

### WebSockets (FastAPI native)

| Path | Purpose |
|------|---------|
| /ws/status | Live status stream (system_metrics, network_status, network_interfaces, monitor_status) |
| /ws/serial/{session_id} | Serial session I/O (bidirectional) |
| /ws/updates/apply | Update apply progress stream |
| /ws/capture/{capture_id} | Packet capture stream (tshark -r -l) |

## Middleware / Pipeline

- CORS (FastAPI CORSMiddleware): localhost, LAN (192.168.x, 10.x, 172.16–31.x)
- SecurityHeadersMiddleware: X-Content-Type-Options, X-Frame-Options, Content-Security-Policy
- Admin routes use require_admin (Depends) from auth_service; /ws/updates/apply verifies token query param

## Service → Route Mapping

- auth_router → routes/auth.py → auth_service (login, verify_token)
- dashboard → stub (501)
- system_router → routes/system.py → system_manager
- network_router → routes/network.py → network_manager
- serial_router → routes/serial.py → serial_manager
- capture_router → routes/capture.py → capture_manager
- updates_router → routes/updates.py → update_manager
- backup_router → routes/backup.py (config backup/restore)
- logs_router → routes/logs.py → logging_service
- modules_router → routes/modules.py → module_manager
- remote_router → routes/remote.py → remote_access_manager

## Key Files

- `services/api_gateway/routes/__init__.py` — register_routes (auth_router first), APIRouter imports
- `services/api_gateway/websockets.py` — register_websockets (status, serial, updates, capture)
- `services/api_gateway/response.py` — success_response, error_response (Starlette JSONResponse)
- Each `services/*_manager/manager.py` — domain logic

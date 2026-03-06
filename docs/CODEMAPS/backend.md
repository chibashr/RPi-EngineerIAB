# Backend

<!-- Generated: 2026-03-05 | Files scanned: 140+ | Token estimate: ~900 -->

## Routes

### Core (Gateway)

| Method | Path | Handler |
|--------|------|---------|
| GET | /health | health_check → success_response |
| GET | / | serve_simple_index (web/index.html) |
| GET | /advanced, /advanced/ | serve_advanced_index |
| GET | /modules/<module_id>/<path> | module_asset → module_manager.resolve_web_asset |
| GET | /<path> | serve_web_asset (web/) |

### API v1 Blueprints (prefix /api/v1/<group>)

**dashboard** — GET /status → dashboard status  
**system** — GET /status, /services, /info; POST /services, /services/bulk, /power, /settings  
**network** — GET /interfaces, /interfaces/<id>, /routes, /routes/current, /profiles, /status; PUT /interfaces/<id>; POST /routes, /profiles, /profiles/<name>/load, /wan-priority, /reset, /vlans, /hotspot; PUT /profiles/<name>; DELETE /profiles/<name>  
**serial** — GET /devices, /devices/<id>, /sessions, /sessions/<id>, /logs, /logs/<id>/content, /logs/export/<name>; PUT /devices/configure, /devices/<id>, /sessions/<id>, /logs/<id>; POST /devices/<id>/test, /sessions, /logs/export; DELETE /sessions/<id>, /logs/<id>  
**capture** — GET /interfaces, /active, /active/<id>, /completed, /completed/<id>, /completed/<id>/download, /<id>/stats|packets|conversations|protocols; POST /start, /active/<id>/stop; DELETE /completed/<id>  
**updates** — GET /check; POST /apply, /reconfigure, /reinstall, /rollback  
**backup** — GET /config; POST /restore  
**logs** — GET /system, /export  
**modules** — GET /list, /components, /available, /updates; POST /install, /enable/<id>, /disable/<id>, /install-from-repo, /update/<id>; DELETE /uninstall/<id>  
**remote** — GET /status, /info  

### Module APIs (registered dynamically)

**example** (/api/v1/example) — GET /hello  
**syslog** (/api/v1/syslog) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart  
**snmp_traps** (/api/v1/snmp_traps) — GET /status, /recent, /stored, /config, /storage; POST /clear, /start, /stop, /restart  
**fileshare** (/api/v1/fileshare) — GET /status, /config, /users, /files; POST /users, /upload  

### WebSockets (Sock)

| Path | Purpose |
|------|---------|
| /ws/status | Live status stream |
| /ws/serial/<session_id> | Serial session I/O |
| /ws/updates/apply | Update apply progress |
| /ws/capture/<capture_id> | Capture stream |

## Middleware / Pipeline

- CORS on /api/*, /ws/* (localhost, LAN, 192.168.x, 10.x, 172.16–31.x)
- after_request: X-Content-Type-Options, X-Frame-Options, Content-Security-Policy
- No auth middleware (LAN-only design)

## Service → Route Mapping

- dashboard_bp → services/api_gateway/routes/dashboard.py (system_manager for status)
- system_bp → routes/system.py → system_manager
- network_bp → routes/network.py → network_manager
- serial_bp → routes/serial.py → serial_manager
- capture_bp → routes/capture.py → capture_manager
- updates_bp → routes/updates.py → update_manager
- backup_bp → routes/backup.py (config backup/restore)
- logs_bp → routes/logs.py → logging_service
- modules_bp → routes/modules.py → module_manager
- remote_bp → routes/remote.py → remote_access_manager

## Key Files

- `services/api_gateway/routes/__init__.py` — register_routes, blueprint imports
- `services/api_gateway/websockets.py` — register_websockets
- `services/api_gateway/response.py` — success_response
- Each `services/*_manager/manager.py` — domain logic

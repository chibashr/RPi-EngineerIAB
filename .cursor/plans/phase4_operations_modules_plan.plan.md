---
name: Phase 4 Operations and Module System Plan
overview: Detailed implementation plan for Phase 4 (Operations Services and Module System) of RPi Engineer-in-a-Box. Implements Update Manager, Logging Service, Monitor Service, and Module Manager per UPDATE-MAINTENANCE-SPECIFICATION, LOGGING-MONITORING-SPECIFICATION, MODULE-SYSTEM-SPECIFICATION, API-REFERENCE, and WEB-INTERFACE-SPECIFICATION.
parentPlan: full_implementation_plan_e49592f8.plan.md
todos:
  - id: phase4a-update-manager-service
    content: Implement Update Manager service (check, apply, rollback, backup) per UPDATE-MAINTENANCE-SPECIFICATION
    status: pending
  - id: phase4a-update-api
    content: Wire Update Manager to API gateway (updates/check, apply, rollback) and backup endpoints
    status: pending
  - id: phase4a-logging-service
    content: Implement Logging Service (aggregation, viewing API, export) per LOGGING-MONITORING-SPECIFICATION
    status: pending
  - id: phase4a-logging-api
    content: Wire Logging Service to API gateway (logs/system, logs/export)
    status: pending
  - id: phase4a-monitor-service
    content: Implement Monitor Service (metrics, health checks, alerts) per LOGGING-MONITORING-SPECIFICATION
    status: pending
  - id: phase4a-monitor-integration
    content: Integrate Monitor Service with dashboard and status APIs
    status: pending
  - id: phase4a-ui-updates-logs
    content: Wire Updates & Maintenance and Logs & Monitoring pages to Phase 4a APIs
    status: pending
  - id: phase4b-module-manager-core
    content: Implement Module Manager core (discovery, lifecycle, registry) per MODULE-SYSTEM-SPECIFICATION
    status: pending
  - id: phase4b-module-api-routes
    content: Implement module API route registration with API Gateway
    status: pending
  - id: phase4b-module-ui-registration
    content: Implement module UI component registration for web interface
    status: pending
  - id: phase4b-module-api
    content: Wire Module Manager to API gateway (modules/list, install, uninstall, enable, disable)
    status: pending
  - id: phase4b-example-module
    content: Create at least one example module to validate the module contract
    status: pending
  - id: phase4b-modules-ui
    content: Wire Modules page to Module Manager APIs
    status: pending
  - id: phase4-verify
    content: Verify Phase 4 exit criteria (updates, logs, monitoring, module system, example module)
    status: pending
isProject: false
---

# Phase 4: Operations Services and Module System – Detailed Implementation Plan

This plan implements **Phase 4** from [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md). It references the specification suite in [.planning/](../.planning/) in detail.

---

## Goal

Implement Update Manager, Logging Service, Monitor Service, and Module Manager so that updates, logs, monitoring, and extensibility are available via API and UI. At least one example module validates the module contract.

---

## Document References

| Document | Path | Relevant Sections |
|----------|------|-------------------|
| **UPDATE-MAINTENANCE-SPECIFICATION** | [.planning/UPDATE-MAINTENANCE-SPECIFICATION.md](../.planning/UPDATE-MAINTENANCE-SPECIFICATION.md) | §2 Update Mechanism, §3 Update Check, §4 Update Application, §5 Rollback, §6 Backup/Restore, §8 Web Interface Integration |
| **LOGGING-MONITORING-SPECIFICATION** | [.planning/LOGGING-MONITORING-SPECIFICATION.md](../.planning/LOGGING-MONITORING-SPECIFICATION.md) | §2 Logging Architecture, §4 Rotation/Retention, §5 System Metrics, §6 Health Monitoring, §7 Alerts, §8 Log Viewing/Export |
| **MODULE-SYSTEM-SPECIFICATION** | [.planning/MODULE-SYSTEM-SPECIFICATION.md](../.planning/MODULE-SYSTEM-SPECIFICATION.md) | §2 Module Architecture, §3 Module Structure, §4 Metadata, §5 Lifecycle, §6 API Integration, §7 Web Interface Integration, §8 Dependencies |
| **API-REFERENCE** | [.planning/API-REFERENCE.md](../.planning/API-REFERENCE.md) | §9 Updates API, §10 Backup API, §11 Logs API, §12 Modules API |
| **WEB-INTERFACE-SPECIFICATION** | [.planning/WEB-INTERFACE-SPECIFICATION.md](../.planning/WEB-INTERFACE-SPECIFICATION.md) | §4 Updates & Maintenance (lines 1196–1436), §4 Logs & Monitoring (lines 1587–1800+), §4 Modules (lines 1437–1586), §4 Dashboard (Recent Alerts, metrics) |
| **SYSTEM-ARCHITECTURE** | [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md) | §2 System Components (Update Manager, Logging Service, Monitor Service, Module Manager) |

---

## Phase 4a: Update, Logging, and Monitor

### 4a.1 Update Manager Service

**Spec**: [UPDATE-MAINTENANCE-SPECIFICATION](../.planning/UPDATE-MAINTENANCE-SPECIFICATION.md)

**Location**: `services/update_manager/`

**Responsibilities** (per spec §2 Update Mechanism):
- Check for available updates (git fetch/ls-remote)
- Download and stage updates
- Execute update procedure
- Perform rollback on failure
- Manage backup/restore
- Report status to API

**Implementation Details**:

| Feature | Spec Section | Implementation |
|---------|--------------|----------------|
| **Update Check** | §3 Update Check Process | `git ls-remote` to compare remote ref with `/etc/rpi-engineer/version` or `/var/lib/rpi-engineer/version`; return `current_version`, `update_available`, `available_version`, `release_notes` |
| **Pre-Flight Checks** | §4 Pre-Update Steps | WAN connectivity, disk space (2× update size), no critical services failed, optional warnings for active serial/captures |
| **Backup Before Update** | §4 Create Backup | Full config backup to `/var/lib/rpi-engineer/backups/pre-update-{timestamp}/`; must succeed before proceeding |
| **Update Procedure** | §4 Update Procedure | Stop services (API → managers → supporting), copy files to `/opt/rpi-engineer/`, update systemd units, run `bin/post-update.sh`, start services, verify health |
| **Rollback** | §5 Rollback Procedures | On post-update failure, service start failure, or health check failure: restore from backup, daemon-reload, start services |
| **Version Storage** | §3 Version Comparison | Semantic version or commit hash in version file; set during install and each update |

**Scripts to Create**:
- `bin/post-update.sh` – migrations, permission fixes, cleanup (per spec §4 Post-Update Script)
- `bin/rollback.sh` – manual rollback (per spec §5 Manual Rollback)

**Todos**:
- [ ] **phase4a-update-manager-service**: Implement Update Manager with check, apply, rollback, backup logic.
- [ ] **phase4a-update-api**: Wire to API gateway; replace stubs for `GET /api/v1/updates/check`, `POST /api/v1/updates/apply`, `POST /api/v1/updates/rollback`, `GET /api/v1/backup/config`, `POST /api/v1/backup/restore`.

---

### 4a.2 Logging Service

**Spec**: [LOGGING-MONITORING-SPECIFICATION](../.planning/LOGGING-MONITORING-SPECIFICATION.md)

**Location**: `services/logging_service/`

**Responsibilities** (per spec §2 Logging Architecture):
- Aggregate log entries from services (read from log files)
- Provide log viewing API
- Handle log export
- Manage log rotation coordination
- Filter and search support

**Log Destinations** (per spec §2):
```
/var/log/rpi-engineer/
├── api_gateway.log
├── network_manager.log
├── serial_manager.log
├── capture_manager.log
├── system_manager.log
├── update_manager.log
├── module_manager.log
├── remote_access.log
├── update.log
└── combined.log (optional)
```

**Implementation Details**:

| Feature | Spec Section | Implementation |
|---------|--------------|----------------|
| **Log Format** | §3 Log Levels and Format | Human-readable for files; JSON for API/export; structured format with timestamp, level, service, message, extra |
| **Rotation** | §4 Rotation and Retention | logrotate or Python handler; rotate at 10MB or daily; compress; retain 7 days default (configurable 1–30) |
| **Config** | §4 Configuration | `/etc/rpi-engineer/logging.conf` – retention days, max size, per-service levels |
| **List Logs** | §8 Log Viewing | `GET /api/v1/logs/system` – list files with name, size, modified |
| **Get Log Content** | §8 | `GET /api/v1/logs/system?file={name}&tail={n}` – query params: file, tail, level, service, since, search |
| **Export** | §8 Export | `GET /api/v1/logs/export?files=&since=` – ZIP archive download |

**Todos**:
- [ ] **phase4a-logging-service**: Implement Logging Service (read logs, filter, search, rotation coordination).
- [ ] **phase4a-logging-api**: Wire to API gateway; replace stubs for `GET /api/v1/logs/system`, `GET /api/v1/logs/export`.

---

### 4a.3 Monitor Service

**Spec**: [LOGGING-MONITORING-SPECIFICATION](../.planning/LOGGING-MONITORING-SPECIFICATION.md)

**Location**: `services/monitor_service/`

**Responsibilities** (per spec §5–7):
- Collect system metrics (CPU, RAM, disk, temperature, uptime)
- Collect network metrics (interface stats, WAN status)
- Collect service status
- Run health checks (services, connectivity, resources)
- Aggregate health status (Healthy, Degraded, Unhealthy, Unknown)
- Generate alerts for critical/warning/info conditions

**Implementation Details**:

| Feature | Spec Section | Implementation |
|---------|--------------|----------------|
| **Metrics** | §5 System Metrics | CPU %, memory %, disk %, temperature, uptime; collection interval 30s default (5–60s configurable); store in SQLite or in-memory buffer; 24h rolling |
| **Health Checks** | §6 Health Monitoring | Service health (process/API), WAN connectivity, disk >10% free, memory <90%, temp <80°C warning / <85°C critical |
| **Alerts** | §7 Alert Generation | Critical: API down, disk >95%, temp >85°C; Warning: WAN down, disk >90%, temp >80°C, memory >90%; Info: update available, failover, backup done |
| **Integration** | §10 Integration | Feed dashboard and status APIs; Network Manager provides WAN status |

**Todos**:
- [ ] **phase4a-monitor-service**: Implement Monitor Service (metrics collection, health checks, alert generation).
- [ ] **phase4a-monitor-integration**: Integrate with dashboard (Recent Alerts panel, metrics) and system status APIs.

---

### 4a.4 UI Integration for Phase 4a

**Spec**: [WEB-INTERFACE-SPECIFICATION](../.planning/WEB-INTERFACE-SPECIFICATION.md) §4

**Updates & Maintenance Page** (`/advanced/updates.html`, lines 1196–1436):
- Software Updates tab: current version, Check for Updates, Apply Update, Update process modal, Update history, Rollback
- Configuration Backup tab: Create Backup, Backup list, Restore modal
- Data Management tab: storage overview, captures/logs/backups management

**Logs & Monitoring Page** (`/advanced/logs.html`, lines 1587–1800+):
- System Logs tab: filter (level, service, time, search), log display, export
- Performance Metrics tab: CPU, memory, temperature, disk, network charts
- Alerts History tab: alerts list, severity, status, acknowledge

**Dashboard** (lines 400–455):
- Recent Alerts Panel: last 5 alerts, severity, message, link to logs
- Quick Actions: Check for Updates, View Full Logs

**Todos**:
- [ ] **phase4a-ui-updates-logs**: Wire Updates & Maintenance and Logs & Monitoring pages to Phase 4a APIs; ensure dashboard Recent Alerts and metrics work.

---

## Phase 4b: Module Manager

### 4b.1 Module Manager Core

**Spec**: [MODULE-SYSTEM-SPECIFICATION](../.planning/MODULE-SYSTEM-SPECIFICATION.md)

**Location**: `services/module_manager/`

**Responsibilities** (per spec §2 Module Architecture):
- Discover modules under `/opt/rpi-engineer/modules/`
- Load `module.json` metadata
- Manage lifecycle: install, uninstall, enable, disable
- Register module API routes with API Gateway
- Register module UI components with web interface
- Handle dependencies (system packages, Python packages, other modules)

**Key Functions** (per spec §2):
- `discover_modules()` – scan modules dir, load metadata
- `load_module(module_name)` – load and initialize
- `unload_module(module_name)` – unload
- `install_module(module_package)` – install from ZIP/tar.gz or URL
- `uninstall_module(module_name)` – remove
- `enable_module(module_name)` – enable (load on boot)
- `disable_module(module_name)` – disable
- `register_api_routes(module_name, routes)` – register with API Gateway
- `register_ui_components(module_name, components)` – register UI

**Module Structure** (per spec §3):
```
modules/module_name/
├── module.json       # Required
├── __init__.py       # Required
├── main.py           # Optional: initialize(), shutdown()
├── service.py        # Optional: background service
├── api.py            # Optional: register_routes(app)
├── config/
├── web/              # Optional: component.html, module.js, module.css
└── README.md
```

**Module States** (per spec §5): Not Installed → Installed → Enabled → Loaded; Disabled; Error

**Todos**:
- [ ] **phase4b-module-manager-core**: Implement Module Manager (discovery, lifecycle, registry, dependency handling).

---

### 4b.2 API Route Registration

**Spec**: [MODULE-SYSTEM-SPECIFICATION](../.planning/MODULE-SYSTEM-SPECIFICATION.md) §6

**Process**:
1. Module defines routes in `api.py` (Flask Blueprint)
2. Module exports `register_routes(app)`
3. Module Manager calls during load
4. Routes registered with API Gateway under `/api/v1/`
5. Use module name prefix (e.g. `/api/v1/display/`) to avoid conflicts

**API Helper Functions** (per spec §6):
- `get_module_config(module_name)`
- `update_module_config(module_name, config)`
- `get_module_status(module_name)`
- `emit_event(event_name, data)`
- `subscribe_event(event_name, callback)`

**Todos**:
- [ ] **phase4b-module-api-routes**: Implement API route registration; Module Manager loads module `api.py` and calls `register_routes(api_gateway_app)`.

---

### 4b.3 UI Component Registration

**Spec**: [MODULE-SYSTEM-SPECIFICATION](../.planning/MODULE-SYSTEM-SPECIFICATION.md) §7

**Process**:
1. Module declares `web_components` in `module.json` (name, path, menu, menu_order, icon)
2. Module Manager reads declaration and injects into web interface
3. Adds menu item to specified section (Dashboard, Network, System, Modules, etc.)
4. Component page accessible at defined path

**Menu Sections** (per spec §7): Dashboard, Network Management, Serial Console, Packet Capture, System Management, Modules (default), Custom

**Todos**:
- [ ] **phase4b-module-ui-registration**: Implement UI component registration; Module Manager injects menu items and serves module web assets.

---

### 4b.4 Module API Endpoints

**Spec**: [API-REFERENCE](../.planning/API-REFERENCE.md) §12

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/modules/list` | GET | List modules with id, name, version, enabled, description |
| `/api/v1/modules/install` | POST | Install from URL or upload; body: `module_url`, `module_id` |
| `/api/v1/modules/uninstall/{id}` | DELETE | Uninstall module |
| `/api/v1/modules/enable/{id}` | POST | Enable module (add if not in API-REFERENCE) |
| `/api/v1/modules/disable/{id}` | POST | Disable module (add if not in API-REFERENCE) |

**Todos**:
- [ ] **phase4b-module-api**: Wire Module Manager to API gateway; implement `modules/list`, `install`, `uninstall`, `enable`, `disable`.

---

### 4b.5 Example Module

**Spec**: [MODULE-SYSTEM-SPECIFICATION](../.planning/MODULE-SYSTEM-SPECIFICATION.md) §10 Example Modules

Create at least one example module to validate the contract. Recommended: **Display Driver** (Example 1) or a simpler **Hello World** module.

**Display Driver Example** (per spec §10):
- `module.json`: metadata, dependencies (i2c-tools, luma.oled), api_routes, web_components, config_schema
- `api.py`: GET/PUT `/api/v1/display`, GET `/api/v1/display/status`
- `web/component.html`: configuration form
- Optional: `service.py` for background display updates

**Minimal Example** (if Display Driver too complex for Phase 4):
- `module.json` with minimal fields
- `api.py` with one GET endpoint
- `web/component.html` with simple "Module loaded" message
- No system dependencies

**Todos**:
- [ ] **phase4b-example-module**: Create example module (Display Driver or minimal); validate discovery, load, API registration, UI registration, enable/disable.

---

### 4b.6 Modules Page UI

**Spec**: [WEB-INTERFACE-SPECIFICATION](../.planning/WEB-INTERFACE-SPECIFICATION.md) §4 Modules Page (lines 1437–1586)

**Installed Modules Tab**:
- Module cards: name, version, description, status (Enabled/Disabled/Error)
- Actions: Configure, Enable/Disable, Uninstall
- Module details modal, Configure modal, Uninstall confirmation

**Available Modules Tab**:
- Module catalog (if repository); search/filter
- Install from catalog or Upload Custom Module (ZIP/tar.gz)

**Todos**:
- [ ] **phase4b-modules-ui**: Wire Modules page (`/advanced/modules.html`) to Module Manager APIs.

---

## Exit Criteria

Per full implementation plan:

1. **Updates, logs, and monitoring** available via API and UI
2. **Module system** loads modules and registers routes/UI
3. **Example module** works end-to-end (discovery → install → enable → API/UI → disable → uninstall)

### Verification Steps

```bash
# 1. Update Manager
curl http://localhost:5000/api/v1/updates/check
# Returns current_version, update_available, etc.

# 2. Logging
curl "http://localhost:5000/api/v1/logs/system"
curl "http://localhost:5000/api/v1/logs/system?file=api_gateway.log&tail=50"

# 3. Monitor (via system status or dashboard)
# Dashboard shows metrics and Recent Alerts

# 4. Module Manager
curl http://localhost:5000/api/v1/modules/list
# Example module appears; enable/disable works; module API responds
```

---

## Todo Summary

| ID | Content | Status |
|----|---------|--------|
| phase4a-update-manager-service | Implement Update Manager service (check, apply, rollback, backup) per UPDATE-MAINTENANCE-SPECIFICATION | pending |
| phase4a-update-api | Wire Update Manager to API gateway (updates/check, apply, rollback) and backup endpoints | pending |
| phase4a-logging-service | Implement Logging Service (aggregation, viewing API, export) per LOGGING-MONITORING-SPECIFICATION | pending |
| phase4a-logging-api | Wire Logging Service to API gateway (logs/system, logs/export) | pending |
| phase4a-monitor-service | Implement Monitor Service (metrics, health checks, alerts) per LOGGING-MONITORING-SPECIFICATION | pending |
| phase4a-monitor-integration | Integrate Monitor Service with dashboard and status APIs | pending |
| phase4a-ui-updates-logs | Wire Updates & Maintenance and Logs & Monitoring pages to Phase 4a APIs | pending |
| phase4b-module-manager-core | Implement Module Manager core (discovery, lifecycle, registry) per MODULE-SYSTEM-SPECIFICATION | pending |
| phase4b-module-api-routes | Implement module API route registration with API Gateway | pending |
| phase4b-module-ui-registration | Implement module UI component registration for web interface | pending |
| phase4b-module-api | Wire Module Manager to API gateway (modules/list, install, uninstall, enable, disable) | pending |
| phase4b-example-module | Create at least one example module to validate the module contract | pending |
| phase4b-modules-ui | Wire Modules page to Module Manager APIs | pending |
| phase4-verify | Verify Phase 4 exit criteria (updates, logs, monitoring, module system, example module) | pending |

---

## Dependencies and Order

**Phase 4a** (sequential within 4a):
1. **phase4a-update-manager-service** → **phase4a-update-api**
2. **phase4a-logging-service** → **phase4a-logging-api**
3. **phase4a-monitor-service** → **phase4a-monitor-integration**
4. All 4a APIs → **phase4a-ui-updates-logs**

**Phase 4b** (sequential within 4b):
1. **phase4b-module-manager-core** → **phase4b-module-api-routes** → **phase4b-module-ui-registration**
2. **phase4b-module-manager-core** → **phase4b-module-api**
3. **phase4b-module-api** + **phase4b-module-ui-registration** → **phase4b-example-module**
4. **phase4b-module-api** → **phase4b-modules-ui**

**Cross-phase**:
- Phase 4a and 4b can proceed in parallel after Phase 3 (Web Interface) is complete
- **phase4-verify** depends on all Phase 4a and 4b todos

---

## Risks and Notes

- **Update Manager**: Requires root/elevated privileges for file copy and service control; install script or systemd handles this. Test on VM or RPi.
- **Module sandboxing**: Module failures must not crash core system; isolate module loading (try/except, separate process for services).
- **Example module complexity**: Prefer minimal example first; Display Driver requires I2C hardware.
- **Log rotation**: Coordinate with system logrotate or use Python RotatingFileHandler; ensure no rotation during active read.

---

## Related Documents

- [.planning/UPDATE-MAINTENANCE-SPECIFICATION.md](../.planning/UPDATE-MAINTENANCE-SPECIFICATION.md)
- [.planning/LOGGING-MONITORING-SPECIFICATION.md](../.planning/LOGGING-MONITORING-SPECIFICATION.md)
- [.planning/MODULE-SYSTEM-SPECIFICATION.md](../.planning/MODULE-SYSTEM-SPECIFICATION.md)
- [.planning/API-REFERENCE.md](../.planning/API-REFERENCE.md)
- [.planning/WEB-INTERFACE-SPECIFICATION.md](../.planning/WEB-INTERFACE-SPECIFICATION.md)
- [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md)
- [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md)

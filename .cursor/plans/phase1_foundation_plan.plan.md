---
name: Phase 1 Foundation Plan
overview: Detailed implementation plan for Phase 1 (Foundation) of RPi Engineer-in-a-Box. Establishes repo structure, API gateway skeleton, and install script framework per SYSTEM-ARCHITECTURE, DEVELOPMENT-GUIDE, API-REFERENCE, and INSTALLATION-SPECIFICATION.
parentPlan: full_implementation_plan_e49592f8.plan.md
todos:
  - id: phase1-repo-structure
    content: Create repository directory structure per SYSTEM-ARCHITECTURE and DEVELOPMENT-GUIDE
    status: pending
  - id: phase1-repo-files
    content: Add requirements.txt, requirements-dev.txt, .gitignore, minimal README
    status: pending
  - id: phase1-api-gateway-app
    content: Create Flask/FastAPI app with health check and CORS
    status: pending
  - id: phase1-api-routes
    content: Add stub route layout for all API groups per API-REFERENCE
    status: pending
  - id: phase1-install-script
    content: Create install.sh framework with pre-flight checks and placeholder stages
    status: pending
  - id: phase1-install-docs
    content: Document install.sh behavior in INSTALLATION-SPECIFICATION
    status: pending
  - id: phase1-verify
    content: Verify exit criteria (gateway runs, health check responds, install.sh passes pre-flight)
    status: pending
isProject: false
---

# Phase 1: Foundation – Detailed Implementation Plan

This plan implements the **Foundation** phase from [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md). It references the specification suite in [.planning/](../.planning/) in detail.

---

## Goal

Establish repo structure, API gateway skeleton, and install script framework so later work has a single entrypoint and a clear deploy path.

---

## Document References

| Document | Path | Relevant Sections |
|----------|------|-------------------|
| **SYSTEM-ARCHITECTURE** | [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md) | §6 File System Structure (lines 368–398), §2 System Components, §5 Component Interactions (API endpoints) |
| **DEVELOPMENT-GUIDE** | [.planning/DEVELOPMENT-GUIDE.md](../.planning/DEVELOPMENT-GUIDE.md) | §3 Repository Structure (lines 119–164), §4 Running Locally (lines 170–227), §5 Implementation Order Phase 1 (lines 233–249) |
| **API-REFERENCE** | [.planning/API-REFERENCE.md](../.planning/API-REFERENCE.md) | §2 Base URL, §3 Request/Response Format, §4 Error Handling, §5–13 All API groups |
| **INSTALLATION-SPECIFICATION** | [.planning/INSTALLATION-SPECIFICATION.md](../.planning/INSTALLATION-SPECIFICATION.md) | §4 Installation Script (lines 256–413), §3 Prerequisites (lines 148–198), §5 Setup Wizard (lines 358–458) |

---

## Deliverable 1: Repository Structure

### Spec References

- **SYSTEM-ARCHITECTURE** §6 File System Structure (lines 368–398): Target layout under `/opt/rpi-engineer/` with `bin/`, `services/`, `web/`, `modules/`, `config/`, `data/`, `logs/`, `lib/`.
- **DEVELOPMENT-GUIDE** §3 Repository Structure (lines 119–164): Dev layout with `services/`, `web/`, `lib/`, `tests/`, `config/`, `.planning/`.

### Target Structure (Development Repo)

Create the following under the project root:

```
rpi-engineer/
├── .planning/                 # (existing)
├── bin/                       # Executable scripts
│   └── install.sh            # Phase 1: framework only
├── config/                    # Default configs
│   └── system.conf.example
├── lib/                       # Shared libraries
│   ├── __init__.py
│   ├── common.py
│   ├── api_client.py
│   └── utils.py
├── services/                  # Backend services
│   ├── api_gateway/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   ├── network_manager/
│   │   └── __init__.py
│   ├── serial_manager/
│   │   └── __init__.py
│   ├── capture_manager/
│   │   └── __init__.py
│   ├── system_manager/
│   │   └── __init__.py
│   ├── update_manager/
│   │   └── __init__.py
│   ├── logging_service/
│   │   └── __init__.py
│   ├── monitor_service/
│   │   └── __init__.py
│   └── module_manager/
│       └── __init__.py
├── web/                       # Frontend (placeholder)
│   ├── index.html            # Minimal placeholder
│   ├── css/
│   ├── js/
│   └── docs/
├── tests/
│   ├── unit/
│   │   └── .gitkeep
│   └── integration/
│       └── .gitkeep
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── README.md
```

### Todos

- [ ] **phase1-repo-structure**: Create all directories and `__init__.py` / `.gitkeep` files.
- [ ] **phase1-repo-files**: Add `requirements.txt`, `requirements-dev.txt`, `.gitignore`, minimal README.

---

## Deliverable 2: API Gateway Skeleton

### Spec References

- **SYSTEM-ARCHITECTURE** §5 Component Interactions (lines 322–363): API endpoint structure under `/api/v1/`.
- **API-REFERENCE** §2 Base URL (`/api/v1/`), §3 Request/Response Format, §4 Error Handling.
- **DEVELOPMENT-GUIDE** §4 Running Locally (lines 172–196): Flask/FastAPI app, health check, stub routes.

### Requirements

1. **Framework**: Flask or FastAPI (per SYSTEM-ARCHITECTURE §3 Technology Stack).
2. **Health check**: `GET /api/v1/system/status` or `GET /health` returning `{"status": "healthy"}`.
3. **CORS**: Allow same-origin and hotspot subnet (192.168.50.0/24) per API-REFERENCE §15.
4. **Route layout**: Stub handlers for all API groups. Return mock data or `501 Not Implemented` as appropriate.

### API Groups to Stub (per API-REFERENCE)

| Group | Base Path | Endpoints to Stub |
|-------|-----------|-------------------|
| Network | `/api/v1/network/` | `interfaces`, `interfaces/{id}`, `routes`, `profiles`, `status` |
| Serial | `/api/v1/serial/` | `devices`, `devices/{id}`, `sessions`, `sessions/{id}`, `logs` |
| Capture | `/api/v1/capture/` | `interfaces`, `start`, `active`, `active/{id}`, `completed`, `completed/{id}`, `{id}/stats` |
| System | `/api/v1/system/` | `status`, `services`, `power`, `info` |
| Updates | `/api/v1/updates/` | `check`, `apply`, `rollback` |
| Backup | `/api/v1/backup/` | `config`, `restore` |
| Logs | `/api/v1/logs/` | `system`, `export` |
| Modules | `/api/v1/modules/` | `list`, `install`, `uninstall/{id}` |
| Remote | `/api/v1/remote/` | `status`, `info` |

### Response Format (per API-REFERENCE §3)

- Success: `{"data": {...}, "meta": {"timestamp": "..."}}`
- Error: `{"error": {"code": "ERROR_CODE", "message": "...", "details": {}}}`

### Todos

- [ ] **phase1-api-gateway-app**: Create `services/api_gateway/main.py` with Flask/FastAPI, health check, CORS.
- [ ] **phase1-api-routes**: Add route modules under `services/api_gateway/routes/` for each API group; stub handlers return mock or 501.

---

## Deliverable 3: Installation Script Framework

### Spec References

- **INSTALLATION-SPECIFICATION** §4 Installation Script (lines 256–413): Script structure, constants, utility functions, pre-flight checks.
- **INSTALLATION-SPECIFICATION** §3 Prerequisites (lines 148–198): OS, arch, disk, network requirements.
- **INSTALLATION-SPECIFICATION** §5 Setup Wizard (lines 358–458): Interactive prompts (remote access tool, hotspot password, hostname, modules).

### Requirements

1. **Location**: `install.sh` at repo root or under `bin/` (per DEVELOPMENT-GUIDE).
2. **Pre-flight checks** (per INSTALLATION-SPECIFICATION §4 Pre-Flight Checks):
   - Root privileges
   - OS detection (Ubuntu or Raspberry Pi OS / Debian)
   - Ubuntu 22.04+ or Debian Bookworm+ (Raspberry Pi OS)
   - Raspberry Pi model detection (optional continue on unsupported)
   - Disk space ≥ 8GB
   - Internet connectivity
3. **Interactive prompts** (minimal for Phase 1):
   - Remote access tool selection (AnyDesk/TeamViewer/VNC/Raspberry Pi Connect/Skip)
   - WiFi hotspot password
   - Hostname (optional)
4. **Placeholder stages** (no full implementation):
   - App install
   - Service setup
   - Module install
   - Remote access setup
5. **Utility functions**: `log_info`, `log_warn`, `log_error`, `log_step`, `check_root`, `detect_os`, `check_os_compatibility`, `detect_rpi`, `check_disk_space`, `check_internet`.

### Script Constants (per INSTALLATION-SPECIFICATION §4)

```bash
INSTALL_DIR="/opt/rpi-engineer"
CONFIG_DIR="/etc/rpi-engineer"
DATA_DIR="/var/lib/rpi-engineer"
LOG_DIR="/var/log/rpi-engineer"
SERVICE_USER="rpi-engineer"
MIN_UBUNTU_VERSION="22.04"
MIN_DEBIAN_VERSION="12"  # Bookworm (Raspberry Pi OS)
```

### Todos

- [ ] **phase1-install-script**: Create `bin/install.sh` (or root `install.sh`) with pre-flight checks, minimal prompts, placeholder stages.
- [ ] **phase1-install-docs**: Add or update section in INSTALLATION-SPECIFICATION documenting Phase 1 install.sh behavior (what runs, what is stubbed).

---

## Exit Criteria

Per full implementation plan:

1. **`python services/api_gateway/main.py`** runs without error.
2. **Health check** responds (e.g. `curl http://localhost:5000/api/v1/system/status` returns 200).
3. **`install.sh`** runs and passes pre-flight checks (on supported OS or with mocks).
4. **Directory layout** matches SYSTEM-ARCHITECTURE and DEVELOPMENT-GUIDE.

### Verification Steps

```bash
# 1. Run API gateway
cd rpi-engineer
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python services/api_gateway/main.py

# 2. Test health (in another terminal)
curl http://localhost:5000/api/v1/system/status

# 3. Run install script (Linux/WSL with sudo)
sudo ./bin/install.sh
# Should pass pre-flight; may exit or prompt before full install
```

---

## Todo Summary

| ID | Content | Status |
|----|---------|--------|
| phase1-repo-structure | Create repository directory structure per SYSTEM-ARCHITECTURE and DEVELOPMENT-GUIDE | pending |
| phase1-repo-files | Add requirements.txt, requirements-dev.txt, .gitignore, minimal README | pending |
| phase1-api-gateway-app | Create Flask/FastAPI app with health check and CORS | pending |
| phase1-api-routes | Add stub route layout for all API groups per API-REFERENCE | pending |
| phase1-install-script | Create install.sh framework with pre-flight checks and placeholder stages | pending |
| phase1-install-docs | Document install.sh behavior in INSTALLATION-SPECIFICATION | pending |
| phase1-verify | Verify exit criteria (gateway runs, health check responds, install.sh passes pre-flight) | pending |

---

## Dependencies and Order

1. **phase1-repo-structure** → **phase1-repo-files** (can be parallel)
2. **phase1-repo-files** → **phase1-api-gateway-app** → **phase1-api-routes**
3. **phase1-repo-structure** → **phase1-install-script** → **phase1-install-docs**
4. All above → **phase1-verify**

---

## Risks and Notes

- **Install script on Windows**: Pre-flight checks assume Linux (Ubuntu/Raspberry Pi OS); use WSL or skip on Windows.
- **API framework choice**: Flask is lighter; FastAPI adds async/OpenAPI. Either is acceptable per spec.
- **Stub responses**: Prefer minimal mock data over 501 where it helps UI development; 501 is fine for write endpoints.

---

## Related Documents

- [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md)
- [.planning/DEVELOPMENT-GUIDE.md](../.planning/DEVELOPMENT-GUIDE.md)
- [.planning/API-REFERENCE.md](../.planning/API-REFERENCE.md)
- [.planning/INSTALLATION-SPECIFICATION.md](../.planning/INSTALLATION-SPECIFICATION.md)
- [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md)

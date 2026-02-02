# Development Guide

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Development Environment Setup](#development-environment-setup)
3. [Repository Structure](#repository-structure)
4. [Running Locally](#running-locally)
5. [Implementation Order](#implementation-order)
6. [Coding Standards](#coding-standards)
7. [Testing During Development](#testing-during-development)
8. [Debugging](#debugging)
9. [Contributing Workflow](#contributing-workflow)

---

## Overview

### Purpose

This guide helps developers set up a development environment and implement the RPi Engineer-in-a-Box platform. It covers environment setup, project structure, running components locally, and development workflow.

### Prerequisites

**Knowledge**:
- Python 3.10+
- REST APIs and WebSocket
- Linux system administration (for full deployment)
- Basic network concepts

**Tools**:
- Git
- Python 3.10 or later
- Code editor (VS Code, etc.)
- Optional: Docker for isolated testing

---

## Development Environment Setup

### Supported Development Hosts

**Primary**: Ubuntu 22.04+ or Raspberry Pi OS (matches target deployment; both Debian-based)

**Alternative**: Windows with WSL2, macOS (some features may differ)

### Python Environment

**1. Install Python 3.10+**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# Verify
python3 --version  # Should be 3.10 or higher
```

**2. Create Virtual Environment**:
```bash
cd rpi-engineer
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
```

**3. Install Dependencies**:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing, linting
```

### Required System Packages (Ubuntu / Raspberry Pi OS)

```bash
# For network management development
sudo apt install iproute2 net-tools

# For packet capture
sudo apt install tcpdump tshark

# For serial (optional, for full testing)
sudo apt install python3-serial

# For USB device detection
sudo apt install libudev-dev
pip install pyudev
```

### IDE Setup

**VS Code Recommendations**:
- Python extension
- Pylance
- REST Client (for API testing)
- GitLens (optional)

**Settings** (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black"
  }
}
```

---

## Repository Structure

### Target Structure (When Implemented)

```
rpi-engineer/
├── .planning/                 # Specifications (this folder)
│   ├── README.md
│   ├── PROJECT-OVERVIEW.md
│   ├── SYSTEM-ARCHITECTURE.md
│   ├── INSTALLATION-SPECIFICATION.md
│   ├── DEVELOPMENT-GUIDE.md
│   ├── API-REFERENCE.md
│   └── [other specs]
├── install.sh                 # Installation script
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── services/                  # Backend services
│   ├── api_gateway/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── routes/
│   ├── network_manager/
│   ├── serial_manager/
│   ├── capture_manager/
│   ├── system_manager/
│   ├── update_manager/
│   └── module_manager/
├── web/                       # Frontend
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── docs/
├── lib/                       # Shared libraries
│   ├── common.py
│   └── utils.py
├── tests/
│   ├── unit/
│   └── integration/
├── config/                    # Default configs
│   └── system.conf.example
└── docs/                      # Additional docs
```

### Current State

**Specification Phase**: Repository contains `.planning/` with specifications. Implementation creates the above structure.

---

## Running Locally

### Minimal Setup (API Gateway Only)

**For Early Development**:
1. Create `services/api_gateway/main.py` with Flask/FastAPI
2. Define stub routes that return mock data
3. Run: `python services/api_gateway/main.py`
4. Access: http://localhost:5000/api/v1/system/status

### With Mock Services

**Strategy**: Implement API Gateway first with mock responses. Replace mocks with real services incrementally.

```python
# Example: Mock network interfaces
@app.get("/api/v1/network/interfaces")
def get_interfaces():
    return {
        "data": {
            "interfaces": [
                {"id": "eth0", "name": "eth0", "status": "up"},
                {"id": "wlan0", "name": "wlan0", "status": "up"}
            ]
        }
    }
```

### Full Stack (Target Hardware)

**On Raspberry Pi**:
1. Clone repo to Pi
2. Run install script (or manual setup per INSTALLATION-SPECIFICATION)
3. Access via http://192.168.50.1 (after hotspot configured)

### Frontend Development

**Option 1**: Serve static files
```bash
cd web
python -m http.server 8080
# Access http://localhost:8080
# Configure API base URL to point to backend
```

**Option 2**: Use backend to serve (when integrated)
- Backend serves `/` and `/web/*`
- Single origin, no CORS issues

### Environment Variables

**Development**:
```
RPI_ENGINEER_ENV=development
RPI_ENGINEER_DEBUG=1
RPI_ENGINEER_API_HOST=0.0.0.0
RPI_ENGINEER_API_PORT=5000
```

**Config File**: `config/development.conf`

---

## Implementation Order

### Phase 1: Foundation (Weeks 1-2)

1. **Repository Setup**
   - Create directory structure
   - Add requirements.txt, .gitignore
   - Basic README

2. **API Gateway Skeleton**
   - Flask or FastAPI app
   - Health check endpoint
   - CORS configuration
   - Route structure for all API groups

3. **Installation Script Framework**
   - install.sh with pre-flight checks
   - Placeholder for full installation
   - Document in INSTALLATION-SPECIFICATION

### Phase 2: Core Services (Weeks 3-8)

**Recommended Order**:
1. **System Manager** - Status, info, power (simplest)
2. **Network Manager** - Interfaces, status (critical path)
3. **API Gateway** - Wire up System and Network
4. **Web Interface** - Simple mode landing page
5. **Remote Access Manager** - Integration with AnyDesk/TeamViewer
6. **Serial Manager** - Device detection, sessions
7. **Capture Manager** - Basic capture with tcpdump

### Phase 3: Integration (Weeks 9-12)

1. **Web Interface** - All pages, Advanced mode
2. **Update Manager** - Check, apply, rollback
3. **Logging Service** - Centralized logs
4. **Module Manager** - Basic module loading

### Phase 4: Polish (Weeks 13+)

1. Testing and bug fixes
2. Performance optimization
3. Documentation completion
4. Deployment preparation

---

## Coding Standards

### Python Style

**Formatter**: Black (line length 100)

**Linter**: flake8, pylint, or ruff

**Type Hints**: Use for public APIs

```python
def get_interface(id: str) -> Optional[dict]:
    """Get network interface by ID."""
    ...
```

### Naming Conventions

- **Files**: snake_case (`network_manager.py`)
- **Classes**: PascalCase (`NetworkManager`)
- **Functions**: snake_case (`get_interfaces`)
- **Constants**: UPPER_SNAKE (`DEFAULT_PORT`)

### Documentation

- Module docstring: Purpose
- Function docstring: Purpose, args, returns, raises
- Complex logic: Inline comments explaining why

### Error Handling

- Use specific exceptions
- Log errors with context
- Return meaningful API error responses
- Never expose stack traces to API clients

---

## Testing During Development

### Unit Tests

```bash
pytest tests/unit/ -v
pytest tests/unit/ -v --cov=services
```

### Integration Tests

```bash
pytest tests/integration/ -v -m integration
```

### Manual API Testing

**Using curl**:
```bash
curl http://localhost:5000/api/v1/system/status
```

**Using REST Client (VS Code)**: Create `.http` files for requests

### Test Data

- Use fixtures in `tests/fixtures/`
- Mock hardware (serial, network) for CI
- Use loopback interface for capture tests

---

## Debugging

### Logging

**Development**: Set log level to DEBUG

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Structured Logging**:
```python
logger.info("Interface updated", extra={"interface": "eth0", "status": "up"})
```

### API Debugging

- Enable Flask/FastAPI debug mode (development only)
- Use browser DevTools Network tab
- Check API Gateway logs for request/response

### Service Debugging

- Run services in foreground (not as systemd)
- Use `print()` or debugger for quick checks
- Use `pdb` or IDE debugger for breakpoints

### Common Issues

**Import Errors**: Ensure PYTHONPATH includes project root, or run from project root

**Permission Denied**: Serial, network ops may need root or group membership

**Port in Use**: Change port in config or stop conflicting service

---

## Contributing Workflow

### Branch Strategy

- `main`: Stable, release-ready
- `develop`: Integration branch (optional)
- `feature/xxx`: Feature branches
- `fix/xxx`: Bug fix branches

### Commit Messages

```
feat: Add network interface list endpoint
fix: Correct serial device detection on hotplug
docs: Update API reference for capture API
```

### Pull Request Process

1. Create branch from main
2. Implement with tests
3. Run full test suite
4. Update documentation if needed
5. Submit PR with description
6. Address review feedback
7. Merge after approval

### Pre-Commit Hooks (Recommended)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/ -x
        language: system
      - id: black
        name: black
        entry: black --check .
        language: system
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial development guide |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- INSTALLATION-SPECIFICATION.md
- API-REFERENCE.md
- TESTING-VALIDATION-SPECIFICATION.md

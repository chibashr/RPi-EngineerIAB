# RPi Engineer-in-a-Box Tests

Tests for the API gateway, services, and web interface. Run from the project root.

## Quick Start

```bash
# From project root
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

## Test Structure

| Directory | Purpose |
|-----------|---------|
| `unit/` | Unit tests for response helpers, BPF parsing, API routes |
| `integration/` | Integration tests for full API and static file serving |

## Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Verbose with output
pytest -v

# Specific test file
pytest tests/unit/test_api_system.py

# Specific test class
pytest tests/unit/test_api_system.py::TestSystemStatus
```

## Environment

Tests run with `RPI_ENGINEER_DRY_RUN=1` (set automatically via `conftest.py`). This prevents:

- System commands (systemctl, poweroff, reboot)
- Network interface changes
- Real tcpdump/serial operations

## Requirements

- Python 3.10+
- Dependencies from `requirements.txt` and `requirements-dev.txt`
- No Raspberry Pi or special hardware required; tests use mocks/fallbacks where needed

## Optional

- **bash** (for install script syntax test): On Windows, the install script syntax check may be skipped if bash cannot run the script (e.g. Windows paths). Run tests from WSL for full validation.

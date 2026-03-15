# RPi Engineer-in-a-Box Tests

Comprehensive test suite for the API gateway, services, and web interface.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt
npm ci

# Run all Python tests
pytest

# Run JavaScript tests
npm test
```

## Test Structure

| Directory | Purpose |
|-----------|---------|
| `unit/` | Unit tests for response helpers, BPF parsing, API routes, services |
| `integration/` | Integration tests for full API, static file serving, serial WebSocket |
| `ui/` | HTML consistency tests |
| `system/` | Manual system test checklist for hardware |
| `docker/` | Docker-based test environments |
| `scripts/` | Manual test scripts (e.g. serial connection) |
| `fixtures/` | Test data files (network profiles, serial logs) |

## Running Tests

### Python Tests (pytest)

```bash
# All tests
pytest

# Unit tests only (fast)
pytest tests/unit/ -m "not slow"

# Integration tests only
pytest tests/integration/

# With coverage report
pytest tests/unit/ --cov=services --cov=lib --cov-report=term-missing

# Exclude hardware-dependent tests
pytest -m "not hardware"

# Specific test file
pytest tests/unit/test_api_system.py

# Specific test class
pytest tests/unit/test_api_system.py::TestSystemStatus
```

### JavaScript Tests (Jest)

```bash
# Run all JS tests
npm test

# Watch mode
npm run test:watch

# With coverage
npm run test:coverage
```

### Docker-based Tests

```bash
# Full test suite in container
docker-compose -f tests/docker/docker-compose.yml run test-runner

# Unit tests only
docker-compose -f tests/docker/docker-compose.yml run test-unit

# Integration tests only
docker-compose -f tests/docker/docker-compose.yml run test-integration

# JavaScript tests
docker-compose -f tests/docker/docker-compose.yml run test-js

# Linting
docker-compose -f tests/docker/docker-compose.yml run lint

# Installation test (Ubuntu)
docker-compose -f tests/docker/docker-compose.yml run install-test-ubuntu

# Installation test (Debian Trixie)
docker-compose -f tests/docker/docker-compose.yml run install-test-trixie
```

### PowerShell (Windows)

```powershell
# Build and run tests in Docker
.\tests\docker\run-tests.ps1
```

## Test Markers

Tests are organized with pytest markers:

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Fast, isolated unit tests |
| `@pytest.mark.integration` | Tests requiring service interactions |
| `@pytest.mark.slow` | Long-running tests |
| `@pytest.mark.hardware` | Tests requiring physical hardware |
| `@pytest.mark.e2e` | End-to-end tests |

```bash
# Run only unit tests
pytest -m unit

# Run everything except slow tests
pytest -m "not slow"

# Run everything except hardware tests
pytest -m "not hardware"
```

## Serial Connection Testing

### Mocked (no hardware)

```bash
pytest tests/integration/test_serial_websocket.py -v
```

The integration suite includes:

| Test | Verifies |
|------|----------|
| `test_serial_tx_accuracy` | Data sent via WebSocket is correctly written to the serial port |
| `test_serial_rx_accuracy` | Data injected into the mock port is received via WebSocket |
| `test_serial_tx_rx_roundtrip` | Full loop: send → mock echoes → receive (simulates device echo) |

### Real Hardware

```bash
# Option A: script starts API and tests
python tests/scripts/test_serial_connection.py --serve --device COM3

# Option B: API already running
python services/api_gateway/main.py   # terminal 1
python tests/scripts/test_serial_connection.py --device COM3  # terminal 2
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RPI_ENGINEER_DRY_RUN` | `1` (tests) | Prevents real system commands |
| `RPI_ENGINEER_TEST_MODE` | - | Enables test mode behaviors |

`RPI_ENGINEER_DRY_RUN=1` is set automatically via `conftest.py`. This prevents:

- System commands (systemctl, poweroff, reboot)
- Network interface changes
- Real tcpdump/serial operations

## Setup

Run the setup script to install all test dependencies:

```bash
# Linux/macOS (from tests/ folder)
./setup-test-env.sh

# Windows PowerShell (from tests/ folder)
.\setup-test-env.ps1
```

Or use Make (from tests/ folder):

```bash
make install-dev
make setup-hooks
```

## CI/CD Integration

The project includes GitHub Actions workflows (`.github/workflows/ci.yml`):

- **Lint**: Ruff and Black formatting checks
- **Python Tests**: Unit and integration tests with coverage
- **JavaScript Tests**: Jest tests
- **UI Tests**: HTML consistency checks
- **Docker Tests**: Full suite in container
- **Installation Tests**: Verify install script (on PRs)

## Pre-commit Hooks

Install pre-commit hooks for automatic code quality checks:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

Hooks include:
- Trailing whitespace removal
- YAML/JSON validation
- Ruff linting with auto-fix
- Black formatting
- Unit tests on pre-push

## Coverage Requirements

| Area | Minimum Coverage |
|------|------------------|
| `services/` | 60% |
| `lib/` | 60% |
| `modules/` | 60% |

Run coverage report:

```bash
pytest tests/unit/ --cov=services --cov=lib --cov=modules \
  --cov-report=term-missing --cov-fail-under=60
```

## Fixtures

Common test fixtures are defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `app` | FastAPI application instance |
| `client` | Test client with Flask compatibility |
| `api_client` | Alias for client |
| `temp_dir` | Temporary directory for test artifacts |
| `temp_file` | Temporary file with test content |
| `mock_subprocess` | Mocked subprocess.run |
| `mock_serial_port` | Mocked serial port |
| `sample_network_profile` | Network profile from fixtures |
| `sample_serial_log` | Serial log from fixtures |
| `mock_system_info` | Consistent system info for tests |
| `mock_websocket` | Mocked WebSocket connection |
| `capture_logs` | Log capture for assertions |

## Requirements

- Python 3.10+
- Node.js 20+
- Dependencies from `requirements.txt` and `requirements-dev.txt`
- No Raspberry Pi or special hardware required; tests use mocks where needed

### Platform Notes

- **Windows**: Use WSL or Docker for full test coverage (bash scripts)
- **Linux**: Full native support
- **macOS**: Full native support (may need `brew install socat` for serial tests)

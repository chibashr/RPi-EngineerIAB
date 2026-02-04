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
| `integration/` | Integration tests for full API, static file serving, serial WebSocket |
| `scripts/` | Manual test scripts (e.g. serial connection) |

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

# Serial WebSocket integration (mocked serial port)
pytest tests/integration/test_serial_websocket.py -v
```

## Serial Connection Testing

### Automated Tx/Rx test (no hardware)

An echo-loopback test verifies both transmit and receive paths:

```bash
pytest tests/integration/test_serial_websocket.py::test_serial_tx_and_rx_echo_loopback -v
```

Uses `EchoMockSerialPort`: data written to the mock is echoed back to `read()`, so the test sends via WebSocket, the backend writes to serial, the mock echoes, the backend reads and forwards to WebSocket, and the test verifies the received data matches.

### All serial WebSocket tests (mocked)

```bash
pytest tests/integration/test_serial_websocket.py -v
```

### Manual test with real hardware

```bash
# Option A: script starts API and tests (replace COM3 with your device)
python tests/scripts/test_serial_connection.py --serve --device COM3

# Option B: API already running in another terminal
python services/api_gateway/main.py   # terminal 1
python tests/scripts/test_serial_connection.py --device COM3  # terminal 2
```

For Rx verification with real hardware: use a loopback (TX and RX shorted) or a device that echoes (e.g. a router console).

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

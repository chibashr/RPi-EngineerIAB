"""Pytest fixtures for RPi Engineer-in-a-Box tests."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _dry_run_env(monkeypatch):
    """Set RPI_ENGINEER_DRY_RUN=1 for all tests to avoid system commands."""
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "1")


@pytest.fixture
def app():
    """Create FastAPI application for testing."""
    from services.api_gateway.main import create_app

    return create_app()


class _CompatClient:
    """Wraps TestClient to add get_json() for Flask test_client compatibility."""

    def __init__(self, tc):
        self._client = tc

    def _wrap(self, r):
        if r is None:
            return r
        if not hasattr(r, "get_json"):
            r.get_json = lambda: r.json()
        if not hasattr(r, "data"):
            r.data = r.content
        if not hasattr(r, "content_type"):
            r.content_type = r.headers.get("content-type", "")
        return r

    def get(self, *a, **kw):
        return self._wrap(self._client.get(*a, **kw))

    def post(self, *a, **kw):
        return self._wrap(self._client.post(*a, **kw))

    def put(self, *a, **kw):
        return self._wrap(self._client.put(*a, **kw))

    def delete(self, *a, **kw):
        return self._wrap(self._client.delete(*a, **kw))

    def patch(self, *a, **kw):
        return self._wrap(self._client.patch(*a, **kw))


@pytest.fixture
def client(app):
    """Create FastAPI test client with get_json() compatibility."""
    from fastapi.testclient import TestClient

    return _CompatClient(TestClient(app))


@pytest.fixture
def api_client(client):
    """Test client with JSON headers for API requests."""
    return client


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file and return its path."""
    filepath = temp_dir / "test_file.txt"
    filepath.write_text("test content")
    return filepath


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for testing commands without execution."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_serial_port():
    """Mock serial port for testing serial communication."""
    mock_port = MagicMock()
    mock_port.name = "/dev/ttyUSB0"
    mock_port.baudrate = 115200
    mock_port.is_open = True
    mock_port.read.return_value = b""
    mock_port.write.return_value = 0
    return mock_port


@pytest.fixture
def sample_network_profile():
    """Load sample network profile from fixtures."""
    profile_path = FIXTURES_DIR / "network_profile.json"
    if profile_path.exists():
        return json.loads(profile_path.read_text())
    return {
        "name": "test_profile",
        "interfaces": [
            {
                "name": "eth0",
                "type": "ethernet",
                "dhcp": True,
            }
        ],
    }


@pytest.fixture
def sample_serial_log():
    """Load sample serial log from fixtures."""
    log_path = FIXTURES_DIR / "serial_log_sample.txt"
    if log_path.exists():
        return log_path.read_text()
    return "Sample serial log content\n"


@pytest.fixture
def mock_system_info():
    """Mock system information for consistent testing."""
    return {
        "hostname": "test-rpi",
        "version": "1.0.0-test",
        "os": "Ubuntu 22.04",
        "cpu_percent": 25.0,
        "memory_percent": 45.0,
        "disk_percent": 60.0,
        "uptime": 3600,
    }


@pytest.fixture
def clean_env(monkeypatch):
    """Provide a clean environment with minimal env vars."""
    env_vars_to_keep = {"PATH", "HOME", "USER", "LANG", "RPI_ENGINEER_DRY_RUN"}
    for key in list(os.environ.keys()):
        if key not in env_vars_to_keep:
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection for testing."""
    ws = MagicMock()
    ws.send_text = MagicMock()
    ws.receive_text = MagicMock(return_value="test message")
    ws.close = MagicMock()
    ws.accept = MagicMock()
    return ws


@pytest.fixture
def capture_logs(caplog):
    """Capture and return log messages for assertion."""
    import logging

    caplog.set_level(logging.DEBUG)
    yield caplog
    return caplog.records

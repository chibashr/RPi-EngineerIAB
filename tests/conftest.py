"""Pytest fixtures for RPi Engineer-in-a-Box tests."""

import sys
from pathlib import Path

import pytest

# Ensure project root is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _dry_run_env(monkeypatch):
    """Set RPI_ENGINEER_DRY_RUN=1 for all tests to avoid system commands."""
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "1")


@pytest.fixture
def app():
    """Create Flask application for testing."""
    from services.api_gateway.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def api_client(client):
    """Test client with JSON headers for API requests."""
    return client

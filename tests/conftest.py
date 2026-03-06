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
        # Flask compatibility: .data (bytes), .content_type
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

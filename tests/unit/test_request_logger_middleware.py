"""Unit tests for RequestLoggerMiddleware."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

from services.api_gateway.middleware.request_logger import RequestLoggerMiddleware


def _make_app():
    """Minimal FastAPI app with RequestLoggerMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(RequestLoggerMiddleware)

    @app.get("/api/v1/test")
    def test_route():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/error500")
    def error_500():
        raise RuntimeError("Intentional server error")

    @app.get("/api/v1/notfound")
    def not_found():
        return Response(status_code=404)

    return app


@pytest.fixture
def middleware_client():
    """Test client with minimal app using RequestLoggerMiddleware."""
    return TestClient(_make_app(), raise_server_exceptions=False)


@pytest.mark.unit
def test_api_request_is_logged(middleware_client, caplog):
    """GET /api/v1/test should produce a log record with method, path, status."""
    with caplog.at_level(logging.INFO):
        r = middleware_client.get("/api/v1/test")
    assert r.status_code == 200
    assert any(
        "GET" in rec.message and "/api/v1/test" in rec.message and "200" in rec.message
        for rec in caplog.records
    )


@pytest.mark.unit
def test_health_not_logged(middleware_client, caplog):
    """GET /health should not produce a request log record from RequestLoggerMiddleware."""
    with caplog.at_level(logging.INFO):
        r = middleware_client.get("/health")
    assert r.status_code == 200
    # Only check for logs from our middleware (exclude httpx, etc.)
    middleware_logs = [
        rec for rec in caplog.records
        if "request_logger" in rec.name and "/health" in rec.message
    ]
    assert len(middleware_logs) == 0


@pytest.mark.unit
def test_5xx_logged_as_error(middleware_client, caplog):
    """Route that raises should produce ERROR level log."""
    with caplog.at_level(logging.ERROR):
        r = middleware_client.get("/api/v1/error500")
    assert r.status_code == 500
    assert any(rec.levelname == "ERROR" for rec in caplog.records)


@pytest.mark.unit
def test_4xx_logged_as_warning(middleware_client, caplog):
    """Route returning 404 should produce WARNING level log."""
    with caplog.at_level(logging.WARNING):
        r = middleware_client.get("/api/v1/notfound")
    assert r.status_code == 404
    assert any(rec.levelname == "WARNING" for rec in caplog.records)


@pytest.mark.unit
def test_duration_present_in_log(middleware_client, caplog):
    """Log message should contain 'ms' duration value."""
    with caplog.at_level(logging.INFO):
        middleware_client.get("/api/v1/test")
    assert any("ms" in rec.message for rec in caplog.records)

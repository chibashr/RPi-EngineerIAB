"""Unit tests for Serial API routes."""

from __future__ import annotations

import pytest


class TestSerialDevices:
    """Tests for GET /api/v1/serial/devices."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/serial/devices")
        assert r.status_code == 200

    def test_returns_devices_list(self, client):
        r = client.get("/api/v1/serial/devices")
        data = r.get_json()
        assert "data" in data
        assert "devices" in data["data"]


class TestSerialSessions:
    """Tests for GET /api/v1/serial/sessions."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/serial/sessions")
        assert r.status_code == 200

    def test_returns_sessions_list(self, client):
        r = client.get("/api/v1/serial/sessions")
        data = r.get_json()
        assert "data" in data
        assert "sessions" in data["data"]


class TestSerialCreateSession:
    """Tests for POST /api/v1/serial/sessions."""

    def test_missing_device_returns_400(self, client):
        r = client.post(
            "/api/v1/serial/sessions",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_invalid_device_returns_404(self, client):
        r = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyNONEXISTENT"},
            content_type="application/json",
        )
        assert r.status_code == 404


class TestSerialLogs:
    """Tests for GET /api/v1/serial/logs."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/serial/logs")
        assert r.status_code == 200

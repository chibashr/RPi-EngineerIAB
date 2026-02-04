"""Unit tests for Serial API routes."""

from __future__ import annotations

import pytest


class TestSerialUpdateDevice:
    """Tests for PUT /api/v1/serial/devices/<device_id>."""

    def test_update_device_applies_config(self, client, monkeypatch):
        """Device config is saved and returned."""
        from services import serial_manager

        def fake_scan():
            return [
                {
                    "id": "COM3",
                    "path": "COM3",
                    "friendly_name": "FTDI",
                    "chipset": "FTDI",
                }
            ]

        monkeypatch.setattr(
            serial_manager.serial_manager,
            "_scan_devices",
            fake_scan,
        )
        r = client.put(
            "/api/v1/serial/devices/COM3",
            json={"baud_rate": 115200, "friendly_name": "Router Console"},
            content_type="application/json",
        )
        assert r.status_code == 200
        data = r.get_json()
        assert "data" in data
        assert data["data"]["config"]["baud_rate"] == 115200
        assert data["data"]["config"]["friendly_name"] == "Router Console"

    def test_update_device_not_found_returns_404(self, client, monkeypatch):
        def fake_scan():
            return []

        from services import serial_manager

        monkeypatch.setattr(
            serial_manager.serial_manager,
            "_scan_devices",
            fake_scan,
        )
        r = client.put(
            "/api/v1/serial/devices/COM99",
            json={"baud_rate": 115200},
            content_type="application/json",
        )
        assert r.status_code == 404


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


class TestSerialRenameLog:
    """Tests for PUT /api/v1/serial/logs/<log_id>."""

    def test_missing_name_returns_400(self, client):
        r = client.put(
            "/api/v1/serial/logs/nonexistent",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_nonexistent_log_returns_404(self, client):
        r = client.put(
            "/api/v1/serial/logs/nonexistent",
            json={"name": "My Log"},
            content_type="application/json",
        )
        assert r.status_code == 404

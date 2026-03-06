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
        )
        assert r.status_code == 200
        data = r.json()
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
        )
        assert r.status_code == 404

    def test_update_device_via_configure_endpoint(self, client, monkeypatch):
        """PUT /devices/configure with device_id in body works for paths like /dev/ttyUSB1."""
        from services import serial_manager

        def fake_scan():
            return [
                {
                    "id": "/dev/ttyUSB1",
                    "path": "/dev/ttyUSB1",
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
            "/api/v1/serial/devices/configure",
            json={
                "device_id": "/dev/ttyUSB1",
                "baud_rate": 115200,
                "friendly_name": "Console",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["data"]["config"]["baud_rate"] == 115200
        assert data["data"]["config"]["friendly_name"] == "Console"


class TestSerialDevices:
    """Tests for GET /api/v1/serial/devices."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/serial/devices")
        assert r.status_code == 200

    def test_returns_devices_list(self, client):
        r = client.get("/api/v1/serial/devices")
        data = r.json()
        assert "data" in data
        assert "devices" in data["data"]


class TestSerialSessions:
    """Tests for GET /api/v1/serial/sessions."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/serial/sessions")
        assert r.status_code == 200

    def test_returns_sessions_list(self, client):
        r = client.get("/api/v1/serial/sessions")
        data = r.json()
        assert "data" in data
        assert "sessions" in data["data"]


class TestSerialCreateSession:
    """Tests for POST /api/v1/serial/sessions."""

    def test_missing_device_returns_400(self, client):
        r = client.post(
            "/api/v1/serial/sessions",
            json={},
        )
        assert r.status_code == 400

    def test_invalid_device_returns_404(self, client):
        r = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyNONEXISTENT"},
        )
        assert r.status_code == 404

    def test_multiple_sessions_across_devices_allowed(self, client, monkeypatch, tmp_path):
        """Sessions for different devices can coexist."""
        from services.serial_manager import manager as serial_manager_mod
        from services import serial_manager

        def fake_scan(use_cache=True):  # noqa: ARG001
            return [
                {"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "A", "chipset": "FTDI"},
                {"id": "/dev/ttyUSB1", "path": "/dev/ttyUSB1", "friendly_name": "B", "chipset": "FTDI"},
            ]

        monkeypatch.setattr(serial_manager.serial_manager, "_scan_devices", fake_scan)
        monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)
        monkeypatch.setattr(serial_manager_mod, "serial", __import__("types").SimpleNamespace())

        serial_manager.serial_manager._sessions.clear()

        r1 = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyUSB0", "config": {}},
        )
        assert r1.status_code in (200, 201)

        r2 = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyUSB1", "config": {}},
        )
        assert r2.status_code in (200, 201)

        r_list = client.get("/api/v1/serial/sessions")
        assert r_list.status_code == 200
        sessions = (r_list.json() or {}).get("data", {}).get("sessions", [])
        device_ids = {s.get("device_id") for s in sessions}
        assert {"/dev/ttyUSB0", "/dev/ttyUSB1"}.issubset(device_ids)

    def test_second_session_same_device_returns_500(self, client, monkeypatch, tmp_path):
        """Second session for same device returns error."""
        from services.serial_manager import manager as serial_manager_mod
        from services import serial_manager

        def fake_scan(use_cache=True):  # noqa: ARG001
            return [
                {"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "A", "chipset": "FTDI"},
            ]

        monkeypatch.setattr(serial_manager.serial_manager, "_scan_devices", fake_scan)
        monkeypatch.setattr(serial_manager_mod, "LOG_DIR", tmp_path)
        monkeypatch.setattr(serial_manager_mod, "serial", __import__("types").SimpleNamespace())

        serial_manager.serial_manager._sessions.clear()

        r1 = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyUSB0", "config": {}},
        )
        assert r1.status_code in (200, 201)

        r2 = client.post(
            "/api/v1/serial/sessions",
            json={"device_id": "/dev/ttyUSB0", "config": {}},
        )
        assert r2.status_code == 500
        assert "Device already in use" in (r2.json() or {}).get("error", {}).get("message", "")


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
        )
        assert r.status_code == 400

    def test_nonexistent_log_returns_404(self, client):
        r = client.put(
            "/api/v1/serial/logs/nonexistent",
            json={"name": "My Log"},
        )
        assert r.status_code == 404


class TestSerialGetDevice:
    """Tests for GET /api/v1/serial/devices/<device_id>."""

    def test_unknown_device_returns_404(self, client, monkeypatch):
        from services import serial_manager

        monkeypatch.setattr(
            serial_manager.serial_manager, "_scan_devices", lambda **kw: []
        )
        r = client.get("/api/v1/serial/devices/COM99")
        assert r.status_code == 404


class TestSerialTestDevice:
    """Tests for POST /api/v1/serial/devices/<device_id>/test."""

    def test_unknown_device_returns_404(self, client, monkeypatch):
        from services import serial_manager

        monkeypatch.setattr(
            serial_manager.serial_manager, "_scan_devices", lambda **kw: []
        )
        r = client.post("/api/v1/serial/devices/COM99/test")
        assert r.status_code == 404


class TestSerialSessionById:
    """Tests for session by ID endpoints."""

    def test_get_session_404(self, client):
        r = client.get("/api/v1/serial/sessions/nonexistent-session-id")
        assert r.status_code == 404

    def test_update_session_404(self, client):
        r = client.put(
            "/api/v1/serial/sessions/nonexistent-session-id",
            json={"baud_rate": 9600},
        )
        assert r.status_code == 404

    def test_delete_session_404(self, client):
        r = client.delete("/api/v1/serial/sessions/nonexistent-session-id")
        assert r.status_code == 404


class TestSerialLogContent:
    """Tests for GET /api/v1/serial/logs/<log_id>/content."""

    def test_log_content_404(self, client):
        r = client.get("/api/v1/serial/logs/nonexistent/content")
        assert r.status_code == 404


class TestSerialDeleteLog:
    """Tests for DELETE /api/v1/serial/logs/<log_id>."""

    def test_delete_log_404(self, client):
        r = client.delete("/api/v1/serial/logs/nonexistent")
        assert r.status_code == 404


class TestSerialExportLogs:
    """Tests for POST /api/v1/serial/logs/export."""

    def test_export_log_ids_not_list_returns_400(self, client):
        r = client.post(
            "/api/v1/serial/logs/export",
            json={"log_ids": "not-a-list"},
        )
        assert r.status_code == 400


class TestSerialDownloadExport:
    """Tests for GET /api/v1/serial/logs/export/<archive_name>."""

    def test_invalid_archive_name_returns_400(self, client):
        r = client.get("/api/v1/serial/logs/export/../../../etc/passwd")
        assert r.status_code == 400

    def test_archive_not_found_returns_404(self, client):
        r = client.get("/api/v1/serial/logs/export/nonexistent.zip")
        assert r.status_code == 404


class TestSerialGetDevice:
    """Tests for GET /api/v1/serial/devices/<device_id>."""

    def test_unknown_device_returns_404(self, client, monkeypatch):
        def fake_scan(use_cache=True):  # noqa: ARG001
            return []

        from services import serial_manager

        monkeypatch.setattr(serial_manager.serial_manager, "_scan_devices", fake_scan)
        r = client.get("/api/v1/serial/devices/COM99")
        assert r.status_code == 404


class TestSerialTestDevice:
    """Tests for POST /api/v1/serial/devices/<device_id>/test."""

    def test_test_device_not_found_returns_404(self, client, monkeypatch):
        def fake_scan(use_cache=True):  # noqa: ARG001
            return []

        from services import serial_manager

        monkeypatch.setattr(serial_manager.serial_manager, "_scan_devices", fake_scan)
        r = client.post("/api/v1/serial/devices/COM99/test")
        assert r.status_code == 404


class TestSerialSessionEndpoints:
    """Tests for session get/update/delete."""

    def test_get_session_not_found_returns_404(self, client):
        r = client.get("/api/v1/serial/sessions/nonexistent-session-id")
        assert r.status_code == 404

    def test_update_session_not_found_returns_404(self, client):
        r = client.put(
            "/api/v1/serial/sessions/nonexistent-session-id",
            json={"baud_rate": 9600},
        )
        assert r.status_code == 404

    def test_delete_session_not_found_returns_404(self, client):
        r = client.delete("/api/v1/serial/sessions/nonexistent-session-id")
        assert r.status_code == 404


class TestSerialLogContent:
    """Tests for GET /api/v1/serial/logs/<log_id>/content."""

    def test_get_log_content_not_found_returns_404(self, client):
        r = client.get("/api/v1/serial/logs/nonexistent/content")
        assert r.status_code == 404


class TestSerialDeleteLog:
    """Tests for DELETE /api/v1/serial/logs/<log_id>."""

    def test_delete_log_not_found_returns_404(self, client):
        r = client.delete("/api/v1/serial/logs/nonexistent")
        assert r.status_code == 404


class TestSerialExportLogs:
    """Tests for POST /api/v1/serial/logs/export."""

    def test_export_logs_invalid_log_ids_returns_400(self, client):
        r = client.post(
            "/api/v1/serial/logs/export",
            json={"log_ids": "not-a-list"},
        )
        assert r.status_code == 400


class TestSerialDownloadExport:
    """Tests for GET /api/v1/serial/logs/export/<archive_name>."""

    def test_download_export_not_found_returns_404(self, client):
        r = client.get("/api/v1/serial/logs/export/nonexistent-archive.zip")
        assert r.status_code == 404

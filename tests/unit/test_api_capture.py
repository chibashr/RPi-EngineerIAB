"""Unit tests for Capture API routes."""

from __future__ import annotations

import pytest


class TestCaptureInterfaces:
    """Tests for GET /api/v1/capture/interfaces."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/capture/interfaces")
        assert r.status_code == 200

    def test_returns_interfaces_list(self, client):
        r = client.get("/api/v1/capture/interfaces")
        data = r.json()
        assert "data" in data
        assert "interfaces" in data["data"]


class TestCaptureStart:
    """Tests for POST /api/v1/capture/start."""

    def test_missing_interface_returns_400(self, client):
        r = client.post("/api/v1/capture/start", json={})
        assert r.status_code == 400

    def test_valid_interface_returns_201_in_dry_run(self, client):
        r = client.get("/api/v1/capture/interfaces")
        interfaces = r.json()["data"]["interfaces"]
        if interfaces:
            iface = interfaces[0]
            r2 = client.post(
                "/api/v1/capture/start",
                json={"interface": iface, "name": "test-capture"},
            )
            assert r2.status_code == 201
            assert "capture_id" in r2.json()["data"]


class TestCaptureActive:
    """Tests for GET /api/v1/capture/active."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/capture/active")
        assert r.status_code == 200

    def test_returns_captures_list(self, client):
        r = client.get("/api/v1/capture/active")
        data = r.json()
        assert "data" in data
        assert "captures" in data["data"]


class TestCaptureCompleted:
    """Tests for GET /api/v1/capture/completed."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/capture/completed")
        assert r.status_code == 200


class TestCaptureNotFound:
    """Tests for capture endpoints with invalid ID."""

    def test_get_active_404(self, client):
        r = client.get("/api/v1/capture/active/nonexistent-id")
        assert r.status_code == 404

    def test_stop_active_404(self, client):
        r = client.post("/api/v1/capture/active/nonexistent-id/stop")
        assert r.status_code == 404

    def test_get_completed_404(self, client):
        r = client.get("/api/v1/capture/completed/nonexistent-id")
        assert r.status_code == 404

    def test_download_completed_404(self, client):
        r = client.get("/api/v1/capture/completed/nonexistent-id/download")
        assert r.status_code == 404

    def test_delete_completed_404(self, client):
        r = client.delete("/api/v1/capture/completed/nonexistent-id")
        assert r.status_code == 404

    def test_stats_404(self, client):
        r = client.get("/api/v1/capture/nonexistent-id/stats")
        assert r.status_code == 404

    def test_packets_404(self, client):
        r = client.get("/api/v1/capture/nonexistent-id/packets")
        assert r.status_code == 404

    def test_conversations_404(self, client):
        r = client.get("/api/v1/capture/nonexistent-id/conversations")
        assert r.status_code == 404

    def test_protocols_404(self, client):
        r = client.get("/api/v1/capture/nonexistent-id/protocols")
        assert r.status_code == 404


class TestCaptureStartException:
    """Tests for capture start when manager raises."""

    def test_start_capture_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.capture.capture_manager") as mock_cm:
            mock_cm.start_capture.side_effect = OSError("Permission denied")
            r = client.post(
                "/api/v1/capture/start",
                json={"interface": "eth0", "name": "test"},
            )
        assert r.status_code == 500

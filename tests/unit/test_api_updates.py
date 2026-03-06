"""Unit tests for Updates API routes."""

from __future__ import annotations

from unittest.mock import patch


class TestUpdatesCheck:
    """Tests for GET /api/v1/updates/check."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/updates/check")
        assert r.status_code == 200

    def test_check_exception_returns_500(self, client):
        with patch("services.api_gateway.routes.updates.update_manager") as mock_um:
            mock_um.check_for_updates.side_effect = RuntimeError("Check failed")
            r = client.get("/api/v1/updates/check")
        assert r.status_code == 500


class TestUpdatesApply:
    """Tests for POST /api/v1/updates/apply."""

    def test_apply_runtime_error_returns_500(self, client):
        with patch("services.api_gateway.routes.updates.update_manager") as mock_um:
            mock_um.apply_update.side_effect = RuntimeError("Apply failed")
            r = client.post("/api/v1/updates/apply")
        assert r.status_code == 500


class TestUpdatesReconfigure:
    """Tests for POST /api/v1/updates/reconfigure."""

    def test_reconfigure_runtime_error_returns_500(self, client):
        with patch("services.api_gateway.routes.updates.update_manager") as mock_um:
            mock_um.run_reconfigure.side_effect = RuntimeError("Reconfigure failed")
            r = client.post("/api/v1/updates/reconfigure")
        assert r.status_code == 500


class TestUpdatesReinstall:
    """Tests for POST /api/v1/updates/reinstall."""

    def test_reinstall_runtime_error_returns_500(self, client):
        with patch("services.api_gateway.routes.updates.update_manager") as mock_um:
            mock_um.run_reinstall_from_scratch.side_effect = RuntimeError("Reinstall failed")
            r = client.post("/api/v1/updates/reinstall")
        assert r.status_code == 500


class TestUpdatesRollback:
    """Tests for POST /api/v1/updates/rollback."""

    def test_rollback_runtime_error_returns_500(self, client):
        with patch("services.api_gateway.routes.updates.update_manager") as mock_um:
            mock_um.rollback_update.side_effect = RuntimeError("Rollback failed")
            r = client.post("/api/v1/updates/rollback")
        assert r.status_code == 500

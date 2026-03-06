"""Unit tests for Modules API routes."""

from __future__ import annotations

import pytest

class TestModulesList:
    """Tests for GET /api/v1/modules/list."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/modules/list")
        assert r.status_code == 200

    def test_returns_modules_list(self, client):
        r = client.get("/api/v1/modules/list")
        data = r.json()
        assert "data" in data
        assert "modules" in data["data"]
        assert isinstance(data["data"]["modules"], list)


class TestModulesComponents:
    """Tests for GET /api/v1/modules/components."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/modules/components")
        assert r.status_code == 200

    def test_returns_components_list(self, client):
        r = client.get("/api/v1/modules/components")
        data = r.json()
        assert "data" in data
        assert "components" in data["data"]


class TestModulesInstall:
    """Tests for POST /api/v1/modules/install."""

    def test_missing_module_url_returns_400(self, client):
        r = client.post("/api/v1/modules/install", json={})
        assert r.status_code == 400


class TestModulesUninstall:
    """Tests for DELETE /api/v1/modules/uninstall/<id>."""

    def test_unknown_module_returns_404(self, client):
        r = client.delete("/api/v1/modules/uninstall/nonexistent_module")
        assert r.status_code == 404


class TestModulesAvailable:
    """Tests for GET /api/v1/modules/available."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/modules/available")
        assert r.status_code == 200

    def test_returns_available_list(self, client):
        r = client.get("/api/v1/modules/available")
        data = r.json()
        assert "data" in data
        assert "available" in data["data"]
        assert isinstance(data["data"]["available"], list)


class TestModulesInstallFromRepo:
    """Tests for POST /api/v1/modules/install-from-repo."""

    def test_missing_module_id_returns_400(self, client):
        r = client.post("/api/v1/modules/install-from-repo", json={})
        assert r.status_code == 400


class TestModulesUpdates:
    """Tests for GET /api/v1/modules/updates."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/modules/updates")
        assert r.status_code == 200

    def test_returns_updates_list(self, client):
        r = client.get("/api/v1/modules/updates")
        data = r.json()
        assert "data" in data
        assert "updates" in data["data"]
        assert isinstance(data["data"]["updates"], list)


class TestModulesUpdate:
    """Tests for POST /api/v1/modules/update/<module_id>."""

    def test_unknown_module_returns_404(self, client):
        r = client.post("/api/v1/modules/update/nonexistent_module", json={})
        assert r.status_code == 404


class TestModulesEnableDisable:
    """Tests for enable/disable endpoints."""

    def test_enable_unknown_module_returns_404(self, client):
        r = client.post("/api/v1/modules/enable/nonexistent_module")
        assert r.status_code == 404

    def test_disable_unknown_module_returns_404(self, client):
        r = client.post("/api/v1/modules/disable/nonexistent_module")
        assert r.status_code == 404


class TestModulesListException:
    """Tests for list when manager raises."""

    def test_list_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.list_modules.side_effect = RuntimeError("List failed")
            r = client.get("/api/v1/modules/list")
        assert r.status_code == 500


class TestModulesInstallException:
    """Tests for install when manager raises RuntimeError."""

    def test_install_runtime_error_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.install_module.side_effect = RuntimeError("Archive not found")
            r = client.post(
                "/api/v1/modules/install",
                json={"module_url": "file:///tmp/module.zip"},
            )
        assert r.status_code == 500


class TestModulesComponentsException:
    """Tests for components when manager raises."""

    def test_components_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.get_web_components.side_effect = RuntimeError("Components failed")
            r = client.get("/api/v1/modules/components")
        assert r.status_code == 500


class TestModulesAvailableException:
    """Tests for available when manager raises."""

    def test_available_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.list_available_from_repo.side_effect = RuntimeError("Repo failed")
            r = client.get("/api/v1/modules/available")
        assert r.status_code == 500


class TestModulesUpdatesException:
    """Tests for updates check when manager raises."""

    def test_updates_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.check_module_updates.side_effect = RuntimeError("Check failed")
            r = client.get("/api/v1/modules/updates")
        assert r.status_code == 500


class TestModulesEnableDisable:
    """Tests for enable/disable when manager raises."""

    def test_enable_unknown_module_returns_404(self, client):
        r = client.post("/api/v1/modules/enable/nonexistent_module")
        assert r.status_code == 404

    def test_disable_unknown_module_returns_404(self, client):
        r = client.post("/api/v1/modules/disable/nonexistent_module")
        assert r.status_code == 404


class TestModulesManagerExceptions:
    """Tests for module routes when manager raises exceptions."""

    def test_list_modules_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.list_modules.side_effect = OSError("List failed")
            r = client.get("/api/v1/modules/list")
        assert r.status_code == 500

    def test_install_module_runtime_error_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.install_module.side_effect = RuntimeError("Archive not found")
            r = client.post("/api/v1/modules/install", json={"module_url": "file:///tmp/mod.zip"})
        assert r.status_code == 500

    def test_uninstall_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.uninstall_module.side_effect = OSError("Uninstall failed")
            r = client.delete("/api/v1/modules/uninstall/example_module")
        assert r.status_code == 500

    def test_components_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.get_web_components.side_effect = OSError("Components failed")
            r = client.get("/api/v1/modules/components")
        assert r.status_code == 500

    def test_available_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.list_available_from_repo.side_effect = OSError("Available failed")
            r = client.get("/api/v1/modules/available")
        assert r.status_code == 500

    def test_updates_exception_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.modules.module_manager") as mock_mm:
            mock_mm.check_module_updates.side_effect = OSError("Updates failed")
            r = client.get("/api/v1/modules/updates")
        assert r.status_code == 500

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
        data = r.get_json()
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
        data = r.get_json()
        assert "data" in data
        assert "components" in data["data"]


class TestModulesInstall:
    """Tests for POST /api/v1/modules/install."""

    def test_missing_module_url_returns_400(self, client):
        r = client.post(
            "/api/v1/modules/install",
            json={},
            content_type="application/json",
        )
        assert r.status_code == 400


class TestModulesUninstall:
    """Tests for DELETE /api/v1/modules/uninstall/<id>."""

    def test_unknown_module_returns_404(self, client):
        r = client.delete("/api/v1/modules/uninstall/nonexistent_module")
        assert r.status_code == 404

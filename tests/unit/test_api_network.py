"""Unit tests for Network API routes."""

from __future__ import annotations

import pytest


class TestNetworkInterfaces:
    """Tests for GET /api/v1/network/interfaces."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/interfaces")
        assert r.status_code == 200

    def test_returns_interfaces_list(self, client):
        r = client.get("/api/v1/network/interfaces")
        data = r.get_json()
        assert "data" in data
        assert "interfaces" in data["data"]
        assert isinstance(data["data"]["interfaces"], list)


class TestNetworkInterfaceById:
    """Tests for GET /api/v1/network/interfaces/<id>."""

    def test_unknown_interface_returns_404(self, client):
        r = client.get("/api/v1/network/interfaces/nonexistent0")
        assert r.status_code == 404

    def test_known_interface_returns_200(self, client):
        r = client.get("/api/v1/network/interfaces")
        interfaces = r.get_json()["data"]["interfaces"]
        if interfaces:
            iface_id = interfaces[0]["id"]
            r2 = client.get(f"/api/v1/network/interfaces/{iface_id}")
            assert r2.status_code == 200


class TestNetworkUpdateInterface:
    """Tests for PUT /api/v1/network/interfaces/<id>."""

    def test_unknown_interface_returns_404(self, client):
        r = client.put(
            "/api/v1/network/interfaces/nonexistent0",
            json={"mode": "dhcp"},
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_invalid_mode_returns_400(self, client):
        r = client.get("/api/v1/network/interfaces")
        interfaces = r.get_json()["data"]["interfaces"]
        if interfaces:
            iface_id = interfaces[0]["id"]
            r2 = client.put(
                f"/api/v1/network/interfaces/{iface_id}",
                json={"mode": "invalid"},
                content_type="application/json",
            )
            assert r2.status_code == 400


class TestNetworkRoutes:
    """Tests for GET /api/v1/network/routes."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/routes")
        assert r.status_code == 200

    def test_returns_routes_list(self, client):
        r = client.get("/api/v1/network/routes")
        data = r.get_json()
        assert "data" in data
        assert "routes" in data["data"]


class TestNetworkStatus:
    """Tests for GET /api/v1/network/status."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/status")
        assert r.status_code == 200

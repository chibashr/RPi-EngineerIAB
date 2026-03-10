"""Unit tests for Network API routes."""

from __future__ import annotations


class TestNetworkInterfaces:
    """Tests for GET /api/v1/network/interfaces."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/interfaces")
        assert r.status_code == 200

    def test_returns_interfaces_list(self, client):
        r = client.get("/api/v1/network/interfaces")
        data = r.json()
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
        interfaces = r.json()["data"]["interfaces"]
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
        )
        assert r.status_code == 404

    def test_invalid_mode_returns_400(self, client):
        r = client.get("/api/v1/network/interfaces")
        interfaces = r.json()["data"]["interfaces"]
        if interfaces:
            iface_id = interfaces[0]["id"]
            r2 = client.put(
                f"/api/v1/network/interfaces/{iface_id}",
                json={"mode": "invalid"},
            )
            assert r2.status_code == 400


class TestNetworkRoutes:
    """Tests for GET /api/v1/network/routes."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/routes")
        assert r.status_code == 200

    def test_returns_routes_list(self, client):
        r = client.get("/api/v1/network/routes")
        data = r.json()
        assert "data" in data
        assert "routes" in data["data"]


class TestNetworkStatus:
    """Tests for GET /api/v1/network/status."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/network/status")
        assert r.status_code == 200


class TestNetworkWanPriority:
    """Tests for POST /api/v1/network/wan-priority."""

    def test_returns_200(self, client):
        r = client.post("/api/v1/network/wan-priority")
        assert r.status_code == 200

    def test_returns_wan_interface_and_applied(self, client):
        r = client.post("/api/v1/network/wan-priority")
        data = r.json()
        assert "data" in data
        assert "wan_interface" in data["data"]
        assert "internet_capable" in data["data"]
        assert "applied" in data["data"]


class TestNetworkAddRoute:
    """Tests for POST /api/v1/network/routes."""

    def test_add_route_validation_error_returns_400(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.add_route.side_effect = ValueError("Invalid route")
            r = client.post("/api/v1/network/routes", json={"destination": "bad"})
        assert r.status_code == 400


class TestNetworkProfiles:
    """Tests for network profile endpoints."""

    def test_load_profile_not_found_returns_404(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.load_profile.side_effect = KeyError("Profile not found")
            r = client.post("/api/v1/network/profiles/nonexistent/load")
        assert r.status_code == 404

    def test_update_profile_not_found_returns_404(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.update_profile.side_effect = KeyError("Profile not found")
            r = client.put("/api/v1/network/profiles/nonexistent", json={"name": "x"})
        assert r.status_code == 404

    def test_delete_profile_not_found_returns_404(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.delete_profile.side_effect = KeyError("Profile not found")
            r = client.delete("/api/v1/network/profiles/nonexistent")
        assert r.status_code == 404


class TestNetworkReset:
    """Tests for POST /api/v1/network/reset."""

    def test_reset_runtime_error_returns_500(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.reset_network.side_effect = RuntimeError("Reset failed")
            r = client.post("/api/v1/network/reset", json={})
        assert r.status_code == 500


class TestNetworkVlan:
    """Tests for POST /api/v1/network/vlans."""

    def test_create_vlan_validation_error_returns_400(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.create_vlan.side_effect = ValueError("Invalid vlan")
            r = client.post("/api/v1/network/vlans", json={})
        assert r.status_code == 400


class TestNetworkShareWithHotspot:
    """Tests for PUT /api/v1/network/interfaces/<id>/share-with-hotspot."""

    def test_wlan_interface_returns_400(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.set_interface_share_hotspot.side_effect = ValueError(
                "Cannot share wlan interface with hotspot (it is the hotspot)"
            )
            r = client.put("/api/v1/network/interfaces/wlan0/share-with-hotspot", json={"enabled": True})
        assert r.status_code == 400

    def test_returns_200_with_enabled(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.set_interface_share_hotspot.return_value = {
                "interface": "eth0",
                "share_with_hotspot": True,
                "applied": False,
            }
            r = client.put("/api/v1/network/interfaces/eth0/share-with-hotspot", json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["data"]["share_with_hotspot"] is True


class TestNetworkHotspot:
    """Tests for POST /api/v1/network/hotspot."""

    def test_configure_hotspot_validation_error_returns_400(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.configure_hotspot.side_effect = ValueError("Invalid ssid")
            r = client.post("/api/v1/network/hotspot", json={})
        assert r.status_code == 400

    def test_save_profile_validation_error_returns_400(self, client):
        from unittest.mock import patch

        with patch("services.api_gateway.routes.network._network_manager") as mock_nm:
            mock_nm.save_profile.side_effect = ValueError("Invalid profile")
            r = client.post("/api/v1/network/profiles", json={"name": "test"})
        assert r.status_code == 400

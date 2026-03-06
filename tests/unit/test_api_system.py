"""Unit tests for System API routes."""

from __future__ import annotations


class TestSystemStatus:
    """Tests for GET /api/v1/system/status."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/system/status")
        assert r.status_code == 200

    def test_returns_json_with_data(self, client):
        r = client.get("/api/v1/system/status")
        data = r.json()
        assert "data" in data
        assert "status" in data["data"]
        assert "services" in data["data"]
        assert "resources" in data["data"]

    def test_resources_include_cpu_memory_disk(self, client):
        r = client.get("/api/v1/system/status")
        resources = r.json()["data"]["resources"]
        assert "cpu_percent" in resources
        assert "memory_percent" in resources
        assert "disk_percent" in resources


class TestSystemServices:
    """Tests for GET /api/v1/system/services."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/system/services")
        assert r.status_code == 200

    def test_returns_services_list(self, client):
        r = client.get("/api/v1/system/services")
        data = r.json()
        assert "data" in data
        assert "services" in data["data"]
        assert isinstance(data["data"]["services"], list)

    def test_services_have_name_status_category(self, client):
        r = client.get("/api/v1/system/services")
        data = r.json()["data"]["services"]
        for item in data:
            assert "name" in item
            assert "status" in item
            assert "category" in item
            assert item["category"] in ("core", "system", "optional")


class TestSystemControlService:
    """Tests for POST /api/v1/system/services."""

    def test_missing_service_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services",
            json={"action": "start"},
        )
        assert r.status_code == 400

    def test_missing_action_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services",
            json={"service": "nginx"},
        )
        assert r.status_code == 400

    def test_invalid_action_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services",
            json={"service": "nginx", "action": "invalid"},
        )
        assert r.status_code == 400


class TestSystemControlServicesBulk:
    """Tests for POST /api/v1/system/services/bulk."""

    def test_missing_services_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services/bulk",
            json={"action": "restart"},
        )
        assert r.status_code == 400

    def test_missing_action_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services/bulk",
            json={"services": ["api_gateway"]},
        )
        assert r.status_code == 400

    def test_invalid_action_returns_400(self, client):
        r = client.post(
            "/api/v1/system/services/bulk",
            json={"services": ["api_gateway"], "action": "pause"},
        )
        assert r.status_code == 400

    def test_returns_results_array(self, client):
        r = client.post(
            "/api/v1/system/services/bulk",
            json={"services": ["api_gateway"], "action": "restart"},
        )
        if r.status_code == 200:
            data = r.json()
            assert "data" in data
            assert "results" in data["data"]
            assert isinstance(data["data"]["results"], list)


class TestSystemPower:
    """Tests for POST /api/v1/system/power."""

    def test_missing_action_returns_400(self, client):
        r = client.post(
            "/api/v1/system/power",
            json={},
        )
        assert r.status_code == 400

    def test_shutdown_in_dry_run_returns_ok(self, client):
        r = client.post(
            "/api/v1/system/power",
            json={"action": "shutdown"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["data"]["action"] == "shutdown"
        assert data["data"]["scheduled"] is False

    def test_reboot_in_dry_run_returns_ok(self, client):
        r = client.post(
            "/api/v1/system/power",
            json={"action": "reboot"},
        )
        assert r.status_code == 200


class TestSystemInfo:
    """Tests for GET /api/v1/system/info."""

    def test_returns_200(self, client):
        r = client.get("/api/v1/system/info")
        assert r.status_code == 200

    def test_includes_hostname_version_os(self, client):
        r = client.get("/api/v1/system/info")
        data = r.json()["data"]
        assert "hostname" in data
        assert "version" in data
        assert "os" in data

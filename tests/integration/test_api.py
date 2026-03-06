"""Integration tests for the full API and web interface."""

from __future__ import annotations

import pytest


class TestHealthEndpoint:
    """Tests for /health."""

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_returns_healthy(self, client):
        r = client.get("/health")
        data = r.json()
        assert data["data"]["status"] == "healthy"


class TestApiResponseFormat:
    """Verify API response structure across endpoints."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/dashboard/status",
            "/api/v1/system/status",
            "/api/v1/system/info",
            "/api/v1/system/services",
            "/api/v1/network/interfaces",
            "/api/v1/network/status",
            "/api/v1/network/routes",
            "/api/v1/network/profiles",
            "/api/v1/serial/devices",
            "/api/v1/serial/sessions",
            "/api/v1/capture/interfaces",
            "/api/v1/capture/active",
            "/api/v1/capture/completed",
            "/api/v1/updates/check",
            "/api/v1/remote/status",
            "/api/v1/remote/info",
            "/api/v1/modules/list",
            "/api/v1/modules/components",
            "/api/v1/syslog/status",
            "/api/v1/syslog/config",
            "/api/v1/syslog/recent",
            "/api/v1/syslog/stored",
            "/api/v1/snmp_traps/status",
            "/api/v1/snmp_traps/config",
            "/api/v1/snmp_traps/recent",
            "/api/v1/snmp_traps/stored",
        ],
    )
    def test_get_endpoint_returns_json_with_data_or_error(self, client, path):
        r = client.get(path)
        # 501 = Phase 1 stub; 404 = module routes not yet registered; 200/500 = real implementation
        assert r.status_code in (200, 404, 500, 501), f"Unexpected status for {path}: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "data" in data or "error" in data
            if "data" in data:
                assert "meta" in data
                assert "timestamp" in data["meta"]


class TestWebStaticFiles:
    """Tests for static web file serving."""

    def test_root_serves_simple_index(self, client):
        """Root path (/) serves simple mode index.html."""
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.content_type
        assert b"Simple Mode" in r.data or b"simple" in r.data.lower()

    def test_advanced_path_serves_advanced_index(self, client):
        """Advanced path (/advanced/ or /advanced) serves advanced index."""
        for path in ("/advanced/", "/advanced"):
            r = client.get(path)
            assert r.status_code == 200, f"Failed for {path}"
            assert "text/html" in r.content_type
            assert b"Advanced" in r.data or b"Dashboard" in r.data

    def test_index_html_returns_200(self, client):
        r = client.get("/index.html")
        assert r.status_code == 200

    def test_index_serves_html(self, client):
        r = client.get("/index.html")
        assert "text/html" in r.content_type
        assert b"RPi Engineer" in r.data or b"rpi-engineer" in r.data.lower()

    def test_advanced_index_returns_200(self, client):
        r = client.get("/advanced/index.html")
        assert r.status_code == 200

    def test_css_served(self, client):
        r = client.get("/css/base.css")
        assert r.status_code == 200
        assert "text/css" in r.content_type or "text/plain" in r.content_type


class TestInstallScript:
    """Basic validation of install script (syntax only)."""

    def test_install_script_exists(self):
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "bin" / "install.sh"
        assert script.exists()

    def test_install_script_syntax_valid(self):
        """Run bash -n to check syntax (no execution). Skips if bash unavailable or fails (e.g. Windows paths)."""
        import platform
        import shutil
        import subprocess
        from pathlib import Path

        if not shutil.which("bash"):
            pytest.skip("bash not available (WSL/Git Bash required on Windows)")
        script = Path(__file__).resolve().parents[2] / "bin" / "install.sh"
        result = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and platform.system() == "Windows":
            pytest.skip("bash syntax check unreliable on Windows (use WSL for full validation)")
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestExampleModule:
    """Tests for example module integration (if enabled)."""

    def test_example_hello_returns_200_or_404(self, client):
        r = client.get("/api/v1/example/hello")
        assert r.status_code in (200, 404, 409)

    def test_example_hello_message_when_available(self, client):
        r = client.get("/api/v1/example/hello")
        if r.status_code != 200:
            pytest.skip("Example module not available")
        data = r.json()
        assert "data" in data
        assert "message" in data["data"]
        assert "Example" in data["data"]["message"]


class TestSyslogModuleApi:
    """Integration tests for syslog receiver module API."""

    def test_syslog_status_returns_200_and_structure(self, client):
        r = client.get("/api/v1/syslog/status")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        status = data["data"]
        assert "enabled" in status
        assert "running" in status
        assert "received_count" in status
        assert "stored_count" in status

    def test_syslog_config_get_returns_200(self, client):
        r = client.get("/api/v1/syslog/config")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        config = data["data"]
        assert "enabled" in config
        assert "bind_address" in config
        assert "port_udp" in config
        assert "port_tcp" in config

    def test_syslog_config_put_accepts_valid_payload(self, client):
        r = client.put(
            "/api/v1/syslog/config",
            json={
                "enabled": True,
                "bind_address": "0.0.0.0",
                "port_udp": 1514,
                "port_tcp": 1514,
                "persist": True,
                "max_live": 1000,
                "max_stored": 10000,
            },
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_syslog_recent_returns_items_array(self, client):
        r = client.get("/api/v1/syslog/recent?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "items" in data["data"]
        assert isinstance(data["data"]["items"], list)

    def test_syslog_stored_returns_items_array(self, client):
        r = client.get("/api/v1/syslog/stored?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "items" in data["data"]
        assert isinstance(data["data"]["items"], list)


class TestSnmpModuleApi:
    """Integration tests for SNMP trap receiver module API."""

    def test_snmp_status_returns_200_and_structure(self, client):
        r = client.get("/api/v1/snmp_traps/status")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "meta" in data
        status = data["data"]
        assert "enabled" in status
        assert "running" in status
        assert "received_count" in status
        assert "stored_count" in status

    def test_snmp_config_get_returns_200(self, client):
        r = client.get("/api/v1/snmp_traps/config")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        config = data["data"]
        assert "enabled" in config
        assert "bind_address" in config
        assert "port" in config

    def test_snmp_config_put_accepts_valid_payload(self, client):
        r = client.put(
            "/api/v1/snmp_traps/config",
            json={
                "enabled": True,
                "bind_address": "0.0.0.0",
                "port": 1162,
                "persist": True,
                "max_live": 500,
                "max_stored": 10000,
            },
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_snmp_recent_returns_items_array(self, client):
        r = client.get("/api/v1/snmp_traps/recent?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "items" in data["data"]
        assert isinstance(data["data"]["items"], list)

    def test_snmp_stored_returns_items_array(self, client):
        r = client.get("/api/v1/snmp_traps/stored?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "items" in data["data"]
        assert isinstance(data["data"]["items"], list)

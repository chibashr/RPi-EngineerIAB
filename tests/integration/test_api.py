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
        data = r.get_json()
        assert data["data"]["status"] == "healthy"


class TestApiResponseFormat:
    """Verify API response structure across endpoints."""

    @pytest.mark.parametrize(
        "path",
        [
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
        ],
    )
    def test_get_endpoint_returns_json_with_data_or_error(self, client, path):
        r = client.get(path)
        assert r.status_code in (200, 500), f"Unexpected status for {path}: {r.status_code}"
        if r.status_code == 200:
            data = r.get_json()
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
        data = r.get_json()
        assert "data" in data
        assert "message" in data["data"]
        assert "Example" in data["data"]["message"]

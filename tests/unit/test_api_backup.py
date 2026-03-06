"""Unit tests for Backup API routes."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

import pytest


class TestBackupDownloadConfig:
    """Tests for GET /api/v1/backup/config."""

    def test_download_config_returns_zip_on_success(self, client, tmp_path):
        zip_path = tmp_path / "config_backup.zip"
        zip_path.write_bytes(b"PK\x03\x04")
        with patch("services.api_gateway.routes.backup.update_manager") as mock_um:
            mock_um.create_config_backup.return_value = zip_path
            r = client.get("/api/v1/backup/config")
        assert r.status_code == 200
        assert "config_backup.zip" in r.headers.get("content-disposition", "")

    def test_download_config_returns_500_when_manager_raises(self, client):
        with patch("services.api_gateway.routes.backup.update_manager") as mock_um:
            mock_um.create_config_backup.side_effect = RuntimeError("Backup failed")
            r = client.get("/api/v1/backup/config")
        assert r.status_code == 500
        data = r.json()
        assert data.get("error", {}).get("code") == "INTERNAL_ERROR"


class TestBackupRestore:
    """Tests for POST /api/v1/backup/restore."""

    def test_restore_missing_filename_returns_400(self, client):
        r = client.post(
            "/api/v1/backup/restore",
            files={"file": ("", BytesIO(b"zip content"), "application/zip")},
        )
        assert r.status_code in (400, 422)

    def test_restore_success_returns_200(self, client):
        with patch("services.api_gateway.routes.backup.update_manager") as mock_um:
            mock_um.restore_config.return_value = {"restored": True}
            r = client.post(
                "/api/v1/backup/restore",
                files={"file": ("backup.zip", BytesIO(b"PK\x03\x04"), "application/zip")},
            )
        assert r.status_code == 200
        data = r.json()
        assert data.get("data", {}).get("restored") is True

    def test_restore_runtime_error_returns_500(self, client):
        with patch("services.api_gateway.routes.backup.update_manager") as mock_um:
            mock_um.restore_config.side_effect = RuntimeError("Restore failed")
            r = client.post(
                "/api/v1/backup/restore",
                files={"file": ("backup.zip", BytesIO(b"PK\x03\x04"), "application/zip")},
            )
        assert r.status_code == 500
        data = r.json()
        assert data.get("error", {}).get("code") == "INTERNAL_ERROR"

    def test_restore_generic_exception_returns_500(self, client):
        with patch("services.api_gateway.routes.backup.update_manager") as mock_um:
            mock_um.restore_config.side_effect = OSError("Permission denied")
            r = client.post(
                "/api/v1/backup/restore",
                files={"file": ("backup.zip", BytesIO(b"PK\x03\x04"), "application/zip")},
            )
        assert r.status_code == 500

"""Unit tests for Logs API routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestLogsSystem:
    """Tests for GET /api/v1/logs/system."""

    def test_list_logs_returns_200(self, client):
        r = client.get("/api/v1/logs/system")
        assert r.status_code == 200
        data = r.json()
        assert "data" in data

    def test_list_logs_with_file_all(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.read_all_logs.return_value = {"logs": []}
            r = client.get("/api/v1/logs/system?file=all")
        assert r.status_code == 200
        mock_ls.read_all_logs.assert_called_once()

    def test_list_logs_with_specific_file(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.read_log.return_value = {"lines": []}
            r = client.get("/api/v1/logs/system?file=api.log")
        assert r.status_code == 200
        mock_ls.read_log.assert_called_once_with(
            "api.log", tail=100, level=None, search=None, service="all"
        )

    def test_list_logs_validation_error_returns_400(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.read_log.side_effect = ValueError("Invalid file name")
            r = client.get("/api/v1/logs/system?file=invalid..path")
        assert r.status_code == 400
        data = r.json()
        assert data.get("error", {}).get("code") == "VALIDATION_ERROR"

    def test_list_logs_file_not_found_returns_404(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.read_log.side_effect = FileNotFoundError()
            r = client.get("/api/v1/logs/system?file=nonexistent.log")
        assert r.status_code == 404
        data = r.json()
        assert data.get("error", {}).get("code") == "NOT_FOUND"

    def test_list_logs_generic_exception_returns_500(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.list_logs.side_effect = OSError("Read failed")
            r = client.get("/api/v1/logs/system")
        assert r.status_code == 500

    def test_list_logs_includes_entries_and_available_services(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.read_all_logs.return_value = {
                "file": "all",
                "tail": 200,
                "lines": ["2026-03-06 14:30:00,123 INFO [serial_manager] Session started"],
                "filters": {},
                "entries": [
                    {
                        "timestamp": "2026-03-06T14:30:00.123Z",
                        "level": "INFO",
                        "service": "serial_manager",
                        "message": "Session started",
                    }
                ],
                "available_services": ["api_gateway", "serial_manager"],
            }
            r = client.get("/api/v1/logs/system?file=all&lines=200")
        assert r.status_code == 200
        data = r.json().get("data", {})
        assert "entries" in data
        assert len(data["entries"]) == 1
        assert data["entries"][0]["service"] == "serial_manager"
        assert "available_services" in data
        assert "serial_manager" in data["available_services"]


class TestLogsExport:
    """Tests for GET /api/v1/logs/export."""

    def test_export_logs_returns_zip_on_success(self, client, tmp_path):
        zip_path = tmp_path / "logs_export.zip"
        zip_path.write_bytes(b"PK\x03\x04")
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.export_logs.return_value = zip_path
            r = client.get("/api/v1/logs/export")
        assert r.status_code == 200
        assert "logs_export.zip" in r.headers.get("content-disposition", "")

    def test_export_logs_exception_returns_500(self, client):
        with patch("services.api_gateway.routes.logs.logging_service") as mock_ls:
            mock_ls.export_logs.side_effect = OSError("Export failed")
            r = client.get("/api/v1/logs/export")
        assert r.status_code == 500
        data = r.json()
        assert data.get("error", {}).get("code") == "INTERNAL_ERROR"

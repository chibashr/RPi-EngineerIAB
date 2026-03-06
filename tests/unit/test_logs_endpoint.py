"""Unit tests for logs endpoint (available_services, entries, level filter, etc.)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.logging_service.manager import LoggingService


@pytest.fixture
def log_dir_with_files(tmp_path):
    """Create temp log dir with known log files."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "api_gateway.log").write_text(
        "2026-03-06 14:30:00,123 INFO [api_gateway] Started\n"
        "2026-03-06 14:30:01,456 WARNING [api_gateway] High load\n"
    )
    (log_dir / "serial_manager.log").write_text(
        "2026-03-06 14:30:02,789 INFO [serial_manager] Session started session_id=abc\n"
    )
    return log_dir


@pytest.fixture
def logging_service_with_tmp(log_dir_with_files, tmp_path, monkeypatch):
    """LoggingService instance using temp log dir."""
    monkeypatch.setenv("RPI_ENGINEER_LOG_DIR", str(log_dir_with_files))
    monkeypatch.setenv("RPI_ENGINEER_LOG_EXPORT_DIR", str(tmp_path / "exports"))
    return LoggingService()


@pytest.mark.unit
def test_available_services_returned(logging_service_with_tmp):
    """available_services should contain discovered log file stems."""
    result = logging_service_with_tmp.list_logs()
    assert "available_services" in result
    services = result["available_services"]
    assert "api_gateway" in services
    assert "serial_manager" in services


@pytest.mark.unit
def test_entries_parsed_correctly(logging_service_with_tmp):
    """Entries should have correct timestamp, level, service, message."""
    result = logging_service_with_tmp.read_log("api_gateway.log", tail=10)
    assert "entries" in result
    entries = result["entries"]
    assert len(entries) >= 1
    e = entries[0]
    assert "timestamp" in e
    assert "level" in e
    assert "service" in e
    assert "message" in e
    assert e["service"] == "api_gateway"
    assert "Started" in e["message"]


@pytest.mark.unit
def test_level_filter_works(log_dir_with_files, logging_service_with_tmp):
    """level=WARNING should return only WARNING and ERROR entries."""
    result = logging_service_with_tmp.read_all_logs(
        tail=100, level="WARNING", service="all"
    )
    entries = result["entries"]
    for e in entries:
        assert e["level"] in ("WARNING", "ERROR")
    assert any(e["level"] == "WARNING" for e in entries)


@pytest.mark.unit
def test_lines_limit_respected(log_dir_with_files, logging_service_with_tmp):
    """Requesting lines=50 should return at most 50 entries."""
    # Write 500 lines
    lines = [
        f"2026-03-06 14:30:{i:02d},000 INFO [api_gateway] Line {i}\n"
        for i in range(500)
    ]
    (log_dir_with_files / "api_gateway.log").write_text("".join(lines))
    result = logging_service_with_tmp.read_log("api_gateway.log", tail=50)
    assert len(result["entries"]) <= 50
    assert len(result["lines"]) <= 50


@pytest.mark.unit
def test_missing_service_returns_empty_not_404(client, log_dir_with_files, monkeypatch):
    """service=nonexistent_service should return 200 with empty entries, not 404."""
    monkeypatch.setenv("RPI_ENGINEER_LOG_DIR", str(log_dir_with_files))
    monkeypatch.setenv(
        "RPI_ENGINEER_LOG_EXPORT_DIR",
        str(log_dir_with_files.parent / "exports"),
    )
    svc = LoggingService()

    with patch("services.api_gateway.routes.logs.logging_service", svc):
        r = client.get(
            "/api/v1/logs/system?file=all&service=nonexistent_service"
        )
    assert r.status_code == 200
    data = r.json().get("data", {})
    assert "entries" in data
    assert data["entries"] == []
    assert "available_services" in data

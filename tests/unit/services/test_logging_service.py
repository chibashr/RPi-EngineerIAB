import pytest

from services.logging_service.manager import LoggingService


@pytest.mark.unit
def test_list_and_read_logs(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text("INFO service ready\nERROR failure\n")
    monkeypatch.setenv("RPI_ENGINEER_LOG_DIR", str(log_dir))
    monkeypatch.setenv("RPI_ENGINEER_LOG_EXPORT_DIR", str(tmp_path / "exports"))

    service = LoggingService()
    listing = service.list_logs()
    assert listing["files"]

    output = service.read_log("app.log", tail=1)
    assert output["lines"][-1].endswith("failure")


@pytest.mark.unit
def test_get_recent_log_alerts(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "app.log").write_text(
        "2025-02-03 12:00:00,000 - root - INFO - started\n"
        "2025-02-03 12:00:01,000 - root - WARNING - high load\n"
        "2025-02-03 12:00:02,000 - root - ERROR - connection failed\n"
    )
    monkeypatch.setenv("RPI_ENGINEER_LOG_DIR", str(log_dir))
    monkeypatch.setenv("RPI_ENGINEER_LOG_EXPORT_DIR", str(tmp_path / "exports"))

    service = LoggingService()
    alerts = service.get_recent_log_alerts(limit=10)
    assert len(alerts) == 2
    severities = {a["severity"] for a in alerts}
    assert "warning" in severities
    assert "critical" in severities
    messages = [a["message"] for a in alerts]
    assert any("connection failed" in m for m in messages)
    assert any("high load" in m for m in messages)
    assert all(a.get("source") == "log" for a in alerts)

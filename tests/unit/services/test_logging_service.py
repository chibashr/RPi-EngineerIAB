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

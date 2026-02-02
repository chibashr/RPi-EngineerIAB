import subprocess

import pytest

from services.system_manager.manager import SystemManager


@pytest.mark.unit
def test_get_status_uses_metrics(monkeypatch):
    manager = SystemManager()
    monkeypatch.setattr(manager, "_get_service_state", lambda _: "running")
    monkeypatch.setattr(manager, "_cpu_percent", lambda: 12.5)
    monkeypatch.setattr(manager, "_memory_percent", lambda: 34.5)
    monkeypatch.setattr(manager, "_disk_percent", lambda: 45.0)
    monkeypatch.setattr(manager, "_temperature_c", lambda: 55.0)
    monkeypatch.setattr(manager, "_uptime_seconds", lambda: 123.0)

    status = manager.get_status()

    assert status["status"] == "healthy"
    assert status["resources"]["cpu_percent"] == 12.5
    assert status["resources"]["memory_percent"] == 34.5
    assert status["resources"]["disk_percent"] == 45.0
    assert status["resources"]["temperature_c"] == 55.0
    assert status["uptime_seconds"] == 123


@pytest.mark.unit
def test_control_service_rejects_invalid_action():
    manager = SystemManager()
    with pytest.raises(ValueError):
        manager.control_service("api_gateway", "pause")


@pytest.mark.unit
def test_control_service_runs_systemctl(monkeypatch):
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)
    called = {}

    def fake_run(cmd, check, stdout, stderr):
        called["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = manager.control_service("api_gateway", "restart")

    assert result["status"] == "ok"
    assert called["cmd"] == ["systemctl", "restart", "api_gateway.service"]


@pytest.mark.unit
def test_power_action_dry_run(monkeypatch):
    manager = SystemManager()
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "1")

    result = manager.power_action("shutdown")

    assert result["action"] == "shutdown"
    assert result["scheduled"] is False

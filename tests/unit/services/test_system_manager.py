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
def test_get_service_state_uses_systemctl_show(monkeypatch):
    """Service state is read via systemctl show ActiveState for reliability."""
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)
    called = {}

    def capture_run(args, **kwargs):
        called["args"] = args
        # Simulate systemctl show --property=ActiveState --value <unit>
        if "rpi-engineer-api" in str(args):
            return subprocess.CompletedProcess(args, 0, stdout="active\n", stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="inactive\n", stderr="")

    monkeypatch.setattr(subprocess, "run", capture_run)
    assert manager._get_service_state("api_gateway") == "running"
    assert "show" in called["args"]
    assert "--property=ActiveState" in called["args"]
    assert "rpi-engineer-api.service" in called["args"]


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
    assert called["cmd"] == ["systemctl", "restart", "rpi-engineer-api.service"]


@pytest.mark.unit
def test_power_action_dry_run(monkeypatch):
    manager = SystemManager()
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "1")

    result = manager.power_action("shutdown")

    assert result["action"] == "shutdown"
    assert result["scheduled"] is False


@pytest.mark.unit
def test_control_services_bulk_rejects_invalid_action():
    manager = SystemManager()
    with pytest.raises(ValueError):
        manager.control_services_bulk(["api_gateway"], "pause")


@pytest.mark.unit
def test_control_services_bulk_returns_one_result_per_service(monkeypatch):
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
    )
    results = manager.control_services_bulk(
        ["api_gateway", "system_manager"], "restart"
    )
    assert len(results) == 2
    assert all("service" in r and "action" in r and "status" in r for r in results)
    assert results[0]["service"] == "api_gateway"
    assert results[1]["service"] == "system_manager"

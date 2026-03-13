import subprocess
from unittest.mock import MagicMock, patch

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


@pytest.mark.unit
def test_cpu_percent_warmup_called_on_init(monkeypatch):
    """psutil.cpu_percent() is called in __init__ to warm up the baseline."""
    warmup_called = {"count": 0}

    class MockPsutil:
        @staticmethod
        def cpu_percent(interval=None):
            warmup_called["count"] += 1
            return 25.0

    monkeypatch.setattr("services.system_manager.manager.psutil", MockPsutil)
    _manager = SystemManager()
    assert warmup_called["count"] == 1, "cpu_percent should be called once during init"


@pytest.mark.unit
def test_get_all_service_states_parses_multiline_output(monkeypatch):
    """Batch systemctl show returns correct states for all services."""
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)

    output_lines = "\n".join(["active"] * len(manager._service_names))

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=output_lines, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    states = manager._get_all_service_states()

    assert len(states) == len(manager._service_names)
    assert all(s == "running" for s in states.values())


@pytest.mark.unit
def test_get_all_service_states_handles_fewer_lines(monkeypatch):
    """Missing lines result in 'unknown' for remaining services."""
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)

    output_lines = "active\ninactive\nfailed"

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=output_lines, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    states = manager._get_all_service_states()

    service_list = list(states.values())
    assert service_list[0] == "running"
    assert service_list[1] == "stopped"
    assert service_list[2] == "failed"
    assert all(s == "unknown" for s in service_list[3:])


@pytest.mark.unit
def test_get_all_service_states_returns_unknown_on_timeout(monkeypatch):
    """TimeoutExpired returns all 'unknown'."""
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)

    def raise_timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    states = manager._get_all_service_states()

    assert all(s == "unknown" for s in states.values())


@pytest.mark.unit
def test_get_all_service_states_returns_unknown_on_oserror(monkeypatch):
    """OSError (e.g., binary not found) returns all 'unknown'."""
    manager = SystemManager()
    monkeypatch.setattr(manager, "_systemctl_available", lambda: True)

    def raise_oserror(cmd, **kwargs):
        raise OSError("systemctl not found")

    monkeypatch.setattr(subprocess, "run", raise_oserror)
    states = manager._get_all_service_states()

    assert all(s == "unknown" for s in states.values())


@pytest.mark.unit
def test_list_services_uses_batched_state_fetch(monkeypatch):
    """list_services calls _get_all_service_states once, not individual _get_service_state."""
    manager = SystemManager()
    batch_called = {"count": 0}
    individual_called = {"count": 0}

    def mock_batch():
        batch_called["count"] += 1
        return {name: "running" for name in manager._service_names}

    def mock_individual(name):
        individual_called["count"] += 1
        return "running"

    monkeypatch.setattr(manager, "_get_all_service_states", mock_batch)
    monkeypatch.setattr(manager, "_get_service_state", mock_individual)

    result = manager.list_services()

    assert batch_called["count"] == 1
    assert individual_called["count"] == 0
    assert len(result["services"]) == len(manager._service_names)


@pytest.mark.unit
@pytest.mark.parametrize("input_state,expected", [
    ("active", "running"),
    ("inactive", "stopped"),
    ("failed", "failed"),
    ("activating", "starting"),
    ("deactivating", "stopping"),
    ("", "unknown"),
    ("reloading", "unknown"),
])
def test_parse_active_state(input_state, expected):
    """State parser handles all systemd ActiveState values."""
    manager = SystemManager()
    assert manager._parse_active_state(input_state) == expected

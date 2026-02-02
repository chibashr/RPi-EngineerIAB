import pytest

from services.monitor_service.manager import MonitorService


@pytest.mark.unit
def test_evaluate_health_flags_alerts():
    service = MonitorService()
    system_status = {
        "resources": {
            "cpu_percent": 10,
            "memory_percent": 91,
            "disk_percent": 96,
            "temperature_c": 86,
        },
        "services": {"api_gateway": "running", "network_manager": "stopped"},
    }
    network_status = {"wan_status": "disconnected"}

    health, alerts = service._evaluate_health(system_status, network_status)

    assert health["status"] == "unhealthy"
    assert any(alert["severity"] == "critical" for alert in alerts)
    assert any("WAN" in alert["message"] for alert in alerts)

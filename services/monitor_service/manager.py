"""Monitor Service implementation for metrics and alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from services.network_manager import NetworkManager
from services.system_manager import SystemManager


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class MonitorService:
    """Collect metrics, health status, and alerts."""

    def __init__(self) -> None:
        self._system_manager = SystemManager()
        self._network_manager = NetworkManager()

    def get_status(self) -> Dict[str, object]:
        system_status = self._system_manager.get_status()
        network_status = self._network_manager.get_status()
        health, alerts = self._evaluate_health(system_status, network_status)
        return {
            "timestamp": _timestamp(),
            "metrics": system_status.get("resources", {}),
            "services": system_status.get("services", {}),
            "health": health,
            "alerts": alerts,
            "network": network_status,
        }

    def _evaluate_health(
        self, system_status: Dict[str, object], network_status: Dict[str, object]
    ) -> tuple[Dict[str, object], List[Dict[str, object]]]:
        alerts: List[Dict[str, object]] = []
        resources = system_status.get("resources", {}) or {}
        services = system_status.get("services", {}) or {}
        disk_percent = float(resources.get("disk_percent") or 0)
        memory_percent = float(resources.get("memory_percent") or 0)
        cpu_percent = float(resources.get("cpu_percent") or 0)
        temperature_c = resources.get("temperature_c")

        severity = "healthy"
        if disk_percent >= 95:
            alerts.append(self._alert("critical", "Disk usage above 95%"))
            severity = "unhealthy"
        elif disk_percent >= 90:
            alerts.append(self._alert("warning", "Disk usage above 90%"))
            severity = "degraded"

        if memory_percent >= 90:
            alerts.append(self._alert("warning", "Memory usage above 90%"))
            severity = "degraded"

        if cpu_percent >= 95:
            alerts.append(self._alert("warning", "CPU usage above 95%"))
            severity = "degraded"

        if temperature_c is not None:
            temp_value = float(temperature_c)
            if temp_value >= 85:
                alerts.append(self._alert("critical", "CPU temperature above 85 C"))
                severity = "unhealthy"
            elif temp_value >= 80:
                alerts.append(self._alert("warning", "CPU temperature above 80 C"))
                severity = "degraded"

        for name, status in services.items():
            if status != "running":
                alerts.append(self._alert("warning", f"Service {name} is {status}"))
                severity = "degraded"

        if network_status.get("wan_status") == "disconnected":
            alerts.append(self._alert("warning", "WAN connectivity is down"))
            severity = "degraded"

        health = {
            "status": severity,
            "checked_at": _timestamp(),
            "checks": {
                "disk_percent": disk_percent,
                "memory_percent": memory_percent,
                "cpu_percent": cpu_percent,
                "temperature_c": temperature_c,
                "wan_status": network_status.get("wan_status"),
            },
        }
        return health, alerts

    def _alert(self, severity: str, message: str) -> Dict[str, object]:
        return {"severity": severity, "message": message, "timestamp": _timestamp()}

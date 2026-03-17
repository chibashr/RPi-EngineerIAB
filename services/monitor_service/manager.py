"""Monitor Service implementation for metrics and alerts."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from datetime import datetime, timezone  # noqa: E402

from lib.module_logger import get_service_logger  # noqa: E402
from services.network_manager import NetworkManager  # noqa: E402
from services.system_manager import SystemManager  # noqa: E402

logger = get_service_logger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class MonitorService:
    """Collect metrics, health status, and alerts and push them via status_queue."""

    def __init__(self, status_queue=None) -> None:  # type: ignore[no-untyped-def]
        self._system_manager = SystemManager()
        self._network_manager = NetworkManager()
        self._status_queue = status_queue

    def set_status_queue(self, status_queue) -> None:  # type: ignore[no-untyped-def]
        self._status_queue = status_queue

    def get_status(self) -> dict[str, object]:
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
        self, system_status: dict[str, object], network_status: dict[str, object]
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        alerts: list[dict[str, object]] = []
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
            severity = "degraded" if severity != "unhealthy" else severity

        if cpu_percent >= 95:
            alerts.append(self._alert("warning", "CPU usage above 95%"))
            severity = "degraded" if severity != "unhealthy" else severity

        if temperature_c is not None:
            temp_value = float(temperature_c)
            if temp_value >= 85:
                alerts.append(self._alert("critical", "CPU temperature above 85 C"))
                severity = "unhealthy"
            elif temp_value >= 80:
                alerts.append(self._alert("warning", "CPU temperature above 80 C"))
                severity = "degraded" if severity != "unhealthy" else severity

        for name, status in services.items():
            if status != "running":
                alerts.append(self._alert("warning", f"Service {name} is {status}"))
                severity = "degraded" if severity != "unhealthy" else severity

        if severity != "healthy":
            logger.debug("Health check: %s (%d alerts)", severity, len(alerts))

        if network_status.get("wan_status") == "disconnected":
            alerts.append(self._alert("warning", "WAN connectivity is down"))
            severity = "degraded" if severity != "unhealthy" else severity

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

    def _alert(self, severity: str, message: str) -> dict[str, object]:
        return {"severity": severity, "message": message, "timestamp": _timestamp()}

    async def run(self, interval_seconds: float = 5.0) -> None:
        """Push core system + network metrics to status_queue on a fixed interval."""
        import asyncio

        while True:
            try:
                status = self.get_status()
                resources = status.get("metrics") or {}
                system_msg = {
                    "source": "system",
                    "type": "metrics",
                    "data": {
                        "cpu": resources.get("cpu_percent"),
                        "memory": resources.get("memory_percent"),
                        "disk": resources.get("disk_percent"),
                    },
                }
                network_msg = {
                    "source": "network",
                    "type": "interfaces",
                    "data": status.get("network") or {},
                }
                if self._status_queue is not None:
                    await self._status_queue.put(system_msg)
                    await self._status_queue.put(network_msg)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("MonitorService run loop error: %s", exc, exc_info=True)
            await asyncio.sleep(interval_seconds)

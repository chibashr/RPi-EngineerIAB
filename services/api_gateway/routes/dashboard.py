"""Dashboard API route – aggregates data for the advanced dashboard."""

from flask import Blueprint

from lib.module_logger import get_service_logger
from services.system_manager import SystemManager
from services.monitor_service import MonitorService
from services.logging_service import logging_service
from services.network_manager import NetworkManager
from services.capture_manager import capture_manager
from services.serial_manager import serial_manager
from services.remote_access_manager import RemoteAccessManager

from ..response import success_response

logger = get_service_logger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/v1/dashboard")
_system_manager = SystemManager()
_monitor_service = MonitorService()
_network_manager = NetworkManager()
_remote_manager = RemoteAccessManager()


@dashboard_bp.get("/status")
def get_dashboard_status():
    """Return aggregated dashboard data: system, network, captures, serial, remote."""
    data = {}

    # System status (resources, services, alerts)
    try:
        status = _system_manager.get_status()
        data["resources"] = status.get("resources", {})
        data["services"] = status.get("services", {})
        data["alerts"] = []
        try:
            monitor = _monitor_service.get_status()
            if monitor:
                data["alerts"] = list(monitor.get("alerts", []))
            log_alerts = logging_service.get_recent_log_alerts(limit=30)
            data["alerts"].extend(log_alerts)
            data["alerts"].sort(
                key=lambda a: (a.get("timestamp") or ""), reverse=True
            )
            data["alerts"] = data["alerts"][:50]
        except Exception as exc:
            logger.debug("Dashboard alerts fetch failed: %s", exc)
    except Exception as exc:
        logger.warning("Dashboard system status failed: %s", exc)
        data["resources"] = {}
        data["services"] = {}
        data["alerts"] = []

    # Network interfaces
    try:
        data["interfaces"] = _network_manager.list_interfaces().get(
            "interfaces", []
        )
    except Exception as exc:
        logger.debug("Dashboard interfaces fetch failed: %s", exc)
        data["interfaces"] = []

    # Active captures
    try:
        data["captures"] = capture_manager.list_active().get("captures", [])
    except Exception as exc:
        logger.debug("Dashboard captures fetch failed: %s", exc)
        data["captures"] = []

    # Serial devices
    try:
        data["devices"] = serial_manager.list_devices().get("devices", [])
    except Exception as exc:
        logger.debug("Dashboard devices fetch failed: %s", exc)
        data["devices"] = []

    # Remote access
    try:
        data["tools"] = _remote_manager.get_status().get("tools", [])
    except Exception as exc:
        logger.debug("Dashboard remote tools fetch failed: %s", exc)
        data["tools"] = []

    return success_response(data)

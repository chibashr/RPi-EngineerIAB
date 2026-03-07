"""Dashboard API routes — aggregated status for the dashboard UI."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter

from lib.module_logger import get_service_logger
from services.capture_manager import capture_manager
from services.logging_service import logging_service
from services.monitor_service import MonitorService
from services.network_manager import NetworkManager
from services.remote_access_manager import RemoteAccessManager
from services.serial_manager import serial_manager
from services.system_manager import SystemManager

from ..response import success_response

logger = get_service_logger(__name__)
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

_system_manager = SystemManager()
_network_manager = NetworkManager()
_monitor_service = MonitorService()
_remote_manager = RemoteAccessManager()


@dashboard_router.get("/status")
async def get_status():
    """Aggregated dashboard data: resources, services, interfaces, captures, devices, alerts, tools."""
    data: Dict[str, Any] = {
        "resources": {},
        "services": {},
        "interfaces": [],
        "captures": [],
        "devices": [],
        "alerts": [],
        "tools": [],
    }
    try:
        status = _system_manager.get_status()
        data["resources"] = status.get("resources") or {}
        data["services"] = status.get("services") or {}
    except Exception as exc:
        logger.debug("Dashboard system status: %s", exc)
    try:
        monitor = _monitor_service.get_status()
        if monitor:
            data["alerts"] = list(monitor.get("alerts", []))
    except Exception:
        pass
    try:
        log_alerts = logging_service.get_recent_log_alerts(limit=30)
        data["alerts"].extend(log_alerts)
        data["alerts"].sort(key=lambda a: (a.get("timestamp") or ""), reverse=True)
        data["alerts"] = data["alerts"][:50]
    except Exception:
        pass
    try:
        ifaces = _network_manager.list_interfaces()
        data["interfaces"] = list((ifaces.get("interfaces") or []))
    except Exception as exc:
        logger.debug("Dashboard network: %s", exc)
    try:
        active = capture_manager.list_active()
        data["captures"] = list((active.get("captures") or []))
    except Exception as exc:
        logger.debug("Dashboard capture: %s", exc)
    try:
        devices_data = await asyncio.to_thread(
            serial_manager.list_devices, force_refresh=False
        )
        data["devices"] = list((devices_data.get("devices") or []))
    except Exception as exc:
        logger.debug("Dashboard serial: %s", exc)
    try:
        remote = _remote_manager.get_status()
        data["tools"] = list((remote.get("tools") or []))
    except Exception as exc:
        logger.debug("Dashboard remote: %s", exc)
    return success_response(data)

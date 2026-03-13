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

    # Run blocking manager calls concurrently
    system_task = asyncio.to_thread(_system_manager.get_status)
    monitor_task = asyncio.to_thread(_monitor_service.get_status)
    network_task = asyncio.to_thread(_network_manager.list_interfaces)
    capture_task = asyncio.to_thread(capture_manager.list_active)
    serial_task = asyncio.to_thread(serial_manager.list_devices, force_refresh=False)
    remote_task = asyncio.to_thread(_remote_manager.get_status)

    results = await asyncio.gather(
        system_task,
        monitor_task,
        network_task,
        capture_task,
        serial_task,
        remote_task,
        return_exceptions=True,
    )

    system_result, monitor_result, network_result, capture_result, serial_result, remote_result = results

    if isinstance(system_result, Exception):
        logger.debug("Dashboard system status: %s", system_result)
    else:
        data["resources"] = system_result.get("resources") or {}
        data["services"] = system_result.get("services") or {}

    if isinstance(monitor_result, Exception):
        logger.debug("Dashboard monitor: %s", monitor_result)
    elif monitor_result:
        data["alerts"] = list(monitor_result.get("alerts", []))

    try:
        log_alerts = await asyncio.to_thread(
            logging_service.get_recent_log_alerts, limit=30
        )
        data["alerts"].extend(log_alerts)
        data["alerts"].sort(key=lambda a: (a.get("timestamp") or ""), reverse=True)
        data["alerts"] = data["alerts"][:50]
    except Exception as exc:
        logger.debug("Dashboard log alerts: %s", exc)

    if isinstance(network_result, Exception):
        logger.debug("Dashboard network: %s", network_result)
    else:
        data["interfaces"] = list((network_result.get("interfaces") or []))

    if isinstance(capture_result, Exception):
        logger.debug("Dashboard capture: %s", capture_result)
    else:
        data["captures"] = list((capture_result.get("captures") or []))

    if isinstance(serial_result, Exception):
        logger.debug("Dashboard serial: %s", serial_result)
    else:
        data["devices"] = list((serial_result.get("devices") or []))

    if isinstance(remote_result, Exception):
        logger.debug("Dashboard remote: %s", remote_result)
    else:
        data["tools"] = list((remote_result.get("tools") or []))

    return success_response(data)

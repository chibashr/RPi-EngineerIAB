"""
Dashboard API routes — aggregated status for the dashboard UI.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from lib.module_logger import get_service_logger
from services.module_manager import module_manager
from services.network_manager import NetworkManager
from services.system_manager import SystemManager

from ..response import error_response, success_response

dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = get_service_logger(__name__)
_system_manager = SystemManager()
_network_manager = NetworkManager()


def _collect_module_sessions() -> dict[str, Any]:
    """Ask enabled modules exposing get_active_sessions() for their active sessions."""
    active: dict[str, Any] = {}
    for module_id, record in module_manager._registry.items():  # type: ignore[attr-defined]
        if not record.enabled or record.state == "error":
            continue
        try:
            main_module = module_manager._load_module_main(record)  # type: ignore[attr-defined]
        except Exception:
            continue
        if not main_module or not hasattr(main_module, "get_active_sessions"):
            continue
        try:
            sessions = main_module.get_active_sessions()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("get_active_sessions failed for %s: %s", module_id, exc)
            continue
        if sessions:
            active[module_id] = sessions
    return active


@dashboard_router.get("/")
def get_dashboard():
    """Return aggregated dashboard payload."""
    try:
        system_status = _system_manager.get_status()
        network_status = _network_manager.get_status()
        modules_data = module_manager.list_modules()
        modules_list: list[dict[str, Any]] = modules_data.get("modules", [])
        enabled_modules = [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "enabled": bool(m.get("enabled")),
                "status": m.get("status") or ("enabled" if m.get("enabled") else "disabled"),
                "version": m.get("version"),
            }
            for m in modules_list
        ]
        active_sessions = _collect_module_sessions()
        payload = {
            "system": system_status,
            "network": network_status,
            "modules": enabled_modules,
            "active_sessions": active_sessions,
        }
        return success_response(payload)
    except Exception as exc:
        logger.exception("Dashboard aggregation failed: %s", exc)
        return error_response("INTERNAL_ERROR", "Dashboard aggregation failed", status_code=500)

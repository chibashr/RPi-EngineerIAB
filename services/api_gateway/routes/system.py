"""System API routes."""

from flask import Blueprint, request

from services.system_manager import SystemManager
from services.monitor_service import MonitorService
from services.logging_service import logging_service

from ..response import error_response, success_response

system_bp = Blueprint("system", __name__, url_prefix="/api/v1/system")
_system_manager = SystemManager()
_monitor_service = MonitorService()


@system_bp.get("/status")
def get_status():
    status = _system_manager.get_status()
    try:
        monitor = _monitor_service.get_status()
    except Exception:
        monitor = {}
    if monitor:
        status["health"] = monitor.get("health")
        status["alerts"] = list(monitor.get("alerts", []))
        status["monitor"] = monitor
    else:
        status["alerts"] = []
    try:
        log_alerts = logging_service.get_recent_log_alerts(limit=30)
        status["alerts"].extend(log_alerts)
        status["alerts"].sort(
            key=lambda a: (a.get("timestamp") or ""), reverse=True
        )
        status["alerts"] = status["alerts"][:50]
    except Exception:
        pass
    return success_response(status)


@system_bp.get("/services")
def list_services():
    return success_response(_system_manager.list_services())


@system_bp.post("/services")
def control_service():
    payload = request.get_json(silent=True) or {}
    service = payload.get("service")
    action = payload.get("action")
    if not service or not action:
        return error_response(
            "VALIDATION_ERROR",
            "Service and action are required",
            status_code=400,
        )
    try:
        result = _system_manager.control_service(service, action)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@system_bp.post("/services/bulk")
def control_services_bulk():
    payload = request.get_json(silent=True) or {}
    services = payload.get("services")
    action = payload.get("action")
    if not services or not isinstance(services, list) or not action:
        return error_response(
            "VALIDATION_ERROR",
            "services (array) and action are required",
            status_code=400,
        )
    try:
        results = _system_manager.control_services_bulk(services, action)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response({"results": results})


@system_bp.post("/power")
def power_action():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if not action:
        return error_response(
            "VALIDATION_ERROR", "Action is required", status_code=400
        )
    try:
        result = _system_manager.power_action(action)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@system_bp.get("/info")
def get_info():
    return success_response(_system_manager.get_info())


@system_bp.post("/settings")
def save_settings():
    payload = request.get_json(silent=True) or {}
    try:
        result = _system_manager.save_settings(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)

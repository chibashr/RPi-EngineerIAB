"""System API routes."""

from fastapi import APIRouter, Body

from lib.module_logger import get_service_logger
from services.system_manager import SystemManager
from services.monitor_service import MonitorService
from services.logging_service import logging_service

from ..response import error_response, success_response

logger = get_service_logger(__name__)
router = APIRouter(prefix="/api/v1/system", tags=["system"])
_system_manager = SystemManager()
_monitor_service = MonitorService()


@router.get("/status")
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


@router.get("/services")
def list_services():
    return success_response(_system_manager.list_services())


@router.post("/services")
def control_service(payload: dict | None = Body(default=None)):
    payload = payload or {}
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
        logger.info("Service control via API: %s %s", action, service)
    except ValueError as exc:
        logger.warning("Service control validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("Service control failed %s %s: %s", action, service, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Service control failed %s %s: %s", action, service, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@router.post("/services/bulk")
def control_services_bulk(payload: dict | None = Body(default=None)):
    payload = payload or {}
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
        logger.info("Bulk service control via API: %s (%d services)", action, len(services))
    except ValueError as exc:
        logger.warning("Bulk service control validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("Bulk service control failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Bulk service control failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response({"results": results})


@router.post("/power")
def power_action(payload: dict | None = Body(default=None)):
    payload = payload or {}
    action = payload.get("action")
    if not action:
        return error_response(
            "VALIDATION_ERROR", "Action is required", status_code=400
        )
    try:
        result = _system_manager.power_action(action)
        logger.warning("Power action via API: %s", action)
    except ValueError as exc:
        logger.warning("Power action validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("Power action failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Power action failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@router.get("/info")
def get_info():
    return success_response(_system_manager.get_info())


@router.post("/settings")
def save_settings(payload: dict | None = Body(default=None)):
    payload = payload or {}
    try:
        result = _system_manager.save_settings(payload)
        logger.info("System settings saved via API")
    except ValueError as exc:
        logger.warning("System settings validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("System settings save failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("System settings save failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)

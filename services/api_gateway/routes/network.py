"""Network API routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body

from lib.module_logger import get_service_logger
from services.network_manager import NetworkManager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
network_router = APIRouter(prefix="/api/v1/network", tags=["network"])
_network_manager = NetworkManager()


@network_router.get("/interfaces")
def list_interfaces():
    return success_response(_network_manager.list_interfaces())


@network_router.get("/interfaces/{interface_id}")
def get_interface(interface_id: str):
    try:
        data = _network_manager.get_interface(interface_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@network_router.put("/interfaces/{interface_id}")
def update_interface(interface_id: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        data = _network_manager.update_interface(interface_id, data_in)
        logger.info("Interface updated via API: %s mode=%s", interface_id, data.get("mode"))
    except KeyError as exc:
        logger.warning("Interface update not found: %s", interface_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except ValueError as exc:
        logger.warning("Interface update validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Interface update failed %s: %s", interface_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_router.get("/routes")
def list_routes():
    return success_response(_network_manager.list_routes())


@network_router.get("/routes/current")
def list_current_routes():
    return success_response(_network_manager.list_current_routes())


@network_router.post("/routes")
def add_route(payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        data = _network_manager.add_route(data_in)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@network_router.get("/profiles")
def list_profiles():
    return success_response(_network_manager.list_profiles())


@network_router.post("/profiles")
def save_profile(payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        data = _network_manager.save_profile(data_in)
        logger.info("Network profile saved via API: %s", data.get("name"))
    except ValueError as exc:
        logger.warning("Profile save validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Profile save failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@network_router.post("/profiles/{profile_name}/load")
def load_profile(profile_name: str):
    try:
        data = _network_manager.load_profile(profile_name)
        logger.info("Network profile loaded via API: %s", profile_name)
    except KeyError as exc:
        logger.warning("Profile load not found: %s", profile_name)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Profile load failed %s: %s", profile_name, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_router.put("/profiles/{profile_name}")
def update_profile(profile_name: str, payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        data = _network_manager.update_profile(profile_name, data_in)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_router.delete("/profiles/{profile_name}")
def delete_profile(profile_name: str):
    try:
        data = _network_manager.delete_profile(profile_name)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_router.get("/status")
def get_status():
    return success_response(_network_manager.get_status())


@network_router.post("/wan-priority")
def ensure_wan_priority():
    """Check internet capability and set WAN to preferred interface (USB then ethernet); failover if current is lost."""
    try:
        data = _network_manager.ensure_wan_priority()
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_router.post("/reset")
def reset_network(payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    preserve_hotspot = data_in.get("preserve_hotspot", False)
    try:
        result = _network_manager.reset_network(preserve_hotspot=preserve_hotspot)
        logger.info("Network reset via API (preserve_hotspot=%s)", preserve_hotspot)
    except RuntimeError as exc:
        logger.error("Network reset failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Network reset failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@network_router.post("/vlans")
def create_vlan(payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        result = _network_manager.create_vlan(data_in)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result, status_code=201)


@network_router.post("/hotspot")
def configure_hotspot(payload: Optional[Dict[str, Any]] = Body(default=None)):
    data_in = payload or {}
    try:
        result = _network_manager.configure_hotspot(data_in)
        logger.info("Hotspot configured via API: ssid=%s", result.get("ssid"))
    except ValueError as exc:
        logger.warning("Hotspot config validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("Hotspot config failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Hotspot config failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)

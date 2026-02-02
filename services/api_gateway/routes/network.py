"""Network API routes."""

from flask import Blueprint, request

from services.network_manager import NetworkManager

from ..response import error_response, success_response

network_bp = Blueprint("network", __name__, url_prefix="/api/v1/network")
_network_manager = NetworkManager()


@network_bp.get("/interfaces")
def list_interfaces():
    return success_response(_network_manager.list_interfaces())


@network_bp.get("/interfaces/<interface_id>")
def get_interface(interface_id: str):
    try:
        data = _network_manager.get_interface(interface_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@network_bp.put("/interfaces/<interface_id>")
def update_interface(interface_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        data = _network_manager.update_interface(interface_id, payload)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_bp.get("/routes")
def list_routes():
    return success_response(_network_manager.list_routes())


@network_bp.post("/routes")
def add_route():
    payload = request.get_json(silent=True) or {}
    try:
        data = _network_manager.add_route(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@network_bp.get("/profiles")
def list_profiles():
    return success_response(_network_manager.list_profiles())


@network_bp.post("/profiles")
def save_profile():
    payload = request.get_json(silent=True) or {}
    try:
        data = _network_manager.save_profile(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@network_bp.post("/profiles/<profile_name>/load")
def load_profile(profile_name: str):
    try:
        data = _network_manager.load_profile(profile_name)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@network_bp.get("/status")
def get_status():
    return success_response(_network_manager.get_status())


@network_bp.post("/reset")
def reset_network():
    payload = request.get_json(silent=True) or {}
    preserve_hotspot = payload.get("preserve_hotspot", False)
    try:
        result = _network_manager.reset_network(preserve_hotspot=preserve_hotspot)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@network_bp.post("/vlans")
def create_vlan():
    payload = request.get_json(silent=True) or {}
    try:
        result = _network_manager.create_vlan(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result, status_code=201)


@network_bp.post("/hotspot")
def configure_hotspot():
    payload = request.get_json(silent=True) or {}
    try:
        result = _network_manager.configure_hotspot(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)

"""Modules API routes."""

from flask import Blueprint, request

from services.module_manager import module_manager

from ..response import error_response, success_response

modules_bp = Blueprint("modules", __name__, url_prefix="/api/v1/modules")


@modules_bp.get("/list")
def list_modules():
    try:
        payload = module_manager.list_modules()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_bp.post("/install")
def install_module():
    payload = request.get_json(silent=True) or {}
    try:
        result = module_manager.install_module(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.delete("/uninstall/<module_id>")
def uninstall_module(module_id: str):
    try:
        result = module_manager.uninstall_module(module_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.post("/enable/<module_id>")
def enable_module(module_id: str):
    try:
        result = module_manager.enable_module(module_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.post("/disable/<module_id>")
def disable_module(module_id: str):
    try:
        result = module_manager.disable_module(module_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.get("/components")
def list_components():
    try:
        payload = {"components": module_manager.get_web_components()}
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)

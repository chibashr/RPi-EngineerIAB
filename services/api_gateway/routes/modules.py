"""Modules API routes."""

from flask import Blueprint, request

from lib.module_logger import get_service_logger
from services.module_manager import module_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
modules_bp = Blueprint("modules", __name__, url_prefix="/api/v1/modules")


@modules_bp.get("/list")
def list_modules():
    try:
        payload = module_manager.list_modules()
    except Exception as exc:
        logger.exception("Module list failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_bp.post("/install")
def install_module():
    payload = request.get_json(silent=True) or {}
    try:
        result = module_manager.install_module(payload)
        logger.info("Module installed via API: %s", result.get("module_id", "unknown"))
    except ValueError as exc:
        logger.warning("Module install validation error: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except RuntimeError as exc:
        logger.error("Module install failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Module install failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.delete("/uninstall/<module_id>")
def uninstall_module(module_id: str):
    try:
        result = module_manager.uninstall_module(module_id)
        logger.info("Module uninstalled via API: %s", module_id)
    except KeyError as exc:
        logger.warning("Module uninstall not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Module uninstall failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.post("/enable/<module_id>")
def enable_module(module_id: str):
    try:
        result = module_manager.enable_module(module_id)
        logger.info("Module enabled via API: %s", module_id)
    except KeyError as exc:
        logger.warning("Module enable not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Module enable failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.post("/disable/<module_id>")
def disable_module(module_id: str):
    try:
        result = module_manager.disable_module(module_id)
        logger.info("Module disabled via API: %s", module_id)
    except KeyError as exc:
        logger.warning("Module disable not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Module disable failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.get("/components")
def list_components():
    try:
        payload = {"components": module_manager.get_web_components()}
    except Exception as exc:
        logger.exception("Module components fetch failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_bp.get("/available")
def list_available():
    """List modules available in the app update repo (install or update from there)."""
    try:
        payload = module_manager.list_available_from_repo()
    except Exception as exc:
        logger.exception("Module available list failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_bp.post("/install-from-repo")
def install_from_repo():
    payload = request.get_json(silent=True) or {}
    module_id = payload.get("module_id") or (request.form.get("module_id") if request.form else None)
    if not module_id:
        return error_response("VALIDATION_ERROR", "module_id is required", status_code=400)
    try:
        result = module_manager.install_module_from_repo(str(module_id).strip())
        logger.info("Module installed from repo via API: %s", module_id)
    except ValueError as exc:
        logger.warning("Module install-from-repo validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except KeyError as exc:
        logger.warning("Module install-from-repo not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except RuntimeError as exc:
        logger.error("Module install-from-repo failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover
        logger.exception("Module install-from-repo failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)


@modules_bp.get("/updates")
def check_module_updates():
    """Check which installed modules have updates available in the repo."""
    try:
        payload = module_manager.check_module_updates()
    except Exception as exc:
        logger.exception("Module updates check failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_bp.post("/update/<module_id>")
def update_module(module_id: str):
    """Update an installed module from the repo."""
    try:
        result = module_manager.update_module(module_id)
        logger.info("Module updated via API: %s", module_id)
    except KeyError as exc:
        logger.warning("Module update not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except RuntimeError as exc:
        logger.error("Module update failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover
        logger.exception("Module update failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(result)

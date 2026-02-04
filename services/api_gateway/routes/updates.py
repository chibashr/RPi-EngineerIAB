"""Updates API routes."""

from flask import Blueprint

from lib.module_logger import get_service_logger
from services.update_manager import update_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
updates_bp = Blueprint("updates", __name__, url_prefix="/api/v1/updates")


@updates_bp.get("/check")
def check_updates():
    try:
        payload = update_manager.check_for_updates()
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@updates_bp.post("/apply")
def apply_update():
    try:
        payload = update_manager.apply_update()
    except RuntimeError as exc:
        logger.exception("Updates apply failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Updates apply failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@updates_bp.post("/reconfigure")
def reconfigure():
    """Re-run install script in reconfigure mode (existing config). Requires sudo for install.sh."""
    try:
        payload = update_manager.run_reconfigure()
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@updates_bp.post("/reinstall")
def reinstall_from_scratch():
    """Run install script in reinstall_from_scratch mode (full reinstall using existing config). Requires sudo for install.sh."""
    try:
        payload = update_manager.run_reinstall_from_scratch()
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@updates_bp.post("/rollback")
def rollback_update():
    try:
        payload = update_manager.rollback_update()
    except RuntimeError as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    except Exception as exc:  # pragma: no cover - defensive
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)

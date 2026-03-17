"""Modules API routes."""

from typing import Any

from fastapi import APIRouter, Body, Depends

from lib.module_logger import get_service_logger
from services.api_gateway.routes.auth import require_admin
from services.module_manager import module_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
modules_router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


def _load_allowlist(path: str) -> list:
    try:
        with open(path) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return []


# Route hot-reload requires app restart or APIRouter re-mount — address in Phase 4 (module_manager migration)
# enable/disable/install update module_manager state; dynamic route mounting not implemented here.


@modules_router.get("/list")
def list_modules():
    """Return list of modules: [{id, name, enabled, status, version}]."""
    try:
        data = module_manager.list_modules()
        modules = data.get("modules", [])
        payload = [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "enabled": bool(m.get("enabled")),
                "status": m.get("status") or ("enabled" if m.get("enabled") else "disabled"),
                "version": m.get("version"),
            }
            for m in modules
        ]
    except Exception as exc:
        logger.exception("Module list failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_router.post("/enable/{module_id}")
def enable_module(module_id: str, _: str = Depends(require_admin)):
    try:
        module_manager.enable_module(module_id)
        logger.info("Module enabled via API (restart required): %s", module_id)
    except KeyError as exc:
        logger.warning("Module enable not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Module enable failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response({"restart_required": True})


@modules_router.post("/disable/{module_id}")
def disable_module(module_id: str, _: str = Depends(require_admin)):
    try:
        module_manager.disable_module(module_id)
        logger.info("Module disabled via API (restart required): %s", module_id)
    except KeyError as exc:
        logger.warning("Module disable not found: %s", module_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except Exception as exc:
        logger.exception("Module disable failed %s: %s", module_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response({"restart_required": True})


@modules_router.get("/components")
def list_components():
    try:
        payload = {"components": module_manager.get_web_components()}
    except Exception as exc:
        logger.exception("Module components fetch failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_router.get("/available")
def list_available():
    """Deprecated endpoint (Phase 1 compatibility)."""
    return error_response("NOT_IMPLEMENTED", "Endpoint removed", status_code=410)


@modules_router.post("/install-from-repo")
def install_from_repo(payload: dict[str, Any] | None = Body(default=None), _: str = Depends(require_admin)):
    """Deprecated endpoint (Phase 1 compatibility)."""
    return error_response("NOT_IMPLEMENTED", "Endpoint removed", status_code=410)

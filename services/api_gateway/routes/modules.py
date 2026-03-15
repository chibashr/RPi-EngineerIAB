"""Modules API routes."""

import os
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from lib.audit import audit_log
from lib.module_logger import get_service_logger
from services.api_gateway.routes.auth import require_admin
from services.module_manager import module_manager
from services.module_manager.manager import DEFAULT_UPDATE_REPO

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
    try:
        payload = module_manager.list_modules()
    except Exception as exc:
        logger.exception("Module list failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_router.post("/install")
def install_module(payload: dict[str, Any] | None = Body(default=None), _: str = Depends(require_admin)):
    data_in = payload or {}
    module_name = data_in.get("module_id")
    if module_name is not None:
        module_name = str(module_name).strip()
    allowed = _load_allowlist("config/modules-allowed.conf")
    if not allowed or module_name not in allowed:
        audit_log({"event": "module_install_blocked", "module": module_name, "reason": "not in allowlist"})
        raise HTTPException(status_code=403, detail="module not in allowlist")
    audit_log({"event": "module_install_allowed", "module": module_name})
    try:
        result = module_manager.install_module(data_in)
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


@modules_router.delete("/uninstall/{module_id}")
def uninstall_module(module_id: str, _: str = Depends(require_admin)):
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


@modules_router.post("/enable/{module_id}")
def enable_module(module_id: str, _: str = Depends(require_admin)):
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


@modules_router.post("/disable/{module_id}")
def disable_module(module_id: str, _: str = Depends(require_admin)):
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
    """List modules available in the app update repo (install or update from there)."""
    try:
        payload = module_manager.list_available_from_repo()
    except Exception as exc:
        logger.exception("Module available list failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_router.post("/install-from-repo")
def install_from_repo(payload: dict[str, Any] | None = Body(default=None), _: str = Depends(require_admin)):
    data_in = payload or {}
    module_id = data_in.get("module_id")
    if not module_id:
        return error_response("VALIDATION_ERROR", "module_id is required", status_code=400)
    module_id = str(module_id).strip()
    repo_url = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
    allowed_repos = _load_allowlist("config/modules-allowed-repos.conf")
    if not allowed_repos or not any(repo_url.startswith(p) for p in allowed_repos):
        audit_log({"event": "module_repo_blocked", "url": repo_url, "reason": "repo not in allowlist"})
        raise HTTPException(status_code=403, detail="repo URL not permitted")
    audit_log({"event": "module_repo_allowed", "url": repo_url})
    try:
        result = module_manager.install_module_from_repo(module_id)
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


@modules_router.get("/updates")
def check_module_updates():
    """Check which installed modules have updates available in the repo."""
    try:
        payload = module_manager.check_module_updates()
    except Exception as exc:
        logger.exception("Module updates check failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@modules_router.post("/update/{module_id}")
def update_module(module_id: str, _: str = Depends(require_admin)):
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

"""Remote console (SSH/Telnet) API routes. Admin-only."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from lib.audit import audit_log
from lib.module_logger import get_service_logger
from services.api_gateway.routes.auth import require_admin
from services.remote_console_manager import remote_console_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
router = APIRouter(prefix="/api/v1/remote-console", tags=["remote-console"])


@router.get("/targets")
def list_targets(_: str = Depends(require_admin)):
    return success_response(remote_console_manager.list_targets())


@router.get("/targets/{target_id}")
def get_target(target_id: str, _: str = Depends(require_admin)):
    try:
        data = remote_console_manager.get_target(target_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.post("/targets")
def create_target(
    payload: dict | None = Body(default=None),
    _: str = Depends(require_admin),
):
    payload = payload or {}
    try:
        data = remote_console_manager.create_target(payload)
        audit_log({"event": "remote_console_target_created", "target_id": data.get("id", "")[:8]})
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    return success_response(data, status_code=201)


@router.put("/targets/{target_id}")
def update_target(
    target_id: str,
    payload: dict | None = Body(default=None),
    _: str = Depends(require_admin),
):
    payload = payload or {}
    try:
        data = remote_console_manager.update_target(target_id, payload)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.delete("/targets/{target_id}")
def delete_target(target_id: str, _: str = Depends(require_admin)):
    try:
        data = remote_console_manager.delete_target(target_id)
        audit_log({"event": "remote_console_target_deleted", "target_id": target_id[:8]})
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.get("/sessions")
def list_sessions(_: str = Depends(require_admin)):
    return success_response(remote_console_manager.list_sessions())


@router.post("/sessions")
def create_session(
    payload: dict | None = Body(default=None),
    _: str = Depends(require_admin),
):
    payload = payload or {}
    logger.info("create_session API: target_id=%s host=%s", payload.get("target_id"), payload.get("host"))
    try:
        data = remote_console_manager.create_session(payload)
        audit_log(
            {
                "event": "remote_console_session_created",
                "session_id": data.get("session_id", "")[:8],
                "host": data.get("host"),
            }
        )
    except ValueError as exc:
        logger.warning("Remote console session create validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except KeyError as exc:
        logger.warning("Remote console session create target not found: %s", exc)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except RuntimeError as exc:
        logger.error("Remote console session create failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, _: str = Depends(require_admin)):
    try:
        data = remote_console_manager.get_session(session_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, _: str = Depends(require_admin)):
    try:
        data = remote_console_manager.delete_session(session_id)
        audit_log({"event": "remote_console_session_deleted", "session_id": session_id[:8]})
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)

"""Remote access API routes."""

from fastapi import APIRouter, Body, HTTPException

from services.remote_access_manager import RemoteAccessManager

from ..response import error_response, success_response

remote_router = APIRouter(prefix="/api/v1/remote", tags=["remote"])
_remote_manager = RemoteAccessManager()


@remote_router.get("/status")
def remote_status():
    return success_response(_remote_manager.get_status())


@remote_router.get("/info")
def remote_info():
    return success_response(_remote_manager.get_info())


@remote_router.post("/password")
def remote_set_password(body: dict = Body(default=None)):
    """Set unattended access password for AnyDesk or TeamViewer. Requires sudo for bin/set-remote-password.sh."""
    body = body or {}
    tool = body.get("tool")
    password = body.get("password")
    if not tool or not isinstance(password, str):
        raise HTTPException(status_code=400, detail="tool and password are required")
    err = _remote_manager.set_password(tool, password)
    if err:
        raise HTTPException(status_code=500, detail=err)
    return success_response({"ok": True})


@remote_router.post("/teamviewer/reset-password")
def teamviewer_reset_password(body: dict = Body(default=None)):
    """Set TeamViewer static password. Password must be 6-8 characters (TeamViewer Linux requirements)."""
    body = body or {}
    password = body.get("password")
    if not isinstance(password, str) or not password:
        return error_response("INVALID_INPUT", "password is required", status_code=400)
    if len(password) < 6:
        return error_response(
            "INVALID_INPUT",
            "Password must be at least 6 characters (TeamViewer requirement)",
            status_code=400,
        )
    if len(password) > 8:
        return error_response(
            "INVALID_INPUT",
            "Password must be at most 8 characters (TeamViewer Linux limit)",
            status_code=400,
        )
    err = _remote_manager.set_teamviewer_password(password)
    if err:
        return error_response("SET_PASSWORD_FAILED", err, status_code=500)
    return success_response({"password": password})

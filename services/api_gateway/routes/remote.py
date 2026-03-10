"""Remote access API routes."""

from fastapi import APIRouter, Body, HTTPException

from services.remote_access_manager import RemoteAccessManager

from ..response import success_response

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

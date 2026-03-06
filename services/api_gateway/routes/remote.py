"""Remote access API routes."""

from fastapi import APIRouter

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

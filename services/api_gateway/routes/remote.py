"""Remote access API routes."""

from flask import Blueprint

from services.remote_access_manager import RemoteAccessManager

from ..response import success_response

remote_bp = Blueprint("remote", __name__, url_prefix="/api/v1/remote")
_remote_manager = RemoteAccessManager()


@remote_bp.get("/status")
def remote_status():
    return success_response(_remote_manager.get_status())


@remote_bp.get("/info")
def remote_info():
    return success_response(_remote_manager.get_info())

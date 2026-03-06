"""Example module API routes."""

from fastapi import APIRouter

from services.api_gateway.response import error_response, success_response
from services.module_manager import module_manager

router = APIRouter(tags=["example_module"])


@router.get("/hello")
def hello():
    if not module_manager.is_enabled("example_module"):
        return error_response("CONFLICT", "Module is disabled", status_code=409)
    return success_response({"message": "Example module is active."})

"""Example module API routes."""

from flask import Blueprint

from services.api_gateway.response import error_response, success_response
from services.module_manager import module_manager

example_bp = Blueprint("example_module", __name__, url_prefix="/api/v1/example")


@example_bp.get("/hello")
def hello():
    if not module_manager.is_enabled("example_module"):
        return error_response("CONFLICT", "Module is disabled", status_code=409)
    return success_response({"message": "Example module is active."})


def register_routes(app) -> None:  # type: ignore[no-untyped-def]
    app.register_blueprint(example_bp)

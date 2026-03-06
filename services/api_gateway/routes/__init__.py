"""API route registrations for the gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter

from services.api_gateway.response import success_response
from services.api_gateway.routes.backup import backup_router
from services.api_gateway.routes.capture import capture_router
from services.api_gateway.routes.logs import logs_router
from services.api_gateway.routes.modules import modules_router
from services.api_gateway.routes.network import network_router
from services.api_gateway.routes.remote import remote_router
from services.api_gateway.routes.serial import router as serial_router
from services.api_gateway.routes.system import router as system_router
from services.api_gateway.routes.updates import updates_router

if TYPE_CHECKING:
    from fastapi import FastAPI

# Stub routers for Phase 1 — full migration in Phase 3.
# module_manager.register_module_routes deferred until Phase 6.

_STUB_MESSAGE = {"message": "Migration in progress", "phase": 1}


def _stub_router(name: str, prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[name])

    @router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def _stub(path: str):
        return success_response(_STUB_MESSAGE, status_code=501)

    @router.api_route("", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def _stub_root():
        return success_response(_STUB_MESSAGE, status_code=501)

    return router


def register_routes(app: "FastAPI") -> None:
    """Register API routers on the FastAPI app."""
    app.include_router(network_router)
    app.include_router(system_router)
    app.include_router(capture_router)
    app.include_router(modules_router)
    app.include_router(remote_router)
    app.include_router(updates_router)
    app.include_router(backup_router)
    app.include_router(logs_router)
    app.include_router(serial_router)

    prefixes = [
        ("dashboard", "/api/v1/dashboard"),
    ]
    for name, prefix in prefixes:
        app.include_router(_stub_router(name, prefix))

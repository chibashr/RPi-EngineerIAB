"""API route registrations for the gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.api_gateway.routes.auth import auth_router
from services.api_gateway.routes.backup import backup_router
from services.api_gateway.routes.dashboard import dashboard_router
from services.api_gateway.routes.logs import logs_router
from services.api_gateway.routes.modules import modules_router
from services.api_gateway.routes.network import network_router
from services.api_gateway.routes.remote import remote_router
from services.api_gateway.routes.system import router as system_router
from services.api_gateway.routes.updates import updates_router

if TYPE_CHECKING:
    from fastapi import FastAPI


def register_routes(app: FastAPI) -> None:
    """Register core API routers on the FastAPI app.

    Module-specific routers (serial, capture, remote_console, syslog, snmp_traps, fileshare)
    are registered via services.module_manager.
    """
    app.include_router(auth_router)
    app.include_router(network_router)
    app.include_router(system_router)
    app.include_router(modules_router)
    app.include_router(remote_router)
    app.include_router(updates_router)
    app.include_router(backup_router)
    app.include_router(logs_router)
    app.include_router(dashboard_router)

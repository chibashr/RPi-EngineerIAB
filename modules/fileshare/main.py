from __future__ import annotations

import asyncio

from fastapi import FastAPI

from lib.module_logger import get_service_logger

from .api import router as fileshare_router
from .manager import initialize_fileshare

logger = get_service_logger("fileshare")


def initialize(app: FastAPI, status_queue: asyncio.Queue) -> None:  # noqa: ARG001
    app.include_router(fileshare_router, prefix="/api/v1/fileshare", tags=["fileshare"])
    try:
        initialize_fileshare()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Fileshare initialize failed: %s", exc)

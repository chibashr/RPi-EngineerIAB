from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI

from lib.module_logger import get_service_logger
from modules.syslog_receiver import receiver

from .api import router as syslog_router

logger = get_service_logger("syslog")

_status_task: asyncio.Task | None = None
_status_queue: asyncio.Queue | None = None


async def _status_worker() -> None:
    assert _status_queue is not None
    while True:
        try:
            status = receiver.get_status()
            payload: dict[str, Any] = {
                "source": "syslog",
                "type": "status",
                "data": {
                    "running": bool(status.get("running")),
                    "stored_count": int(status.get("stored_count") or 0),
                },
            }
            await _status_queue.put(payload)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("syslog status worker error: %s", exc)
        await asyncio.sleep(30.0)


def initialize(app: FastAPI, status_queue: asyncio.Queue) -> None:
    global _status_queue, _status_task

    _status_queue = status_queue

    app.include_router(syslog_router, prefix="/api/v1/syslog", tags=["syslog"])

    try:
        receiver.start_receiver()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to start syslog receiver during initialize: %s", exc)

    loop = asyncio.get_event_loop()
    if _status_task is None or _status_task.done():
        _status_task = loop.create_task(_status_worker())

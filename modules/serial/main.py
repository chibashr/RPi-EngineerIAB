from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI, WebSocket

from lib.module_logger import get_service_logger
from lib.session_manager import SessionManager

from .api import router as serial_router
from .manager import get_serial_manager

logger = get_service_logger("serial")

_status_task: asyncio.Task | None = None
_status_queue: asyncio.Queue | None = None
_session_manager = SessionManager()


async def _serial_status_worker() -> None:
    assert _status_queue is not None
    manager = get_serial_manager()
    last_ids: list[str] = []
    while True:
        try:
            current_ids = manager.get_active_session_ids()
            if current_ids != last_ids:
                payload = {
                    "source": "serial",
                    "type": "session_activity",
                    "data": {
                        "active_sessions": len(current_ids),
                        "session_ids": current_ids,
                    },
                }
                await _status_queue.put(payload)
                last_ids = current_ids
        except Exception as exc:  # pragma: no cover - guard loop
            logger.warning("serial status worker error: %s", exc)
        await asyncio.sleep(2.0)


def initialize(app: FastAPI, status_queue: asyncio.Queue) -> None:
    global _status_queue, _status_task

    _status_queue = status_queue

    app.include_router(serial_router, prefix="/api/v1/serial", tags=["serial"])

    loop = asyncio.get_event_loop()
    if _status_task is None or _status_task.done():
        _status_task = loop.create_task(_serial_status_worker())


def register_websockets(app: FastAPI) -> None:
    manager = get_serial_manager()

    async def _read_cb_factory(session_id: str) -> Callable[[bytes], None]:
        def _read_cb(data: bytes) -> None:
            try:
                manager.record_tx(session_id, data)
            except Exception:
                return

        return _read_cb

    def _write_cb_factory(session_id: str) -> Callable[[], AsyncIterator[bytes]]:
        async def _writer() -> AsyncIterator[bytes]:
            while True:
                await asyncio.sleep(1.0)
                if not manager.get_session_record(session_id).status == "active":
                    break
                if False:
                    yield b""

        return _writer

    @app.websocket("/ws/serial/{session_id}")
    async def serial_websocket(websocket: WebSocket, session_id: str) -> None:  # type: ignore[override]
        try:
            manager.get_session_record(session_id)
        except KeyError:
            await websocket.close(code=1000)
            return

        _session_manager.create_session(session_id, target=session_id)

        read_cb = await _read_cb_factory(session_id)
        write_cb = _write_cb_factory(session_id)

        await _session_manager.handle_websocket(
            websocket=websocket,
            session_id=session_id,
            read_cb=read_cb,
            write_cb=write_cb,
        )

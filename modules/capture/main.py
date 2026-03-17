from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import FastAPI, WebSocket

from lib.module_logger import get_service_logger

from .api import router as capture_router
from .manager import CaptureManager, get_capture_manager

logger = get_service_logger("capture")

_status_task: asyncio.Task | None = None
_status_queue: asyncio.Queue | None = None


async def _capture_status_worker(manager: CaptureManager) -> None:
    assert _status_queue is not None
    last_ids: list[str] = []
    while True:
        try:
            current_ids = manager.get_active_capture_ids()
            if current_ids != last_ids:
                payload = {
                    "source": "capture",
                    "type": "capture_activity",
                    "data": {
                        "active_captures": len(current_ids),
                        "capture_ids": current_ids,
                    },
                }
                await _status_queue.put(payload)
                last_ids = current_ids
        except Exception as exc:  # pragma: no cover - guard loop
            logger.warning("capture status worker error: %s", exc)
        await asyncio.sleep(2.0)


def initialize(app: FastAPI, status_queue: asyncio.Queue) -> None:
    global _status_queue, _status_task

    _status_queue = status_queue

    app.include_router(capture_router, prefix="/api/v1/capture", tags=["capture"])

    loop = asyncio.get_event_loop()
    manager = get_capture_manager()
    if _status_task is None or _status_task.done():
        _status_task = loop.create_task(_capture_status_worker(manager))


def register_websockets(app: FastAPI) -> None:
    manager = get_capture_manager()

    async def _stream_capture(path: str) -> AsyncIterator[bytes]:
        process = await asyncio.create_subprocess_exec(
            "tshark",
            "-l",
            "-r",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert process.stdout is not None
        try:
            while True:
                chunk = await process.stdout.read(1024)
                if not chunk:
                    break
                yield chunk
        finally:
            if process.returncode is None:
                process.terminate()
                with contextlib.suppress(ProcessLookupError):
                    await process.wait()

    @app.websocket("/ws/capture/{capture_id}")
    async def capture_websocket(websocket: WebSocket, capture_id: str) -> None:  # type: ignore[override]

        from starlette.websockets import WebSocketDisconnect

        try:
            path = manager.get_capture_file_path(capture_id)
        except FileNotFoundError:
            await websocket.close(code=1000)
            return

        await websocket.accept()

        async def _reader() -> None:
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                return

        async def _writer() -> None:
            try:
                async for chunk in _stream_capture(str(path)):
                    await websocket.send_bytes(chunk)
            except WebSocketDisconnect:
                return

        reader_task = asyncio.create_task(_reader())
        writer_task = asyncio.create_task(_writer())
        try:
            await asyncio.gather(reader_task, writer_task)
        finally:
            if not reader_task.done():
                reader_task.cancel()
            if not writer_task.done():
                writer_task.cancel()

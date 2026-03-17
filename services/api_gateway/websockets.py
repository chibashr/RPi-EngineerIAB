"""WebSocket endpoints for serial console, capture streaming, and update progress.

Migrated from flask-sock to FastAPI native WebSockets.
"""

from __future__ import annotations

import asyncio
import json
import queue
import time
from typing import TYPE_CHECKING, Any

from fastapi import Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from lib.audit import audit_log
from lib.module_logger import get_api_logger
from services.auth_service.manager import verify_token
from services.monitor_service import MonitorService
from services.network_manager import NetworkManager
from services.system_manager import SystemManager
from services.update_manager import update_manager

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_api_logger(__name__)
_system_manager = SystemManager()
_network_manager = NetworkManager()
_monitor_service = MonitorService()

CAPTURE_PERMISSION_HINT = (
    " Give dumpcap permission to capture: "
    "sudo setcap cap_net_raw,cap_net_admin=eip $(which dumpcap); "
    "or run the API as root. See Capture issues in Documentation."
)


def _capture_error_message(stderr: str, is_active: bool) -> str:
    """Turn tshark/dumpcap stderr into a user-friendly message."""
    err = stderr.strip()[:500]
    if "Permission denied" in err and ("dumpcap" in err or "Couldn't run" in err):
        return "Live capture requires permission to capture packets. " "dumpcap could not run (Permission denied)." + (
            CAPTURE_PERMISSION_HINT if is_active else ""
        )
    return f"tshark exited: {err}"


def register_websockets(app: FastAPI, *, status_queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Register WebSocket routes on the FastAPI app."""

    # ------------------------------------------------------------------
    # /ws/status: broadcast messages from status_queue to all clients.
    # Core metrics are pushed by monitor_service; modules push their own.
    # ------------------------------------------------------------------

    connections: set[WebSocket] = set()

    async def _status_broadcaster() -> None:
        """Background task that reads from status_queue and fan-outs to clients."""
        while True:
            msg: dict[str, Any] = await status_queue.get()
            if not isinstance(msg, dict):
                continue
            # Backwards-compat shim: if legacy shape, preserve type=data mapping.
            try:
                payload = json.dumps(msg)
            except TypeError:
                continue
            dead: list[WebSocket] = []
            for ws in list(connections):
                try:
                    await ws.send_text(payload)
                except WebSocketDisconnect:
                    dead.append(ws)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                connections.discard(ws)

    @app.on_event("startup")
    async def _start_status_broadcaster() -> None:
        asyncio.create_task(_status_broadcaster())

    @app.websocket("/ws/status")
    async def status_stream(websocket: WebSocket) -> None:
        client = websocket.client.host if websocket.client else "unknown"
        logger.info("WS connect path=/ws/status client=%s", client)
        start = time.monotonic()
        await websocket.accept()
        connections.add(websocket)
        try:
            while True:
                try:
                    msg = await websocket.receive_text()
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
                try:
                    data = json.loads(msg) if msg else {}
                except json.JSONDecodeError:
                    data = {}
                if isinstance(data, dict) and data.get("type") == "ping":
                    try:
                        await websocket.send_json({"type": "pong"})
                    except Exception:
                        break
        finally:
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/status client=%s duration_s=%.1f",
                client,
                duration,
            )
            connections.discard(websocket)

    @app.websocket("/ws/serial/{session_id}")
    async def serial_console(
        websocket: WebSocket, session_id: str
    ) -> None:  # pragma: no cover - preserved for legacy clients
        await websocket.close(code=1000)

    @app.websocket("/ws/remote-console/{session_id}")
    async def remote_console_ws(
        websocket: WebSocket, session_id: str
    ) -> None:  # pragma: no cover - preserved for legacy clients
        await websocket.close(code=1000)

    @app.websocket("/ws/updates/apply")
    async def updates_apply_stream(websocket: WebSocket, token: str = Query(None)) -> None:
        if not verify_token(token):
            audit_log({"event": "ws_auth_rejected", "path": "/ws/updates/apply"})
            await websocket.close(code=1008)
            return
        audit_log({"event": "ws_auth_accepted", "path": "/ws/updates/apply"})
        client = websocket.client.host if websocket.client else "unknown"
        logger.info("WS connect path=/ws/updates/apply client=%s", client)
        start = time.monotonic()
        tx_count = 0
        await websocket.accept()
        progress_queue: queue.Queue = queue.Queue()

        def progress_callback(line: str) -> None:
            progress_queue.put(("progress", line))

        def run_apply() -> None:
            try:
                result = update_manager.apply_update(progress_callback=progress_callback)
                progress_queue.put(("done", result))
            except Exception as exc:
                progress_queue.put(("error", str(exc)))

        async def drain_queue() -> None:
            nonlocal tx_count
            loop = asyncio.get_running_loop()
            while True:
                try:
                    kind, payload = await loop.run_in_executor(None, progress_queue.get)
                    if kind == "progress":
                        await websocket.send_json({"type": "progress", "line": payload})
                        tx_count += 1
                    elif kind == "done":
                        await websocket.send_json({"type": "done", "result": payload})
                        tx_count += 1
                        return
                    elif kind == "error":
                        await websocket.send_json({"type": "error", "message": str(payload)})
                        tx_count += 1
                        return
                except Exception:
                    return

        try:
            apply_task = asyncio.create_task(asyncio.to_thread(run_apply))
            drain_task = asyncio.create_task(drain_queue())
            await asyncio.gather(apply_task, drain_task)
        except WebSocketDisconnect:
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/updates/apply client=%s duration_s=%.1f tx=%d",
                client,
                duration,
                tx_count,
            )
        except Exception as exc:
            logger.error(
                "WS error path=/ws/updates/apply client=%s error=%s",
                client,
                str(exc),
                exc_info=True,
            )
            try:
                await websocket.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass
            raise

    @app.websocket("/ws/capture/{capture_id}")
    async def capture_stream(
        websocket: WebSocket, capture_id: str
    ) -> None:  # pragma: no cover - preserved for legacy clients
        await websocket.close(code=1000)

"""WebSocket endpoints for serial console, capture streaming, and update progress.

Migrated from flask-sock to FastAPI native WebSockets.
"""

from __future__ import annotations

import asyncio
import json
import queue
import shutil
import time
from typing import TYPE_CHECKING

from fastapi import Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from lib.audit import audit_log
from lib.module_logger import get_api_logger
from services.auth_service.manager import verify_token
from services.capture_manager import capture_manager
from services.logging_service import logging_service
from services.monitor_service import MonitorService
from services.network_manager import NetworkManager
from services.serial_manager import serial_manager
from services.system_manager import SystemManager
from services.update_manager import update_manager

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = get_api_logger(__name__)
_system_manager = SystemManager()
_network_manager = NetworkManager()
_monitor_service = MonitorService()

STATUS_INTERVAL_SEC = 2.0

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


def register_websockets(app: FastAPI) -> None:
    """Register WebSocket routes on the FastAPI app."""

    @app.websocket("/ws/status")
    async def status_stream(websocket: WebSocket) -> None:
        client = websocket.client.host if websocket.client else "unknown"
        logger.info("WS connect path=/ws/status client=%s", client)
        start = time.monotonic()
        tx_count = 0
        await websocket.accept()
        try:
            while True:
                try:
                    # Non-blocking receive for ping
                    try:
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                        data = json.loads(msg) if msg else {}
                        if data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                            tx_count += 1
                    except asyncio.TimeoutError:
                        pass

                    # Gather status (sync managers → run in executor)
                    loop = asyncio.get_running_loop()
                    system_status = await loop.run_in_executor(None, _system_manager.get_status)
                    network_status = await loop.run_in_executor(None, _network_manager.get_status)
                    interfaces_data = await loop.run_in_executor(
                        None,
                        lambda: _network_manager.list_interfaces(),
                    )
                    try:
                        monitor_status = await loop.run_in_executor(None, _monitor_service.get_status)
                    except Exception:
                        monitor_status = {}

                    # Merge monitor into system for system_metrics
                    if monitor_status:
                        system_status = dict(system_status)
                        system_status["health"] = monitor_status.get("health")
                        system_status["alerts"] = list(monitor_status.get("alerts", []))
                        system_status["monitor"] = monitor_status
                    else:
                        system_status = dict(system_status)
                        system_status.setdefault("alerts", [])
                    try:
                        log_alerts = await loop.run_in_executor(
                            None,
                            lambda: logging_service.get_recent_log_alerts(limit=30),
                        )
                        system_status["alerts"].extend(log_alerts)
                        system_status["alerts"].sort(
                            key=lambda a: (a.get("timestamp") or ""),
                            reverse=True,
                        )
                        system_status["alerts"] = system_status["alerts"][:50]
                    except Exception:
                        pass

                    await websocket.send_json({"type": "system_metrics", "data": system_status})
                    await websocket.send_json({"type": "network_status", "data": network_status})
                    await websocket.send_json(
                        {
                            "type": "network_interfaces",
                            "data": {"interfaces": interfaces_data.get("interfaces", [])},
                        }
                    )
                    await websocket.send_json({"type": "monitor_status", "data": monitor_status})
                    tx_count += 4
                except WebSocketDisconnect:
                    break
                await asyncio.sleep(STATUS_INTERVAL_SEC)
        except WebSocketDisconnect:
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/status client=%s duration_s=%.1f tx=%d",
                client,
                duration,
                tx_count,
            )
        except Exception as exc:
            logger.error(
                "WS error path=/ws/status client=%s error=%s",
                client,
                str(exc),
                exc_info=True,
            )
            raise

    @app.websocket("/ws/serial/{session_id}")
    async def serial_console(websocket: WebSocket, session_id: str) -> None:
        client = websocket.client.host if websocket.client else "unknown"
        logger.info(
            "WS connect path=/ws/serial client=%s session=%s",
            client,
            session_id,
        )
        start = time.monotonic()
        rx_tx: list[int] = [0, 0]  # [rx_count, tx_count]
        await websocket.accept()
        ser = None
        stop_event = asyncio.Event()

        try:
            session = serial_manager.get_session_record(session_id)
        except KeyError:
            await websocket.send_json({"type": "error", "message": "Session not found"})
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/serial session=%s client=%s " "duration_s=%.1f rx=%d tx=%d",
                session_id,
                client,
                duration,
                rx_tx[0],
                rx_tx[1],
            )
            return

        device_id = session.device_id
        config = session.config or {}
        baud_rate = int(config.get("baud_rate", 9600))

        try:
            import serial as pyserial  # type: ignore
        except ImportError:
            await websocket.send_json({"type": "error", "message": "pyserial not installed"})
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/serial session=%s client=%s " "duration_s=%.1f rx=%d tx=%d",
                session_id,
                client,
                duration,
                rx_tx[0],
                rx_tx[1],
            )
            return

        try:
            ser = pyserial.Serial(
                device_id,
                baudrate=baud_rate,
                timeout=0.0,
            )
            logger.info(
                "Serial opened session=%s device=%s",
                session_id[:8],
                device_id,
            )
        except Exception as exc:
            logger.warning(
                "Serial open failed session=%s device=%s: %s",
                session_id[:8],
                device_id,
                exc,
            )
            await websocket.send_json({"type": "error", "message": str(exc)})
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/serial session=%s client=%s " "duration_s=%.1f rx=%d tx=%d",
                session_id,
                client,
                duration,
                rx_tx[0],
                rx_tx[1],
            )
            return

        def read_available(port) -> bytes:
            """Non-blocking: return up to 256 bytes if available, else b''."""
            n = port.in_waiting
            if n <= 0:
                return b""
            return port.read(min(n, 256))

        async def reader() -> None:
            loop = asyncio.get_running_loop()
            while not stop_event.is_set():
                try:
                    data = await loop.run_in_executor(None, read_available, ser)
                    if not data:
                        await asyncio.sleep(0.02)
                        continue
                    serial_manager.record_rx(session_id, data)
                    text = data.decode(errors="replace")
                    await websocket.send_json({"type": "data", "data": text})
                    rx_tx[1] += 1
                except (WebSocketDisconnect, ConnectionError, OSError):
                    break
                except Exception as exc:
                    logger.warning(
                        "Serial reader error session=%s device=%s: %s",
                        session_id[:8],
                        device_id,
                        exc,
                    )
                    break

        async def writer() -> None:
            while not stop_event.is_set():
                try:
                    msg = await websocket.receive_text()
                    rx_tx[0] += 1
                    data = json.loads(msg) if msg else {}
                    msg_type = data.get("type")
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                        rx_tx[1] += 1
                    elif msg_type == "data":
                        payload = data.get("data", "")
                        if isinstance(payload, str):
                            out = payload.encode("utf-8", errors="replace")
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(None, lambda out=out: ser.write(out))
                            serial_manager.record_tx(session_id, out)
                    elif msg_type == "control":
                        action = data.get("action")
                        if action == "pause_logging":
                            serial_manager.update_session(session_id, {"logging_paused": True})
                        elif action == "resume_logging":
                            serial_manager.update_session(session_id, {"logging_paused": False})
                        elif action == "break":
                            duration = float(data.get("duration", 0.25))
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(
                                None,
                                lambda dur=duration: _send_break(ser, dur),
                            )
                except WebSocketDisconnect:
                    break
                except Exception as exc:
                    logger.debug("Serial writer error: %s", exc)
                    break

        async def status_emitter() -> None:
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
                try:
                    s = serial_manager.get_session(session_id)
                    await websocket.send_json(
                        {
                            "type": "status",
                            "bytes_tx": s.get("bytes_tx", 0),
                            "bytes_rx": s.get("bytes_rx", 0),
                        }
                    )
                    rx_tx[1] += 1
                except (WebSocketDisconnect, KeyError):
                    break

        def _send_break(port, dur: float) -> None:
            port.break_condition = True
            import time

            time.sleep(dur)
            port.break_condition = False

        try:
            reader_task = asyncio.create_task(reader())
            writer_task = asyncio.create_task(writer())
            status_task = asyncio.create_task(status_emitter())
            await asyncio.gather(reader_task, writer_task, status_task)
        except Exception as exc:
            logger.error(
                "WS error path=/ws/serial session=%s error=%s",
                session_id,
                str(exc),
                exc_info=True,
            )
            raise
        finally:
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/serial session=%s client=%s " "duration_s=%.1f rx=%d tx=%d",
                session_id,
                client,
                duration,
                rx_tx[0],
                rx_tx[1],
            )
            stop_event.set()
            try:
                ser.close()
            except Exception:
                pass
            serial_manager.release_session(session_id)

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
    async def capture_stream(websocket: WebSocket, capture_id: str) -> None:
        client = websocket.client.host if websocket.client else "unknown"
        logger.info(
            "WS connect path=/ws/capture client=%s capture=%s",
            client,
            capture_id,
        )
        start = time.monotonic()
        tx_count = 0
        await websocket.accept()
        try:
            job = capture_manager.get_job(capture_id)
            if not job:
                await websocket.send_json({"type": "error", "message": "Capture not found"})
                duration = time.monotonic() - start
                logger.info(
                    "WS disconnect path=/ws/capture capture=%s client=%s " "duration_s=%.1f tx=%d",
                    capture_id,
                    client,
                    duration,
                    tx_count,
                )
                return
            if not shutil.which("tshark"):
                await websocket.send_json({"type": "error", "message": "tshark not installed"})
                duration = time.monotonic() - start
                logger.info(
                    "WS disconnect path=/ws/capture capture=%s client=%s " "duration_s=%.1f tx=%d",
                    capture_id,
                    client,
                    duration,
                    tx_count,
                )
                return

            is_active = job.stopped_at is None
            if is_active:
                cmd = ["tshark", "-i", job.interface, "-l"]
                if job.filter:
                    cmd.extend(["-f", job.filter])
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                if not job.file_path or not job.file_path.exists():
                    await websocket.send_json({"type": "error", "message": "Capture not found"})
                    duration = time.monotonic() - start
                    logger.info(
                        "WS disconnect path=/ws/capture capture=%s client=%s " "duration_s=%.1f tx=%d",
                        capture_id,
                        client,
                        duration,
                        tx_count,
                    )
                    return
                proc = await asyncio.create_subprocess_exec(
                    "tshark",
                    "-r",
                    str(job.file_path),
                    "-l",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            try:
                if is_active:
                    await websocket.send_json({"type": "live_started"})
                if proc.stdout:
                    async for line in proc.stdout:
                        line_str = line.decode(errors="replace").strip()
                        if line_str:
                            await websocket.send_json({"type": "packet", "summary": line_str})
                            tx_count += 1
            except (WebSocketDisconnect, ConnectionError):
                pass
            finally:
                try:
                    proc.terminate()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                if proc.returncode and proc.returncode != 0 and proc.stderr:
                    try:
                        stderr = (await proc.stderr.read()).decode(errors="replace").strip()
                        if stderr:
                            msg = _capture_error_message(stderr, is_active)
                            await websocket.send_json({"type": "error", "message": msg})
                    except Exception:
                        pass
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/capture capture=%s client=%s " "duration_s=%.1f tx=%d",
                capture_id,
                client,
                duration,
                tx_count,
            )
        except WebSocketDisconnect:
            duration = time.monotonic() - start
            logger.info(
                "WS disconnect path=/ws/capture capture=%s client=%s " "duration_s=%.1f tx=%d",
                capture_id,
                client,
                duration,
                tx_count,
            )
        except Exception as exc:
            logger.error(
                "WS error path=/ws/capture capture=%s error=%s",
                capture_id,
                str(exc),
                exc_info=True,
            )
            try:
                await websocket.send_json({"type": "error", "message": str(exc)})
            except Exception:
                pass
            raise

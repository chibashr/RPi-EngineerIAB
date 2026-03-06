"""WebSocket endpoints for serial console, capture streaming, and update progress."""

from __future__ import annotations

import json
import queue
import threading
import time
from typing import Optional

from flask_sock import Sock
from simple_websocket import ConnectionClosed

from services.capture_manager import capture_manager
from services.capture_manager.manager import split_bpf_filter
from services.serial_manager import serial_manager
from services.system_manager import SystemManager
from services.network_manager import NetworkManager
from services.monitor_service import MonitorService
from services.logging_service import logging_service
from lib.module_logger import get_service_logger
from services.update_manager import update_manager

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    serial = None


def register_websockets(sock: Sock) -> None:
    system_manager = SystemManager()
    network_manager = NetworkManager()
    monitor_service = MonitorService()
    logger = get_service_logger(__name__)

    def _merged_monitor_payload() -> dict:
        """Build monitor payload with health alerts + recent log alerts (same as GET /system/status)."""
        try:
            monitor = monitor_service.get_status()
            alerts = list(monitor.get("alerts", []))
        except Exception:
            monitor = {}
            alerts = []
        try:
            log_alerts = logging_service.get_recent_log_alerts(limit=30)
            alerts.extend(log_alerts)
            alerts.sort(key=lambda a: (a.get("timestamp") or ""), reverse=True)
            alerts = alerts[:50]
        except Exception:
            pass
        if monitor:
            monitor = dict(monitor)
            monitor["alerts"] = alerts
        return monitor or {"alerts": alerts, "health": None}

    @sock.route("/ws/status")
    def status_stream(ws) -> None:  # type: ignore[no-untyped-def]
        stop_event = threading.Event()
        send_lock = threading.Lock()

        def safe_send(payload: dict) -> bool:
            try:
                with send_lock:
                    ws.send(json.dumps(payload))
                return True
            except Exception:
                stop_event.set()
                return False

        def receiver() -> None:
            while not stop_event.is_set():
                try:
                    message = ws.receive()
                except Exception:
                    break
                if message is None:
                    break
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "ping":
                    safe_send({"type": "pong"})
            stop_event.set()

        thread = threading.Thread(target=receiver, daemon=True)
        thread.start()

        while not stop_event.is_set():
            system_status = system_manager.get_status()
            if not safe_send({"type": "system_metrics", "data": system_status}):
                break
            network_status = network_manager.get_status()
            if not safe_send({"type": "network_status", "data": network_status}):
                break
            network_interfaces = network_manager.list_interfaces()
            if not safe_send(
                {"type": "network_interfaces", "data": network_interfaces}
            ):
                break
            monitor_payload = _merged_monitor_payload()
            if not safe_send({"type": "monitor_status", "data": monitor_payload}):
                break
            time.sleep(2)

    @sock.route("/ws/serial/<session_id>")
    def serial_console(ws, session_id: str) -> None:  # type: ignore[no-untyped-def]
        logger.info("serial_console: WebSocket connect request session_id=%s", session_id[:8] if session_id else "?")
        try:
            session = serial_manager.get_session_record(session_id)
        except KeyError as exc:
            logger.warning("serial_console: session %s not found: %s", session_id[:8] if session_id else "?", exc)
            ws.send(json.dumps({"type": "error", "message": "Session not found"}))
            return
        if not serial:
            logger.error("serial_console: pyserial not installed")
            ws.send(json.dumps({"type": "error", "message": "pyserial not installed"}))
            try:
                serial_manager.release_session(session_id)
            except Exception:
                pass
            return
        config = session.config or {}
        baud_rate = int(config.get("baud_rate", 9600))
        data_bits = int(config.get("data_bits", 8))
        parity = str(config.get("parity", "none")).upper()
        stop_bits = int(config.get("stop_bits", 1))
        timeout = 0.1
        logger.info("serial_console: opening %s baud=%s data_bits=%s parity=%s stop_bits=%s", session.device_id, baud_rate, data_bits, parity, stop_bits)
        parity_map = {
            "NONE": serial.PARITY_NONE,
            "N": serial.PARITY_NONE,
            "EVEN": serial.PARITY_EVEN,
            "E": serial.PARITY_EVEN,
            "ODD": serial.PARITY_ODD,
            "O": serial.PARITY_ODD,
        }
        bytesize_map = {
            5: serial.FIVEBITS,
            6: serial.SIXBITS,
            7: serial.SEVENBITS,
            8: serial.EIGHTBITS,
        }
        stopbits_map = {1: serial.STOPBITS_ONE, 2: serial.STOPBITS_TWO}
        try:
            ser = serial.Serial(
                session.device_id,
                baudrate=baud_rate,
                bytesize=bytesize_map.get(data_bits, serial.EIGHTBITS),
                parity=parity_map.get(parity, serial.PARITY_NONE),
                stopbits=stopbits_map.get(stop_bits, serial.STOPBITS_ONE),
                timeout=timeout,
            )
        except Exception as exc:
            logger.exception("serial_console: failed to open %s: %s", session.device_id, exc)
            ws.send(json.dumps({"type": "error", "message": str(exc)}))
            try:
                serial_manager.release_session(session_id)
            except Exception:
                pass
            return

        logger.info("serial_console: port opened, starting reader for session %s", session_id[:8])
        session.websocket_connected = True
        stop_event = threading.Event()
        send_queue = queue.SimpleQueue()
        read_poll_interval = 0.05  # 50ms between polls when idle (RasPi-NetPal-style)

        def reader() -> None:
            last_status = time.time()
            while not stop_event.is_set():
                try:
                    n = ser.in_waiting
                    if n > 0:
                        data = ser.read(n)
                    else:
                        time.sleep(read_poll_interval)
                        continue
                except Exception as read_exc:
                    logger.warning("serial_console: reader error on %s: %s", session.device_id, read_exc)
                    break
                if data:
                    serial_manager.record_rx(session_id, data)
                    payload = {"type": "data", "data": data.decode(errors="ignore")}
                    send_queue.put(json.dumps(payload))
                if time.time() - last_status > 1:
                    last_status = time.time()
                    status = {
                        "type": "status",
                        "bytes_tx": session.bytes_tx,
                        "bytes_rx": session.bytes_rx,
                    }
                    send_queue.put(json.dumps(status))

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        def drain_send_queue() -> None:
            try:
                while True:
                    ws.send(send_queue.get_nowait())
            except queue.Empty:
                pass
            except Exception:
                pass

        try:
            while True:
                try:
                    message = ws.receive(timeout=0.05)
                except ConnectionClosed:
                    logger.info("serial_console: client disconnected session=%s", session_id[:8])
                    break
                drain_send_queue()
                if message is None:
                    continue
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError as je:
                    logger.warning("serial_console: invalid JSON from client: %s", je)
                    ws.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
                    continue
                msg_type = payload.get("type")
                if msg_type == "ping":
                    ws.send(json.dumps({"type": "pong"}))
                elif msg_type == "data":
                    data = payload.get("data", "")
                    if data:
                        raw = data.encode("utf-8", errors="replace")
                        ser.write(raw)
                        ser.flush()
                        serial_manager.record_tx(session_id, raw)
                        logger.debug("serial_console: sent %d byte(s) to %s", len(raw), session.device_id)
                elif msg_type == "control":
                    action = payload.get("action")
                    if action == "pause_logging":
                        serial_manager.update_session(session_id, {"logging_paused": True})
                    elif action == "resume_logging":
                        serial_manager.update_session(session_id, {"logging_paused": False})
                    elif action == "break":
                        try:
                            ser.send_break(duration=payload.get("duration", 0.25))
                            logger.debug("serial_console: sent break to %s", session.device_id)
                        except Exception as brk_exc:
                            logger.warning("serial_console: break failed %s: %s", session.device_id, brk_exc)
        except Exception as exc:
            logger.info("serial_console: main loop exited session=%s: %s", session_id[:8], exc)
        finally:
            stop_event.set()
            thread.join(timeout=2.0)
            session.websocket_connected = False
            try:
                ser.close()
                logger.info("serial_console: closed session %s device %s", session_id[:8], session.device_id)
            except Exception as close_exc:
                logger.warning("serial_console: error closing port %s: %s", session.device_id, close_exc)
            try:
                serial_manager.release_session(session_id)
            except Exception as rel_exc:
                logger.warning("serial_console: release_session failed: %s", rel_exc)

    @sock.route("/ws/updates/apply")
    def updates_apply_stream(ws) -> None:  # type: ignore[no-untyped-def]
        """Stream update apply progress (same steps as CLI) over WebSocket."""
        send_lock = threading.Lock()

        def send_message(msg_type: str, payload: dict) -> None:
            try:
                with send_lock:
                    ws.send(json.dumps({"type": msg_type, **payload}))
            except Exception as e:
                logger.debug("Update stream send failed: %s", e)

        def progress_callback(line: str) -> None:
            send_message("progress", {"line": line})

        def run_apply() -> None:
            try:
                result = update_manager.apply_update(progress_callback=progress_callback)
                send_message("done", {"result": result})
                time.sleep(0.25)  # allow client to receive "done" before handler return closes the socket
            except Exception as exc:
                logger.exception("Update apply failed in stream: %s", exc)
                send_message("error", {"message": str(exc)})

        thread = threading.Thread(target=run_apply, daemon=True)
        thread.start()
        thread.join(timeout=180)
        if thread.is_alive():
            send_message("error", {"message": "Update timed out after 3 minutes."})

    @sock.route("/ws/capture/<capture_id>")
    def capture_stream(ws, capture_id: str) -> None:  # type: ignore[no-untyped-def]
        job = capture_manager.get_job(capture_id)
        if not job:
            ws.send(json.dumps({"type": "error", "message": "Capture not found"}))
            return
        interface = job.interface
        filter_expr = job.filter or ""
        if not _which("tcpdump"):
            ws.send(json.dumps({"type": "error", "message": "tcpdump not installed"}))
            return
        cmd = ["tcpdump", "-l", "-n", "-i", interface]
        if filter_expr:
            try:
                cmd += split_bpf_filter(filter_expr)
            except ValueError as exc:
                ws.send(json.dumps({"type": "error", "message": str(exc)}))
                return
        proc = _popen_stream(cmd)
        if not proc:
            ws.send(json.dumps({"type": "error", "message": "Unable to start tcpdump"}))
            return
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                payload = {"type": "packet", "summary": line.strip()}
                try:
                    ws.send(json.dumps(payload))
                except Exception:
                    break
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
                proc.wait()


def _popen_stream(cmd: list[str]) -> Optional["subprocess.Popen[str]"]:
    import subprocess

    try:
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
    except OSError:
        return None


def _which(binary: str) -> Optional[str]:
    import shutil

    return shutil.which(binary)

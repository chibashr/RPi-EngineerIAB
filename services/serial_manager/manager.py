"""Serial Manager implementation for device and session management."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import calendar
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import pyudev  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pyudev = None

try:
    import serial  # type: ignore
    import serial.tools.list_ports  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    serial = None

from lib.module_logger import get_service_logger

logger = get_service_logger(__name__)
LOG_DIR = Path("/opt/rpi-engineer/data/serial_logs")
EXPORT_DIR = LOG_DIR / "exports"
CONFIG_PATH = LOG_DIR.parent / "serial_devices.json"
MAX_SESSIONS = 8


@dataclass
class SerialSession:
    session_id: str
    device_id: str
    config: Dict[str, object]
    created_at: str
    status: str = "active"
    logging_paused: bool = False
    bytes_tx: int = 0
    bytes_rx: int = 0
    log_path: Optional[Path] = None
    websocket_connected: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


class SerialManager:
    """Serial device detection and session lifecycle."""

    def __init__(self) -> None:
        self._device_configs: Dict[str, Dict[str, object]] = {}
        self._sessions: Dict[str, SerialSession] = {}
        self._load_device_configs()
        logger.info("Serial manager started")

    def list_devices(self) -> Dict[str, List[Dict[str, object]]]:
        raw = self._scan_devices()
        logger.info("list_devices: scanned %d device(s)", len(raw))
        devices = []
        for device in raw:
            config = self._device_configs.get(device["id"], {})
            status = "in_use" if self._device_in_use(device["id"]) else "available"
            devices.append(
                {
                    "id": device["id"],
                    "path": device["path"],
                    "friendly_name": config.get("friendly_name", device["friendly_name"]),
                    "chipset": device["chipset"],
                    "status": status,
                    "baud_rate": config.get("baud_rate", 9600),
                    "config": config,
                }
            )
        return {"devices": devices}

    def get_device(self, device_id: str) -> Dict[str, object]:
        device = self._device_by_id(device_id)
        if not device:
            raise KeyError("Device not found")
        config = self._device_configs.get(device_id, {})
        return {
            "id": device_id,
            "path": device_id,
            "friendly_name": config.get("friendly_name", device["friendly_name"]),
            "chipset": device["chipset"],
            "status": "in_use" if self._device_in_use(device_id) else "available",
            "baud_rate": config.get("baud_rate", 9600),
            "config": config,
        }

    def update_device(self, device_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        if not self._device_by_id(device_id):
            raise KeyError("Device not found")
        allowed = {
            "friendly_name",
            "baud_rate",
            "data_bits",
            "parity",
            "stop_bits",
            "flow_control",
        }
        config = dict(self._device_configs.get(device_id, {}))
        for key, value in payload.items():
            if key in allowed and value is not None:
                if key in ("baud_rate", "data_bits", "stop_bits"):
                    try:
                        config[key] = int(value)
                    except (TypeError, ValueError):
                        config[key] = value
                else:
                    config[key] = value
        self._device_configs[device_id] = config
        self._save_device_configs()
        return {"id": device_id, "config": config}

    def test_device(self, device_id: str) -> Dict[str, object]:
        if not serial:
            raise RuntimeError("pyserial not installed")
        device = self._device_by_id(device_id)
        if not device:
            raise KeyError("Device not found")
        config = self._device_configs.get(device_id, {})
        baud_rate = int(config.get("baud_rate", 9600))
        try:
            with serial.Serial(device_id, baudrate=baud_rate, timeout=1):
                pass
        except Exception as exc:
            logger.warning("Device test failed %s: %s", device_id, exc)
            raise RuntimeError(str(exc)) from exc
        return {"id": device_id, "status": "ok"}

    def create_session(self, payload: Dict[str, object]) -> Dict[str, object]:
        device_id = payload.get("device_id")
        config = payload.get("config", {}) or {}
        logger.info("create_session: request device_id=%r config_keys=%s", device_id, list(config.keys()) if config else [])
        if not device_id:
            logger.warning("create_session: device_id missing")
            raise ValueError("device_id is required")
        if not serial:
            logger.error("create_session: pyserial not installed")
            raise RuntimeError("pyserial not installed")
        if len(self._sessions) >= MAX_SESSIONS:
            logger.warning("create_session: max sessions (%d) reached", MAX_SESSIONS)
            raise RuntimeError("Maximum sessions reached")
        if self._device_in_use(device_id):
            logger.warning("create_session: device %s already in use", device_id)
            raise RuntimeError("Device already in use")
        if not self._device_by_id(device_id):
            logger.warning("create_session: device %s not found in scan", device_id)
            raise KeyError("Device not found")
        session_id = str(uuid.uuid4())
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{session_id}.log"
        log_path.write_text(self._log_header(device_id))
        merged_config = {**self._device_configs.get(device_id, {}), **config}
        session = SerialSession(
            session_id=session_id,
            device_id=device_id,
            config=merged_config,
            created_at=_timestamp(),
            log_path=log_path,
        )
        self._sessions[session_id] = session
        logger.info("Session created: %s for device %s (baud=%s)", session_id[:8], device_id, merged_config.get("baud_rate", 9600))
        return {
            "session_id": session_id,
            "device_id": device_id,
            "websocket_url": f"{_ws_base()}/ws/serial/{session_id}",
        }

    def list_sessions(self) -> Dict[str, List[Dict[str, object]]]:
        return {
            "sessions": [
                {
                    "session_id": session.session_id,
                    "device_id": session.device_id,
                    "status": session.status,
                    "logging_paused": session.logging_paused,
                    "created_at": session.created_at,
                }
                for session in self._sessions.values()
            ]
        }

    def get_session(self, session_id: str) -> Dict[str, object]:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError("Session not found")
        return {
            "session_id": session.session_id,
            "device_id": session.device_id,
            "status": session.status,
            "logging_paused": session.logging_paused,
            "bytes_tx": session.bytes_tx,
            "bytes_rx": session.bytes_rx,
        }

    def update_session(self, session_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        session = self._sessions.get(session_id)
        if not session:
            raise KeyError("Session not found")
        if "logging_paused" in payload:
            session.logging_paused = bool(payload["logging_paused"])
        return {"session_id": session_id, "logging_paused": session.logging_paused}

    def delete_session(self, session_id: str) -> Dict[str, object]:
        session = self._sessions.pop(session_id, None)
        if not session:
            raise KeyError("Session not found")
        session.status = "closed"
        logger.info("Session closed: %s (device %s)", session_id[:8], session.device_id)
        return {"session_id": session_id, "status": "closed"}

    def list_logs(self, device: Optional[str], since: Optional[str], limit: int) -> Dict[str, object]:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logs = []
        for path in sorted(LOG_DIR.glob("*.log")):
            content = path.read_text(errors="ignore")
            if device and device not in content:
                continue
            modified = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))
            if since and modified < since:
                continue
            device_id, created = self._parse_log_header(content)
            duration_sec = None
            if created:
                try:
                    created_ts = calendar.timegm(
                        time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")
                    )
                    modified_ts = path.stat().st_mtime
                    duration_sec = max(0, int(modified_ts - created_ts))
                except (ValueError, OSError):
                    pass
            display_name = self._get_log_display_name(path.stem)
            logs.append(
                {
                    "id": path.stem,
                    "name": display_name or path.stem,
                    "device": device_id or device or "",
                    "created": created or modified,
                    "modified": modified,
                    "duration_seconds": duration_sec,
                    "size_bytes": path.stat().st_size,
                }
            )
        if limit:
            logs = logs[:limit]
        return {"logs": logs}

    def _parse_log_header(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse Device and Created from log header. Returns (device_id, created_iso)."""
        device_id = None
        created = None
        for line in content.split("\n")[:5]:
            if line.startswith("Device:"):
                device_id = line[7:].strip()
            elif line.startswith("Created:"):
                created = line[8:].strip()
        return (device_id, created)

    def _get_log_display_name(self, log_id: str) -> Optional[str]:
        """Read display name from metadata file if present."""
        meta_path = LOG_DIR / f"{log_id}.meta.json"
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            return data.get("display_name")
        except (json.JSONDecodeError, OSError):
            return None

    def rename_log(self, log_id: str, display_name: str) -> Dict[str, object]:
        path = LOG_DIR / f"{log_id}.log"
        if not path.exists():
            raise KeyError("Log not found")
        meta_path = LOG_DIR / f"{log_id}.meta.json"
        meta_path.write_text(json.dumps({"display_name": display_name.strip()}), encoding="utf-8")
        return {"id": log_id, "name": display_name.strip()}

    def get_log_content(self, log_id: str) -> Dict[str, object]:
        path = LOG_DIR / f"{log_id}.log"
        if not path.exists():
            raise KeyError("Log not found")
        return {"id": log_id, "content": path.read_text(errors="ignore")}

    def delete_log(self, log_id: str) -> Dict[str, object]:
        path = LOG_DIR / f"{log_id}.log"
        if not path.exists():
            raise KeyError("Log not found")
        path.unlink()
        return {"id": log_id, "deleted": True}

    def export_logs(self, log_ids: List[str]) -> Dict[str, object]:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = EXPORT_DIR / f"serial_logs_{int(time.time())}.zip"
        import zipfile

        with zipfile.ZipFile(archive_path, "w") as archive:
            for log_id in log_ids:
                path = LOG_DIR / f"{log_id}.log"
                if path.exists():
                    archive.write(path, arcname=path.name)
        return {"archive": str(archive_path)}

    def get_session_record(self, session_id: str) -> SerialSession:
        session = self._sessions.get(session_id)
        if not session:
            logger.warning("get_session_record: session %s not found (active: %s)", session_id[:8] if session_id else "?", list(self._sessions.keys())[:3])
            raise KeyError("Session not found")
        return session

    def record_tx(self, session_id: str, data: bytes) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session.bytes_tx += len(data)
        self._append_log(session, "TX", data)

    def record_rx(self, session_id: str, data: bytes) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session.bytes_rx += len(data)
        self._append_log(session, "RX", data)

    def _append_log(self, session: SerialSession, direction: str, data: bytes) -> None:
        if session.logging_paused or not session.log_path:
            return
        try:
            text = data.decode(errors="ignore")
        except Exception:
            text = ""
        line = f"{_timestamp()} {direction} {text}\n"
        with session.log_path.open("a") as handle:
            handle.write(line)

    def _log_header(self, device_id: str) -> str:
        return f"Device: {device_id}\nCreated: {_timestamp()}\n---\n"

    def _load_device_configs(self) -> None:
        """Load device configs from disk. Survives service restarts."""
        if not CONFIG_PATH.exists():
            return
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            configs = data.get("devices", {})
            if isinstance(configs, dict):
                self._device_configs.update(configs)
                logger.info("Loaded %d serial device config(s) from %s", len(configs), CONFIG_PATH)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load serial device configs from %s: %s", CONFIG_PATH, exc)

    def _save_device_configs(self) -> None:
        """Persist device configs to disk."""
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {"devices": self._device_configs, "version": 1}
            CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save serial device configs to %s: %s", CONFIG_PATH, exc)

    def _device_in_use(self, device_id: str) -> bool:
        return any(session.device_id == device_id for session in self._sessions.values())

    def _device_by_id(self, device_id: str) -> Optional[Dict[str, object]]:
        for device in self._scan_devices():
            if device["id"] == device_id:
                return device
        return None

    def _scan_devices(self) -> List[Dict[str, object]]:
        devices = []
        if serial:
            ports = list(serial.tools.list_ports.comports())
            logger.info("_scan_devices: pyserial found %d port(s)", len(ports))
            for port in ports:
                dev = self._port_to_device(port.device, port.description, port.vid)
                devices.append(dev)
        if pyudev and not devices:
            logger.info("_scan_devices: pyserial empty, trying pyudev")
            context = pyudev.Context()
            for device in context.list_devices(subsystem="tty"):
                node = device.device_node
                if not node:
                    continue
                devices.append(
                    self._port_to_device(node, device.get("ID_MODEL", "Serial Device"), device.get("ID_VENDOR_ID"))
                )
        dev_root = Path("/dev")
        if not devices and dev_root.exists():
            logger.info("_scan_devices: fallback to /dev/ttyUSB* and ttyACM*")
            for path in dev_root.glob("ttyUSB*"):
                devices.append(self._port_to_device(str(path), "Serial Device", None))
            for path in dev_root.glob("ttyACM*"):
                devices.append(self._port_to_device(str(path), "Serial Device", None))
        return devices

    def _port_to_device(self, path: str, description: str, vid: Optional[int]) -> Dict[str, object]:
        chipset = _chipset_from_vid(vid)
        friendly = (description or "").strip()
        if not friendly or friendly.lower() == "n/a":
            friendly = path or "Serial Device"
        return {
            "id": path,
            "path": path,
            "friendly_name": friendly,
            "chipset": chipset,
        }


def _chipset_from_vid(vid: Optional[object]) -> str:
    if vid is None:
        return "Unknown"
    try:
        vid_int = int(str(vid), 16) if isinstance(vid, str) and vid.startswith("0x") else int(vid)
    except (TypeError, ValueError):
        return "Unknown"
    lookup = {0x0403: "FTDI", 0x067B: "Prolific", 0x1A86: "CH340"}
    return lookup.get(vid_int, "Unknown")


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ws_base() -> str:
    return os.getenv("RPI_ENGINEER_WS_BASE", "ws://192.168.50.1")

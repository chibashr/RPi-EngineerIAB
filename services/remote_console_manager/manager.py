"""Remote console (SSH/Telnet) manager: targets and sessions."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.module_logger import get_service_logger

logger = get_service_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_SESSIONS = 5
TARGETS_FILENAME = "remote_console_targets.json"


def _data_dir() -> Path:
    base = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/opt/rpi-engineer/data"))
    if not base.exists():
        base = _REPO_ROOT / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _targets_path() -> Path:
    return _data_dir() / TARGETS_FILENAME


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ws_base() -> str:
    return os.getenv("RPI_ENGINEER_WS_BASE", "ws://192.168.50.1")


@dataclass
class RemoteConsoleTarget:
    """Saved connection target (SSH or Telnet)."""

    id: str
    type: str  # "ssh" | "telnet"
    host: str
    port: int
    friendly_name: str
    username: str | None = None
    password: str | None = None  # persisted; never returned by API (write-only)
    auth_type: str | None = None  # "password" | "key"
    private_key_path: str | None = None
    created_at: str = field(default_factory=_timestamp)


@dataclass
class RemoteConsoleSession:
    """Active session (connection params for WS handler; no I/O in manager)."""

    session_id: str
    target_id: str | None
    type: str  # "ssh" | "telnet"
    host: str
    port: int
    username: str | None
    password: str | None = None  # in-memory only, for this session
    private_key_path: str | None = None
    created_at: str = field(default_factory=_timestamp)
    status: str = "active"
    bytes_tx: int = 0
    bytes_rx: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class RemoteConsoleManager:
    """Target CRUD and session lifecycle for SSH/Telnet remote console."""

    def __init__(self) -> None:
        self._targets: dict[str, RemoteConsoleTarget] = {}
        self._sessions: dict[str, RemoteConsoleSession] = {}
        self._load_targets()
        logger.info("Remote console manager started")

    def _load_targets(self) -> None:
        path = _targets_path()
        if not path.exists():
            return
        try:
            data = path.read_text(encoding="utf-8")
            obj = json.loads(data)
            targets_list = obj.get("targets", [])
            if not isinstance(targets_list, list):
                return
            for t in targets_list:
                if not isinstance(t, dict) or not t.get("id"):
                    continue
                tid = str(t["id"])
                self._targets[tid] = RemoteConsoleTarget(
                    id=tid,
                    type=str(t.get("type", "ssh")),
                    host=str(t.get("host", "")),
                    port=int(t.get("port", 22 if t.get("type") == "ssh" else 23)),
                    friendly_name=str(t.get("friendly_name", "") or t.get("host", "")),
                    username=t.get("username"),
                    password=t.get("password"),
                    auth_type=t.get("auth_type"),
                    private_key_path=t.get("private_key_path"),
                    created_at=str(t.get("created_at", _timestamp())),
                )
            logger.info("Loaded %d remote console target(s)", len(self._targets))
        except Exception as exc:
            logger.warning("Could not load targets from %s: %s", path, exc)

    def _save_targets(self) -> None:
        path = _targets_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            targets_list = []
            for t in self._targets.values():
                row = {
                    "id": t.id,
                    "type": t.type,
                    "host": t.host,
                    "port": t.port,
                    "friendly_name": t.friendly_name,
                    "username": t.username,
                    "auth_type": t.auth_type,
                    "private_key_path": t.private_key_path,
                    "created_at": t.created_at,
                }
                if t.password is not None:
                    row["password"] = t.password
                targets_list.append(row)
            path.write_text(
                json.dumps({"targets": targets_list, "version": 1}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not save targets to %s: %s", path, exc)

    def list_targets(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "targets": [
                {
                    "id": t.id,
                    "type": t.type,
                    "host": t.host,
                    "port": t.port,
                    "friendly_name": t.friendly_name,
                    "username": t.username,
                    "auth_type": t.auth_type,
                    "created_at": t.created_at,
                }
                for t in self._targets.values()
            ]
        }

    def get_target(self, target_id: str) -> dict[str, Any]:
        t = self._targets.get(target_id)
        if not t:
            raise KeyError("Target not found")
        return {
            "id": t.id,
            "type": t.type,
            "host": t.host,
            "port": t.port,
            "friendly_name": t.friendly_name,
            "username": t.username,
            "auth_type": t.auth_type,
            "private_key_path": t.private_key_path,
            "created_at": t.created_at,
        }

    def create_target(self, payload: dict[str, Any]) -> dict[str, Any]:
        host = (payload.get("host") or "").strip()
        if not host:
            raise ValueError("host is required")
        port = int(payload.get("port", 22))
        if port < 1 or port > 65535:
            raise ValueError("port must be 1-65535")
        conn_type = (payload.get("type") or "ssh").strip().lower()
        if conn_type not in ("ssh", "telnet"):
            raise ValueError("type must be ssh or telnet")
        friendly_name = (payload.get("friendly_name") or host).strip()
        target_id = str(uuid.uuid4())
        username = payload.get("username")
        if username is not None:
            username = str(username).strip() or None
        password = payload.get("password")
        if password is not None:
            password = str(password)
        auth_type = payload.get("auth_type")
        if auth_type is not None:
            auth_type = str(auth_type).strip().lower() or None
        private_key_path = payload.get("private_key_path")
        if private_key_path is not None:
            private_key_path = str(private_key_path).strip() or None
        t = RemoteConsoleTarget(
            id=target_id,
            type=conn_type,
            host=host,
            port=port,
            friendly_name=friendly_name,
            username=username,
            password=password,
            auth_type=auth_type,
            private_key_path=private_key_path,
        )
        self._targets[target_id] = t
        self._save_targets()
        logger.info("Remote console target created: %s %s:%s", target_id[:8], host, port)
        return self.get_target(target_id)

    def update_target(self, target_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        t = self._targets.get(target_id)
        if not t:
            raise KeyError("Target not found")
        if "host" in payload and payload["host"] is not None:
            t.host = str(payload["host"]).strip()
        if "port" in payload and payload["port"] is not None:
            t.port = int(payload["port"])
        if "type" in payload and payload["type"] is not None:
            ct = str(payload["type"]).strip().lower()
            if ct in ("ssh", "telnet"):
                t.type = ct
        if "friendly_name" in payload:
            t.friendly_name = (payload["friendly_name"] or t.host).strip()
        if "username" in payload:
            t.username = str(payload["username"]).strip() or None
        if "auth_type" in payload:
            t.auth_type = str(payload["auth_type"]).strip().lower() or None
        if "private_key_path" in payload:
            t.private_key_path = str(payload["private_key_path"]).strip() or None
        if "password" in payload:
            t.password = str(payload["password"]) if payload["password"] is not None else None
        self._save_targets()
        return self.get_target(target_id)

    def delete_target(self, target_id: str) -> dict[str, Any]:
        if target_id not in self._targets:
            raise KeyError("Target not found")
        del self._targets[target_id]
        self._save_targets()
        logger.info("Remote console target deleted: %s", target_id[:8])
        return {"id": target_id, "deleted": True}

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        if len(self._sessions) >= MAX_SESSIONS:
            raise RuntimeError("Maximum sessions reached")
        target_id = payload.get("target_id")
        password = payload.get("password")
        if password is not None:
            password = str(password)
        if target_id:
            t = self._targets.get(target_id)
            if not t:
                raise KeyError("Target not found")
            session_password = password if password is not None else getattr(t, "password", None)
            session = RemoteConsoleSession(
                session_id=str(uuid.uuid4()),
                target_id=target_id,
                type=t.type,
                host=t.host,
                port=t.port,
                username=t.username,
                password=session_password,
                private_key_path=t.private_key_path,
            )
        else:
            host = (payload.get("host") or "").strip()
            if not host:
                raise ValueError("host is required (or provide target_id)")
            port = int(payload.get("port", 22))
            if port < 1 or port > 65535:
                raise ValueError("port must be 1-65535")
            conn_type = (payload.get("type") or "ssh").strip().lower()
            if conn_type not in ("ssh", "telnet"):
                raise ValueError("type must be ssh or telnet")
            username = payload.get("username")
            if username is not None:
                username = str(username).strip() or None
            session = RemoteConsoleSession(
                session_id=str(uuid.uuid4()),
                target_id=None,
                type=conn_type,
                host=host,
                port=port,
                username=username,
                password=password,
                private_key_path=payload.get("private_key_path") or None,
            )
        self._sessions[session.session_id] = session
        logger.info(
            "Remote console session created: %s %s:%s (%s)",
            session.session_id[:8],
            session.host,
            session.port,
            session.type,
        )
        return {
            "session_id": session.session_id,
            "target_id": session.target_id,
            "type": session.type,
            "host": session.host,
            "port": session.port,
            "websocket_url": f"{_ws_base()}/ws/remote-console/{session.session_id}",
        }

    def list_sessions(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "target_id": s.target_id,
                    "type": s.type,
                    "host": s.host,
                    "port": s.port,
                    "status": s.status,
                    "created_at": s.created_at,
                }
                for s in self._sessions.values()
            ]
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        s = self._sessions.get(session_id)
        if not s:
            raise KeyError("Session not found")
        return {
            "session_id": s.session_id,
            "target_id": s.target_id,
            "type": s.type,
            "host": s.host,
            "port": s.port,
            "status": s.status,
            "bytes_tx": s.bytes_tx,
            "bytes_rx": s.bytes_rx,
            "created_at": s.created_at,
        }

    def delete_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.pop(session_id, None)
        if not session:
            raise KeyError("Session not found")
        session.status = "closed"
        logger.info("Remote console session deleted: %s", session_id[:8])
        return {"session_id": session_id, "status": "closed"}

    def release_session(self, session_id: str) -> None:
        """Remove session when WebSocket closes. Does not raise."""
        session = self._sessions.pop(session_id, None)
        if session:
            session.status = "closed"
            logger.info("Remote console session ended: %s", session_id[:8])

    def get_session_record(self, session_id: str) -> RemoteConsoleSession:
        s = self._sessions.get(session_id)
        if not s:
            raise KeyError("Session not found")
        return s

    def record_tx(self, session_id: str, size: int) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.bytes_tx += size

    def record_rx(self, session_id: str, size: int) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.bytes_rx += size

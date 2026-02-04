"""Syslog receiver implementation (UDP + TCP)."""

from __future__ import annotations

import json
import os
import socket
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, List, Optional


DEFAULT_CONFIG = {
    "enabled": True,
    "bind_address": "0.0.0.0",
    "port_udp": 1514,
    "port_tcp": 1514,
    "persist": True,
    "max_stored": 10000,
    "max_live": 1000,
}


MONTHS = {
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_path = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    base = env_path if env_path.exists() else _repo_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    module_dir = base / "syslog_receiver"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _config_path() -> Path:
    return _data_dir() / "config.json"


def _db_path() -> Path:
    return _data_dir() / "messages.db"


def get_storage_info() -> Dict[str, object]:
    """Return storage directory path and list of files (name, size, mtime) for the explorer."""
    data = _data_dir()
    files: List[Dict[str, object]] = []
    for p in sorted(data.iterdir()):
        if p.is_file():
            stat = p.stat()
            files.append({
                "name": p.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"path": str(data), "files": files}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ReceiverState:
    recent: Deque[Dict[str, object]] = field(default_factory=deque)
    lock: threading.Lock = field(default_factory=threading.Lock)
    received_count: int = 0
    stored_count: int = 0
    last_received: Optional[str] = None
    last_error: Optional[str] = None
    running: bool = False
    udp_running: bool = False
    tcp_running: bool = False
    bind_address: Optional[str] = None
    port_udp: Optional[int] = None
    port_tcp: Optional[int] = None


class SyslogReceiver:
    def __init__(self, config: Dict[str, object], state: ReceiverState) -> None:
        self._config = config
        self._state = state
        self._stop_event = threading.Event()
        self._udp_thread: Optional[threading.Thread] = None
        self._tcp_thread: Optional[threading.Thread] = None
        self._udp_socket: Optional[socket.socket] = None
        self._tcp_socket: Optional[socket.socket] = None
        self._client_threads: List[threading.Thread] = []

    def start(self) -> None:
        if self._udp_thread and self._udp_thread.is_alive():
            return
        self._stop_event.clear()
        self._udp_thread = threading.Thread(target=self._run_udp, daemon=True)
        self._tcp_thread = threading.Thread(target=self._run_tcp, daemon=True)
        self._udp_thread.start()
        self._tcp_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for sock in (self._udp_socket, self._tcp_socket):
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        if self._udp_thread:
            self._udp_thread.join(timeout=2)
        if self._tcp_thread:
            self._tcp_thread.join(timeout=2)

    def _run_udp(self) -> None:
        bind_address = str(self._config.get("bind_address", "0.0.0.0"))
        port_udp = int(self._config.get("port_udp", 1514))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_address, port_udp))
            sock.settimeout(1.0)
            self._udp_socket = sock
        except OSError as exc:
            with self._state.lock:
                self._state.udp_running = False
                self._state.running = self._state.tcp_running
                self._state.last_error = str(exc)
            return

        with self._state.lock:
            self._state.udp_running = True
            self._state.running = True
            self._state.bind_address = bind_address
            self._state.port_udp = port_udp
            self._state.last_error = None

        while not self._stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            entry = _decode_syslog(payload, addr, "udp")
            _handle_entry(entry, self._config, self._state)

        with self._state.lock:
            self._state.udp_running = False
            self._state.running = self._state.tcp_running

    def _run_tcp(self) -> None:
        bind_address = str(self._config.get("bind_address", "0.0.0.0"))
        port_tcp = int(self._config.get("port_tcp", 1514))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_address, port_tcp))
            sock.listen(5)
            sock.settimeout(1.0)
            self._tcp_socket = sock
        except OSError as exc:
            with self._state.lock:
                self._state.tcp_running = False
                self._state.running = self._state.udp_running
                self._state.last_error = str(exc)
            return

        with self._state.lock:
            self._state.tcp_running = True
            self._state.running = True
            self._state.bind_address = bind_address
            self._state.port_tcp = port_tcp
            self._state.last_error = None

        while not self._stop_event.is_set():
            try:
                conn, addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            thread = threading.Thread(
                target=self._handle_tcp_client, args=(conn, addr), daemon=True
            )
            self._client_threads.append(thread)
            thread.start()

        with self._state.lock:
            self._state.tcp_running = False
            self._state.running = self._state.udp_running

    def _handle_tcp_client(self, conn: socket.socket, addr: tuple) -> None:
        buffer = ""
        with conn:
            conn.settimeout(1.0)
            while not self._stop_event.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buffer += chunk.decode(errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip("\r")
                    if not line:
                        continue
                    entry = _decode_syslog(line.encode(), addr, "tcp")
                    _handle_entry(entry, self._config, self._state)


_state = ReceiverState()
_receiver: Optional[SyslogReceiver] = None
_config_cache: Optional[Dict[str, object]] = None


def load_config() -> Dict[str, object]:
    global _config_cache
    if _config_cache is not None:
        return dict(_config_cache)
    path = _config_path()
    if not path.exists():
        _config_cache = dict(DEFAULT_CONFIG)
        _config_path().write_text(json.dumps(_config_cache, indent=2))
        return dict(_config_cache)
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        payload = dict(DEFAULT_CONFIG)
    config = dict(DEFAULT_CONFIG)
    config.update(payload)
    _config_cache = config
    return dict(config)


def save_config(config: Dict[str, object]) -> None:
    global _config_cache
    _config_cache = dict(config)
    _config_path().write_text(json.dumps(_config_cache, indent=2))


def start_receiver() -> None:
    global _receiver
    config = load_config()
    if not config.get("enabled", True):
        return
    _ensure_db(config)
    if _receiver is None:
        _receiver = SyslogReceiver(config, _state)
    _receiver.start()


def stop_receiver() -> None:
    global _receiver
    if _receiver:
        _receiver.stop()
    _receiver = None


def apply_config(new_config: Dict[str, object]) -> None:
    previous = dict(load_config())
    updated = dict(previous)
    updated.update(new_config)
    save_config(updated)
    restart_keys = (
        "bind_address",
        "port_udp",
        "port_tcp",
        "enabled",
        "persist",
        "max_stored",
        "max_live",
    )
    restart_needed = any(previous.get(key) != updated.get(key) for key in restart_keys)
    if restart_needed:
        stop_receiver()
        if updated.get("enabled", True):
            start_receiver()


def get_status() -> Dict[str, object]:
    config = load_config()
    with _state.lock:
        status = {
            "enabled": bool(config.get("enabled", True)),
            "running": _state.running,
            "bind_address": _state.bind_address,
            "port_udp": _state.port_udp,
            "port_tcp": _state.port_tcp,
            "received_count": _state.received_count,
            "stored_count": _state.stored_count,
            "last_received": _state.last_received,
            "last_error": _state.last_error,
        }
    return status


def get_recent(limit: int = 100, offset: int = 0) -> List[Dict[str, object]]:
    with _state.lock:
        items = list(_state.recent)
    return items[offset : offset + limit]


def get_stored(
    limit: int = 100,
    offset: int = 0,
    hostname: Optional[str] = None,
    facility: Optional[int] = None,
    severity: Optional[int] = None,
) -> List[Dict[str, object]]:
    if not load_config().get("persist", True):
        return []
    db_path = _db_path()
    if not db_path.exists():
        return []
    query = """
        SELECT received_at, timestamp, hostname, app_name, facility, severity, message, raw, protocol, source_ip
        FROM syslog_messages
    """
    filters: List[str] = []
    params: List[object] = []
    if hostname:
        filters.append("hostname = ?")
        params.append(hostname)
    if facility is not None:
        filters.append("facility = ?")
        params.append(facility)
    if severity is not None:
        filters.append("severity = ?")
        params.append(severity)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows: List[Dict[str, object]] = []
    with sqlite3.connect(db_path) as conn:
        for row in conn.execute(query, params):
            rows.append(
                {
                    "received_at": row[0],
                    "timestamp": row[1],
                    "hostname": row[2],
                    "app_name": row[3],
                    "facility": row[4],
                    "severity": row[5],
                    "message": row[6],
                    "raw": row[7],
                    "protocol": row[8],
                    "source_ip": row[9],
                }
            )
    return rows


def clear_recent() -> None:
    with _state.lock:
        _state.recent.clear()


def clear_stored() -> None:
    db_path = _db_path()
    if not db_path.exists():
        return
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM syslog_messages")
        conn.commit()
    with _state.lock:
        _state.stored_count = 0


def _ensure_db(config: Dict[str, object]) -> None:
    if not config.get("persist", True):
        return
    db_path = _db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS syslog_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                timestamp TEXT,
                hostname TEXT,
                app_name TEXT,
                source_ip TEXT,
                facility INTEGER,
                severity INTEGER,
                message TEXT,
                raw TEXT,
                protocol TEXT
            )
            """
        )
        _ensure_column(conn, "syslog_messages", "source_ip", "TEXT")
        conn.commit()
        cursor = conn.execute("SELECT COUNT(*) FROM syslog_messages")
        count = cursor.fetchone()[0]
    with _state.lock:
        _state.stored_count = int(count)


def _handle_entry(
    entry: Dict[str, object], config: Dict[str, object], state: ReceiverState
) -> None:
    with state.lock:
        state.received_count += 1
        state.last_received = entry.get("received_at")  # type: ignore[assignment]
        state.recent.appendleft(entry)
        max_live = int(config.get("max_live", 1000))
        while max_live > 0 and len(state.recent) > max_live:
            state.recent.pop()
    if config.get("persist", True):
        _store_entry(entry, config, state)


def _store_entry(
    entry: Dict[str, object], config: Dict[str, object], state: ReceiverState
) -> None:
    _ensure_db(config)
    db_path = _db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO syslog_messages (
                received_at, timestamp, hostname, app_name,
                source_ip, facility, severity, message, raw, protocol
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.get("received_at"),
                entry.get("timestamp"),
                entry.get("hostname"),
                entry.get("app_name"),
                entry.get("source_ip"),
                entry.get("facility"),
                entry.get("severity"),
                entry.get("message"),
                entry.get("raw"),
                entry.get("protocol"),
            ),
        )
        conn.commit()
        _prune_db(conn, int(config.get("max_stored", 10000)))
        cursor = conn.execute("SELECT COUNT(*) FROM syslog_messages")
        count = cursor.fetchone()[0]
    with state.lock:
        state.stored_count = int(count)


def _prune_db(conn: sqlite3.Connection, max_stored: int) -> None:
    if max_stored <= 0:
        return
    conn.execute(
        """
        DELETE FROM syslog_messages WHERE id NOT IN (
            SELECT id FROM syslog_messages ORDER BY id DESC LIMIT ?
        )
        """,
        (max_stored,),
    )
    conn.commit()


def _decode_syslog(payload: bytes, addr: tuple, protocol: str) -> Dict[str, object]:
    text = payload.decode(errors="replace").strip()
    received_at = _utc_now()
    source_ip = addr[0] if addr else "unknown"

    pri = None
    rest = text
    if text.startswith("<") and ">" in text:
        end = text.find(">")
        if end > 1:
            pri_text = text[1:end]
            if pri_text.isdigit():
                pri = int(pri_text)
                rest = text[end + 1 :].lstrip()

    facility = pri >> 3 if pri is not None else None
    severity = pri & 7 if pri is not None else None

    entry: Dict[str, object] = {
        "received_at": received_at,
        "timestamp": None,
        "hostname": None,
        "app_name": None,
        "procid": None,
        "msgid": None,
        "facility": facility,
        "severity": severity,
        "message": rest,
        "raw": text,
        "protocol": protocol,
        "source_ip": source_ip,
    }

    if _parse_rfc5424(rest, entry):
        return entry
    _parse_rfc3164(rest, entry)
    return entry


def _parse_rfc5424(text: str, entry: Dict[str, object]) -> bool:
    parts = text.split(" ", 6)
    if len(parts) < 7:
        return False
    if not parts[0].isdigit():
        return False
    entry["timestamp"] = parts[1]
    entry["hostname"] = parts[2]
    entry["app_name"] = parts[3]
    entry["procid"] = parts[4]
    entry["msgid"] = parts[5]
    remainder = parts[6] if len(parts) > 6 else ""
    if " " in remainder:
        structured, message = remainder.split(" ", 1)
    else:
        structured, message = remainder, ""
    if structured and structured != "-":
        entry["message"] = message or structured
    elif message:
        entry["message"] = message
    return True


def _parse_rfc3164(text: str, entry: Dict[str, object]) -> None:
    tokens = text.split()
    if len(tokens) < 4 or tokens[0] not in MONTHS:
        return
    entry["timestamp"] = " ".join(tokens[:3])
    entry["hostname"] = tokens[3]
    remainder = " ".join(tokens[4:]) if len(tokens) > 4 else ""
    if ":" in remainder:
        tag, msg = remainder.split(":", 1)
        entry["app_name"] = tag.strip()
        entry["message"] = msg.lstrip()
    else:
        entry["message"] = remainder


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    info = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(row[1] == column for row in info):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

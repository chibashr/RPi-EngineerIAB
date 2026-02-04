"""SNMP trap receiver implementation."""

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

try:
    from pysnmp.proto import api as snmp_api
except ImportError:  # pragma: no cover - dependency may be missing
    snmp_api = None


DEFAULT_CONFIG = {
    "enabled": True,
    "bind_address": "0.0.0.0",
    "port": 1162,
    "persist": True,
    "max_stored": 10000,
    "max_live": 500,
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_path = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    base = env_path if env_path.exists() else _repo_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    module_dir = base / "snmp_trap_receiver"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _config_path() -> Path:
    return _data_dir() / "config.json"


def _db_path() -> Path:
    return _data_dir() / "traps.db"


def get_storage_info() -> Dict[str, object]:
    """Return storage directory path, list of files (name, size, mtime), and stored trap count."""
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
    with _state.lock:
        stored_count = _state.stored_count
    return {"path": str(data), "files": files, "stored_count": stored_count}


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
    bind_address: Optional[str] = None
    port: Optional[int] = None


class TrapReceiver:
    def __init__(self, config: Dict[str, object], state: ReceiverState) -> None:
        self._config = config
        self._state = state
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._socket: Optional[socket.socket] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        bind_address = str(self._config.get("bind_address", "0.0.0.0"))
        port = int(self._config.get("port", 1162))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_address, port))
            sock.settimeout(1.0)
            self._socket = sock
        except OSError as exc:
            with self._state.lock:
                self._state.running = False
                self._state.last_error = str(exc)
            return

        with self._state.lock:
            self._state.running = True
            self._state.bind_address = bind_address
            self._state.port = port
            self._state.last_error = None

        while not self._stop_event.is_set():
            try:
                payload, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            entry = _decode_trap(payload, addr)
            _handle_entry(entry, self._config, self._state)

        with self._state.lock:
            self._state.running = False


_state = ReceiverState()
_receiver: Optional[TrapReceiver] = None
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
        _receiver = TrapReceiver(config, _state)
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
        "port",
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
            "port": _state.port,
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
    source: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, object]]:
    if not load_config().get("persist", True):
        return []
    db_path = _db_path()
    if not db_path.exists():
        return []
    query = "SELECT received_at, source_ip, trap_oid, varbinds, raw_hex FROM traps"
    filters: List[str] = []
    params: List[object] = []
    if source:
        filters.append("source_ip = ?")
        params.append(source)
    if since:
        filters.append("received_at >= ?")
        params.append(since)
    if until:
        filters.append("received_at <= ?")
        params.append(until)
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
                    "source_ip": row[1],
                    "trap_oid": row[2],
                    "varbinds": json.loads(row[3]) if row[3] else [],
                    "raw_hex": row[4],
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
        conn.execute("DELETE FROM traps")
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
            CREATE TABLE IF NOT EXISTS traps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                trap_oid TEXT,
                varbinds TEXT,
                raw_hex TEXT
            )
            """
        )
        conn.commit()
        cursor = conn.execute("SELECT COUNT(*) FROM traps")
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
        max_live = int(config.get("max_live", 500))
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
            INSERT INTO traps (received_at, source_ip, trap_oid, varbinds, raw_hex)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entry.get("received_at"),
                entry.get("source_ip"),
                entry.get("trap_oid"),
                json.dumps(entry.get("varbinds", [])),
                entry.get("raw_hex"),
            ),
        )
        conn.commit()
        _prune_db(conn, int(config.get("max_stored", 10000)))
        cursor = conn.execute("SELECT COUNT(*) FROM traps")
        count = cursor.fetchone()[0]
    with state.lock:
        state.stored_count = int(count)


def _prune_db(conn: sqlite3.Connection, max_stored: int) -> None:
    if max_stored <= 0:
        return
    conn.execute(
        """
        DELETE FROM traps WHERE id NOT IN (
            SELECT id FROM traps ORDER BY id DESC LIMIT ?
        )
        """,
        (max_stored,),
    )
    conn.commit()


def _decode_trap(payload: bytes, addr: tuple) -> Dict[str, object]:
    received_at = _utc_now()
    source_ip = addr[0] if addr else "unknown"
    raw_hex = payload.hex()
    entry: Dict[str, object] = {
        "received_at": received_at,
        "source_ip": source_ip,
        "trap_oid": None,
        "varbinds": [],
        "raw_hex": raw_hex,
    }
    if snmp_api is None:
        entry["parse_error"] = "pysnmp not installed"
        return entry
    try:
        version = snmp_api.decodeMessageVersion(payload)
        proto = snmp_api.protoModules[version]
        msg = proto.Message()
        msg.decode(payload)
        pdu = proto.apiMessage.getPDU(msg)
        varbinds = []
        trap_oid = None
        for oid, val in proto.apiPDU.getVarBinds(pdu):
            item = {"oid": str(oid), "value": str(val)}
            varbinds.append(item)
            if item["oid"] == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid = item["value"]
        entry["trap_oid"] = trap_oid
        entry["varbinds"] = varbinds
    except Exception as exc:  # pragma: no cover - defensive
        entry["parse_error"] = str(exc)
    return entry

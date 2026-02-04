"""Module-managed user store for file sharing."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,32}$")
_HASH_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 200_000


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_path = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    base = env_path if env_path.exists() else _repo_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    module_dir = base / "file_share"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _users_path() -> Path:
    return _data_dir() / "users.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_users() -> Dict[str, Dict[str, object]]:
    path = _users_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _save_users(users: Dict[str, Dict[str, object]]) -> None:
    path = _users_path()
    path.write_text(json.dumps(users, indent=2, sort_keys=True), encoding="utf-8")


def list_users() -> List[Dict[str, object]]:
    users = _load_users()
    output: List[Dict[str, object]] = []
    for username, entry in sorted(users.items()):
        output.append(
            {
                "username": username,
                "has_keys": bool(entry.get("ssh_public_keys")),
                "created_at": entry.get("created_at"),
            }
        )
    return output


def create_user(username: str, password: str, ssh_keys: Optional[List[str]] = None) -> None:
    if not _USERNAME_RE.match(username or ""):
        raise ValueError("Invalid username")
    if not password:
        raise ValueError("Password is required")
    users = _load_users()
    if username in users:
        raise ValueError("User already exists")
    users[username] = {
        "password_hash": _hash_password(password),
        "ssh_public_keys": _clean_keys(ssh_keys),
        "created_at": _utc_now(),
    }
    _save_users(users)


def delete_user(username: str) -> None:
    users = _load_users()
    if username not in users:
        raise ValueError("User not found")
    users.pop(username, None)
    _save_users(users)


def set_password(username: str, password: str) -> None:
    if not password:
        raise ValueError("Password is required")
    users = _load_users()
    if username not in users:
        raise ValueError("User not found")
    users[username]["password_hash"] = _hash_password(password)
    _save_users(users)


def verify_password(username: str, password: str) -> bool:
    users = _load_users()
    entry = users.get(username)
    if not entry:
        return False
    stored = str(entry.get("password_hash") or "")
    return _verify_password(password, stored)


def authorized_keys(username: str) -> List[str]:
    users = _load_users()
    entry = users.get(username) or {}
    return _clean_keys(entry.get("ssh_public_keys"))


def _clean_keys(keys: Optional[List[str]]) -> List[str]:
    if not keys:
        return []
    cleaned = []
    for key in keys:
        if not isinstance(key, str):
            continue
        value = key.strip()
        if value:
            cleaned.append(value)
    return cleaned


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(digest).decode("ascii")
    return f"{_HASH_PREFIX}${_ITERATIONS}${salt_b64}${hash_b64}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        prefix, iterations, salt_b64, hash_b64 = stored.split("$", 3)
    except ValueError:
        return False
    if prefix != _HASH_PREFIX:
        return False
    try:
        iter_count = int(iterations)
    except ValueError:
        return False
    try:
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except (ValueError, binascii.Error, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iter_count)
    return hashlib.compare_digest(digest, expected)

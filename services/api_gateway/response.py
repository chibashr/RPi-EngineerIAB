"""Response helpers for API Gateway."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from flask import jsonify


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def success_response(
    data: Any,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> Tuple[Any, int]:
    payload = {"data": data, "meta": {"timestamp": _timestamp()}}
    if meta:
        payload["meta"].update(meta)
    return jsonify(payload), status_code


def error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500,
) -> Tuple[Any, int]:
    payload = {"error": {"code": code, "message": message, "details": details or {}}}
    return jsonify(payload), status_code

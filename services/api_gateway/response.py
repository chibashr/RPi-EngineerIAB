"""Response helpers for API Gateway."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from starlette.responses import JSONResponse


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def success_response(
    data: Any,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> JSONResponse:
    payload = {"data": data, "meta": {"timestamp": _timestamp()}}
    if meta:
        payload["meta"].update(meta)
    return JSONResponse(content=payload, status_code=status_code)


def error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500,
) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(content=payload, status_code=status_code)

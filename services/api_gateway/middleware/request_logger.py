"""Request logging middleware for HTTP API and WebSocket paths."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from lib.module_logger import get_api_logger

logger = get_api_logger(__name__)

# Paths to exclude from request logging (too noisy or not useful)
_EXCLUDE_PREFIXES = ("/health",)
_INCLUDE_PREFIXES = ("/api/", "/ws/")


def _should_log(path: str) -> bool:
    for exc in _EXCLUDE_PREFIXES:
        if path.startswith(exc):
            return False
    for inc in _INCLUDE_PREFIXES:
        if path.startswith(inc):
            return True
    return False


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log HTTP requests to /api/* and /ws/* with method, path, status, duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not _should_log(request.url.path):
            return await call_next(request)

        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            logger.error(
                "Unhandled exception %s %s error=%s",
                request.method,
                request.url.path,
                str(exc),
                exc_info=True,
            )
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            level = logging.INFO
            if status_code >= 500:
                level = logging.ERROR
            elif status_code >= 400:
                level = logging.WARNING

            logger.log(
                level,
                "%s %s %d %.0fms",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )

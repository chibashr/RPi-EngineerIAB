"""Logs API routes."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from lib.module_logger import get_service_logger
from services.logging_service import logging_service

from ..response import error_response, success_response

logger = get_service_logger(__name__)
logs_router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@logs_router.get("/system")
def list_system_logs(
    file: Optional[str] = Query(default=None, alias="file"),
    tail: int = Query(default=100),
    lines: Optional[int] = Query(default=None),
    level: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default="all"),
):
    """List or read system logs. Query params: file, tail, lines (max 1000), level, search, service."""
    n_lines = lines if lines is not None else tail
    n_lines = min(max(1, n_lines), 1000)
    try:
        if file:
            if file.lower() == "all":
                payload = logging_service.read_all_logs(
                    tail=n_lines, level=level, search=search, service=service
                )
            else:
                payload = logging_service.read_log(
                    file, tail=n_lines, level=level, search=search, service=service
                )
        else:
            payload = logging_service.list_logs()
    except ValueError as exc:
        logger.warning("Logs validation error: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except FileNotFoundError:
        logger.warning("Log file not found: %s", file or "all")
        return error_response("NOT_FOUND", "Log file not found", status_code=404)
    except Exception as exc:
        logger.exception("Logs read failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@logs_router.get("/export")
def export_logs(
    files: Optional[List[str]] = Query(default=None, alias="files"),
):
    try:
        export_path = logging_service.export_logs(files if files else None)
        logger.info("Logs exported: %s", export_path.name)
    except Exception as exc:
        logger.exception("Logs export failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return FileResponse(
        str(export_path),
        media_type="application/zip",
        filename=export_path.name,
    )

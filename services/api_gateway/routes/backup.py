"""Backup API routes."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from lib.module_logger import get_service_logger
from services.api_gateway.routes.auth import require_admin
from services.update_manager import update_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
backup_router = APIRouter(prefix="/api/v1/backup", tags=["backup"])


@backup_router.get("/config")
def download_config():
    try:
        backup_path = update_manager.create_config_backup(label="config")
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return FileResponse(
        str(backup_path),
        media_type="application/zip",
        filename=backup_path.name,
    )


@backup_router.post("/restore")
async def restore_config(file: UploadFile = File(...), _: str = Depends(require_admin)):
    if not file.filename:
        return error_response("VALIDATION_ERROR", "Backup file is required", status_code=400)
    temp_path = None
    try:
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        loop = asyncio.get_running_loop()
        payload = await loop.run_in_executor(
            None,
            lambda: update_manager.restore_config(temp_path),
        )
    except RuntimeError as exc:
        logger.warning("Restore failed: %s", exc)
        return error_response(
            "INTERNAL_ERROR",
            f"Restore failed: {exc}. Config may be partially restored; verify system state.",
            status_code=500,
        )
    except Exception as exc:
        logger.exception("Restore failed: %s", exc)
        return error_response(
            "INTERNAL_ERROR",
            f"Restore failed: {exc}. Config may be partially restored; verify system state.",
            status_code=500,
        )
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to remove temp backup file %s: %s", temp_path, exc)
    return success_response(payload)

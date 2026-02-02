"""Backup API routes."""

import logging

import tempfile
from pathlib import Path

from flask import Blueprint, request, send_file

from services.update_manager import update_manager

from ..response import error_response, success_response

backup_bp = Blueprint("backup", __name__, url_prefix="/api/v1/backup")
logger = logging.getLogger(__name__)


@backup_bp.get("/config")
def download_config():
    try:
        backup_path = update_manager.create_config_backup(label="config")
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=backup_path.name,
        mimetype="application/zip",
    )


@backup_bp.post("/restore")
def restore_config():
    if "file" not in request.files:
        return error_response("VALIDATION_ERROR", "Backup file is required", status_code=400)
    file = request.files["file"]
    if not file:
        return error_response("VALIDATION_ERROR", "Backup file is required", status_code=400)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        payload = update_manager.restore_config(temp_path)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to remove temp backup file %s: %s", temp_path, exc)
    return success_response(payload)

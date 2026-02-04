"""Packet capture API routes."""

from flask import Blueprint, send_file, request

from lib.module_logger import get_service_logger
from services.capture_manager import capture_manager

from ..response import error_response, success_response

logger = get_service_logger(__name__)
capture_bp = Blueprint("capture", __name__, url_prefix="/api/v1/capture")


@capture_bp.get("/interfaces")
def list_interfaces():
    return success_response(capture_manager.list_interfaces())


@capture_bp.post("/start")
def start_capture():
    payload = request.get_json(silent=True) or {}
    try:
        data = capture_manager.start_capture(payload)
        logger.info("Capture started via API: %s on %s", data.get("capture_id", "")[:8], data.get("interface"))
    except ValueError as exc:
        logger.warning("Capture start validation error: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Capture start failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@capture_bp.get("/active")
def list_active_captures():
    return success_response(capture_manager.list_active())


@capture_bp.get("/active/<capture_id>")
def get_active_capture(capture_id: str):
    try:
        data = capture_manager.get_active(capture_id)
    except KeyError as exc:
        logger.debug("Active capture not found: %s", capture_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.post("/active/<capture_id>/stop")
def stop_active_capture(capture_id: str):
    try:
        data = capture_manager.stop_capture(capture_id)
        logger.info("Capture stopped via API: %s", capture_id[:8])
    except KeyError as exc:
        logger.warning("Capture stop not found: %s", capture_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/completed")
def list_completed_captures():
    return success_response(capture_manager.list_completed())


@capture_bp.get("/completed/<capture_id>")
def get_completed_capture(capture_id: str):
    try:
        data = capture_manager.get_completed(capture_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/completed/<capture_id>/download")
def download_capture(capture_id: str):
    try:
        job = capture_manager.get_job(capture_id)
    except Exception as exc:
        logger.debug("Capture download lookup failed %s: %s", capture_id, exc)
        job = None
    if not job or not job.file_path or not job.file_path.exists():
        return error_response("NOT_FOUND", "Capture not found", status_code=404)
    logger.info("Capture downloaded: %s", capture_id[:8])
    return send_file(str(job.file_path), as_attachment=True)


@capture_bp.delete("/completed/<capture_id>")
def delete_capture(capture_id: str):
    try:
        data = capture_manager.delete_completed(capture_id)
        logger.info("Capture deleted via API: %s", capture_id[:8])
    except KeyError as exc:
        logger.warning("Capture delete not found: %s", capture_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/<capture_id>/stats")
def get_capture_stats(capture_id: str):
    try:
        data = capture_manager.get_stats(capture_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/<capture_id>/packets")
def get_capture_packets(capture_id: str):
    try:
        data = capture_manager.get_packets(capture_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/<capture_id>/conversations")
def get_capture_conversations(capture_id: str):
    try:
        data = capture_manager.get_conversations(capture_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.get("/<capture_id>/protocols")
def get_capture_protocols(capture_id: str):
    try:
        data = capture_manager.get_protocols(capture_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)

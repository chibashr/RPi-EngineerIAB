"""Packet capture API routes."""

from flask import Blueprint, send_file, request

from services.capture_manager import capture_manager

from ..response import error_response, success_response

capture_bp = Blueprint("capture", __name__, url_prefix="/api/v1/capture")


@capture_bp.get("/interfaces")
def list_interfaces():
    return success_response(capture_manager.list_interfaces())


@capture_bp.post("/start")
def start_capture():
    payload = request.get_json(silent=True) or {}
    try:
        data = capture_manager.start_capture(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except Exception as exc:  # pragma: no cover - defensive
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
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@capture_bp.post("/active/<capture_id>/stop")
def stop_active_capture(capture_id: str):
    try:
        data = capture_manager.stop_capture(capture_id)
    except KeyError as exc:
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
    except Exception:
        job = None
    if not job or not job.file_path or not job.file_path.exists():
        return error_response("NOT_FOUND", "Capture not found", status_code=404)
    return send_file(str(job.file_path), as_attachment=True)


@capture_bp.delete("/completed/<capture_id>")
def delete_capture(capture_id: str):
    try:
        data = capture_manager.delete_completed(capture_id)
    except KeyError as exc:
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

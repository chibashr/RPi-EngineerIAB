"""Logs API routes."""

from flask import Blueprint, request, send_file

from services.logging_service import logging_service

from ..response import error_response, success_response

logs_bp = Blueprint("logs", __name__, url_prefix="/api/v1/logs")


@logs_bp.get("/system")
def list_system_logs():
    file_name = request.args.get("file")
    tail = request.args.get("tail", type=int) or 100
    level = request.args.get("level")
    search = request.args.get("search")
    service = request.args.get("service")
    try:
        if file_name:
            payload = logging_service.read_log(
                file_name, tail=tail, level=level, search=search, service=service
            )
        else:
            payload = logging_service.list_logs()
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except FileNotFoundError:
        return error_response("NOT_FOUND", "Log file not found", status_code=404)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(payload)


@logs_bp.get("/export")
def export_logs():
    files = request.args.getlist("files")
    try:
        export_path = logging_service.export_logs(files if files else None)
    except Exception as exc:
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return send_file(
        export_path,
        as_attachment=True,
        download_name=export_path.name,
        mimetype="application/zip",
    )

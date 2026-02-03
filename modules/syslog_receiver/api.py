"""Syslog receiver API routes."""

from flask import Blueprint, request

from services.api_gateway.response import error_response, success_response

from . import receiver

syslog_bp = Blueprint("syslog_receiver", __name__, url_prefix="/api/v1/syslog")


def _get_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@syslog_bp.get("/status")
def status():
    return success_response(receiver.get_status())


@syslog_bp.get("/recent")
def recent():
    limit = _get_int(request.args.get("limit"), 100)
    offset = _get_int(request.args.get("offset"), 0)
    payload = receiver.get_recent(limit=limit, offset=offset)
    return success_response({"items": payload})


@syslog_bp.get("/stored")
def stored():
    limit = _get_int(request.args.get("limit"), 100)
    offset = _get_int(request.args.get("offset"), 0)
    hostname = request.args.get("hostname")
    facility = request.args.get("facility")
    severity = request.args.get("severity")
    facility_val = _get_int(facility, -1) if facility is not None else None
    severity_val = _get_int(severity, -1) if severity is not None else None
    if facility_val == -1:
        facility_val = None
    if severity_val == -1:
        severity_val = None
    payload = receiver.get_stored(
        limit=limit,
        offset=offset,
        hostname=hostname,
        facility=facility_val,
        severity=severity_val,
    )
    return success_response({"items": payload})


@syslog_bp.get("/config")
def get_config():
    return success_response(receiver.load_config())


@syslog_bp.put("/config")
def update_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Invalid configuration payload", 400)
    receiver.apply_config(payload)
    return success_response(receiver.load_config())


@syslog_bp.post("/clear")
def clear():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target", "live")
    if target in ("live", "all"):
        receiver.clear_recent()
    if target in ("stored", "all"):
        receiver.clear_stored()
    return success_response({"cleared": target})


def register_routes(app) -> None:  # type: ignore[no-untyped-def]
    app.register_blueprint(syslog_bp)

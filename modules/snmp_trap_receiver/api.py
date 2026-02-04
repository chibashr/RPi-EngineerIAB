"""SNMP trap receiver API routes."""

from flask import Blueprint, request

from services.api_gateway.response import error_response, success_response

from . import receiver

snmp_bp = Blueprint("snmp_trap_receiver", __name__, url_prefix="/api/v1/snmp_traps")


def _get_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@snmp_bp.get("/status")
def status():
    return success_response(receiver.get_status())


@snmp_bp.get("/recent")
def recent():
    limit = _get_int(request.args.get("limit"), 100)
    offset = _get_int(request.args.get("offset"), 0)
    payload = receiver.get_recent(limit=limit, offset=offset)
    return success_response({"items": payload})


@snmp_bp.get("/stored")
def stored():
    limit = _get_int(request.args.get("limit"), 100)
    offset = _get_int(request.args.get("offset"), 0)
    source = request.args.get("source")
    since = request.args.get("since")
    until = request.args.get("until")
    payload = receiver.get_stored(
        limit=limit, offset=offset, source=source, since=since, until=until
    )
    return success_response({"items": payload})


@snmp_bp.get("/config")
def get_config():
    return success_response(receiver.load_config())


@snmp_bp.put("/config")
def update_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Invalid configuration payload", 400)
    receiver.apply_config(payload)
    return success_response(receiver.load_config())


@snmp_bp.post("/clear")
def clear():
    payload = request.get_json(silent=True) or {}
    target = payload.get("target", "live")
    if target in ("live", "all"):
        receiver.clear_recent()
    if target in ("stored", "all"):
        receiver.clear_stored()
    return success_response({"cleared": target})


@snmp_bp.post("/start")
def start():
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return success_response(receiver.get_status())


@snmp_bp.post("/stop")
def stop():
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = False
    receiver.save_config(config)
    return success_response(receiver.get_status())


@snmp_bp.post("/restart")
def restart():
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return success_response(receiver.get_status())


@snmp_bp.get("/storage")
def storage():
    return success_response(receiver.get_storage_info())


def register_routes(app) -> None:  # type: ignore[no-untyped-def]
    app.register_blueprint(snmp_bp)

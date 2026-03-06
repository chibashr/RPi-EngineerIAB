"""SNMP trap receiver API routes."""

from typing import Optional

from fastapi import APIRouter, Body, Query

from services.api_gateway.response import error_response, success_response

from . import receiver

router = APIRouter(tags=["snmp_trap_receiver"])


def _get_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@router.get("/status")
def status():
    return success_response(receiver.get_status())


@router.get("/recent")
def recent(
    limit: int = Query(100, ge=0),
    offset: int = Query(0, ge=0),
):
    payload = receiver.get_recent(limit=limit, offset=offset)
    return success_response({"items": payload})


@router.get("/stored")
def stored(
    limit: int = Query(100, ge=0),
    offset: int = Query(0, ge=0),
    source: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    payload = receiver.get_stored(
        limit=limit, offset=offset, source=source, since=since, until=until
    )
    return success_response({"items": payload})


@router.get("/config")
def get_config():
    return success_response(receiver.load_config())


@router.put("/config")
def update_config(payload: Optional[dict] = Body(default=None)):
    data = payload or {}
    if not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Invalid configuration payload", status_code=400)
    receiver.apply_config(data)
    return success_response(receiver.load_config())


@router.post("/clear")
def clear(payload: Optional[dict] = Body(default=None)):
    data = payload or {}
    target = data.get("target", "live")
    if target in ("live", "all"):
        receiver.clear_recent()
    if target in ("stored", "all"):
        receiver.clear_stored()
    return success_response({"cleared": target})


@router.post("/start")
def start():
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return success_response(receiver.get_status())


@router.post("/stop")
def stop():
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = False
    receiver.save_config(config)
    return success_response(receiver.get_status())


@router.post("/restart")
def restart():
    receiver.stop_receiver()
    config = receiver.load_config()
    config["enabled"] = True
    receiver.save_config(config)
    receiver.start_receiver()
    return success_response(receiver.get_status())


@router.get("/storage")
def storage():
    return success_response(receiver.get_storage_info())

"""Serial API routes."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Body, Query
from starlette.responses import FileResponse

from lib.module_logger import get_service_logger
from services.serial_manager import serial_manager
from services.serial_manager.manager import EXPORT_DIR

from ..response import error_response, success_response

logger = get_service_logger(__name__)
router = APIRouter(prefix="/api/v1/serial", tags=["serial"])


@router.get("/devices")
async def list_devices(
    refresh: str = Query(default="", alias="refresh"),
):
    force_refresh = refresh.lower() in ("1", "true", "yes")
    data = await asyncio.to_thread(
        serial_manager.list_devices, force_refresh=force_refresh
    )
    return success_response(data)


@router.get("/devices/{device_id}")
def get_device(device_id: str):
    try:
        data = serial_manager.get_device(device_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.put("/devices/configure")
def update_device_by_body(payload: dict | None = Body(default=None)):
    """Update device config with device_id in body. Avoids 405 from nginx when device_id contains slashes (e.g. /dev/ttyUSB1)."""
    payload = payload or {}
    device_id = payload.get("device_id") or payload.get("device")
    if not device_id or not str(device_id).strip():
        return error_response("VALIDATION_ERROR", "device_id is required", status_code=400)
    device_id = str(device_id).strip()
    config_payload = {k: v for k, v in payload.items() if k not in ("device_id", "device")}
    try:
        data = serial_manager.update_device(device_id, config_payload)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.put("/devices/{device_id}")
def update_device(device_id: str, payload: dict | None = Body(default=None)):
    payload = payload or {}
    try:
        data = serial_manager.update_device(device_id, payload)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.post("/devices/{device_id}/test")
def test_device(device_id: str):
    try:
        data = serial_manager.test_device(device_id)
        logger.info("Serial device tested via API: %s", device_id)
    except KeyError as exc:
        logger.warning("Serial device test not found: %s", device_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except RuntimeError as exc:
        logger.warning("Serial device test failed %s: %s", device_id, exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data)


@router.get("/sessions")
def list_sessions():
    return success_response(serial_manager.list_sessions())


@router.post("/sessions")
def create_session(payload: dict | None = Body(default=None)):
    payload = payload or {}
    logger.info("create_session API: device_id=%s", payload.get("device_id"))
    try:
        data = serial_manager.create_session(payload)
        logger.info(
            "Serial session created via API: %s for %s",
            data.get("session_id", "")[:8],
            data.get("device_id"),
        )
    except ValueError as exc:
        logger.warning("Serial session create validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    except KeyError as exc:
        logger.warning("Serial session create device not found: %s", exc)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    except RuntimeError as exc:
        logger.error("Serial session create failed: %s", exc)
        return error_response("INTERNAL_ERROR", str(exc), status_code=500)
    return success_response(data, status_code=201)


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    try:
        data = serial_manager.get_session(session_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.put("/sessions/{session_id}")
def update_session(session_id: str, payload: dict | None = Body(default=None)):
    payload = payload or {}
    try:
        data = serial_manager.update_session(session_id, payload)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        data = serial_manager.delete_session(session_id)
        logger.info("Serial session deleted via API: %s", session_id[:8])
    except KeyError as exc:
        logger.warning("Serial session delete not found: %s", session_id)
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.get("/logs")
def list_logs(
    device: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=0),
):
    return success_response(serial_manager.list_logs(device, since, limit))


@router.get("/logs/{log_id}/content")
async def get_log_content(log_id: str):
    try:
        data = await asyncio.to_thread(serial_manager.get_log_content, log_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.delete("/logs/{log_id}")
def delete_log(log_id: str):
    try:
        data = serial_manager.delete_log(log_id)
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.put("/logs/{log_id}")
def rename_log(log_id: str, payload: dict | None = Body(default=None)):
    payload = payload or {}
    display_name = payload.get("name") or payload.get("display_name")
    if not display_name or not str(display_name).strip():
        return error_response("VALIDATION_ERROR", "name is required", status_code=400)
    try:
        data = serial_manager.rename_log(log_id, str(display_name))
    except KeyError as exc:
        return error_response("NOT_FOUND", str(exc), status_code=404)
    return success_response(data)


@router.post("/logs/export")
def export_logs(payload: dict | None = Body(default=None)):
    payload = payload or {}
    log_ids = payload.get("log_ids", [])
    if not isinstance(log_ids, list):
        return error_response(
            "VALIDATION_ERROR", "log_ids must be a list", status_code=400
        )
    data = serial_manager.export_logs(log_ids)
    return success_response(data, status_code=201)


@router.get("/logs/export/{archive_name}")
def download_export(archive_name: str):
    safe_name = Path(archive_name).name
    if safe_name != archive_name:
        return error_response("VALIDATION_ERROR", "Invalid archive name", status_code=400)
    archive_path = EXPORT_DIR / archive_name
    if not archive_path.exists():
        return error_response("NOT_FOUND", "Export archive not found", status_code=404)
    return FileResponse(
        path=str(archive_path),
        filename=archive_path.name,
        media_type="application/zip",
    )

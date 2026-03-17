from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse

from .manager import EXPORT_DIR, get_serial_manager

router = APIRouter()


@router.get("/devices")
async def list_devices(force_refresh: bool = Query(False)) -> dict[str, Any]:
    manager = get_serial_manager()
    return manager.list_devices(force_refresh=force_refresh)


@router.get("/devices/{device_id}")
async def get_device(device_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.get_device(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")


@router.put("/devices/{device_id}")
async def update_device(device_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.update_device(device_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")


@router.put("/devices/configure")
async def configure_device(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_serial_manager()
    device_id = payload.get("device_id")
    config = payload.get("config") or {}
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    try:
        return manager.update_device(device_id, config)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")


@router.post("/devices/{device_id}/test")
async def test_device(device_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.test_device(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions")
async def create_session(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.create_session(payload)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    manager = get_serial_manager()
    return manager.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.update_session(session_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.delete_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/logs")
async def list_logs(
    device: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100, ge=0),
) -> dict[str, Any]:
    manager = get_serial_manager()
    return manager.list_logs(device=device, since=since, limit=limit)


@router.get("/logs/{log_id}/content")
async def get_log_content(log_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.get_log_content(log_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Log not found")


@router.put("/logs/{log_id}")
async def rename_log(
    log_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    display_name = payload.get("name") or payload.get("display_name")
    if not display_name:
        raise HTTPException(status_code=400, detail="name is required")
    manager = get_serial_manager()
    try:
        return manager.rename_log(log_id, display_name)
    except KeyError:
        raise HTTPException(status_code=404, detail="Log not found")


@router.delete("/logs/{log_id}")
async def delete_log(log_id: str) -> dict[str, Any]:
    manager = get_serial_manager()
    try:
        return manager.delete_log(log_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Log not found")


@router.post("/logs/export")
async def export_logs(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    log_ids = payload.get("log_ids") or payload.get("ids")
    if not isinstance(log_ids, list) or not log_ids:
        raise HTTPException(status_code=400, detail="log_ids must be a non-empty list")
    manager = get_serial_manager()
    return manager.export_logs(list(map(str, log_ids)))


@router.get("/logs/export/{name}")
async def download_export(name: str) -> FileResponse:
    archive_path = EXPORT_DIR / name
    if not archive_path.exists() or not archive_path.is_file():
        raise HTTPException(status_code=404, detail="Archive not found")
    return FileResponse(path=str(archive_path), filename=archive_path.name)

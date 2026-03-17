from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from .manager import get_capture_manager

router = APIRouter()


@router.get("/interfaces")
async def list_interfaces() -> dict[str, Any]:
    manager = get_capture_manager()
    return manager.list_interfaces()


@router.post("/start")
async def start_capture(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.start_capture(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/active")
async def list_active() -> dict[str, Any]:
    manager = get_capture_manager()
    return manager.list_active()


@router.get("/active/{capture_id}")
async def get_active(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_active(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Active capture not found")


@router.post("/active/{capture_id}/stop")
async def stop_capture(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.stop_capture(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Active capture not found")


@router.get("/completed")
async def list_completed() -> dict[str, Any]:
    manager = get_capture_manager()
    return manager.list_completed()


@router.get("/completed/{capture_id}")
async def get_completed(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_completed(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Completed capture not found")


@router.delete("/completed/{capture_id}")
async def delete_completed(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.delete_completed(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Completed capture not found")


@router.get("/completed/{capture_id}/download")
async def download_completed(capture_id: str) -> FileResponse:
    manager = get_capture_manager()
    try:
        path = manager.get_capture_file_path(capture_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Capture file not found")
    return FileResponse(path=str(path), filename=path.name)


@router.get("/{capture_id}/stats")
async def get_stats(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_stats(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found")


@router.get("/{capture_id}/packets")
async def get_packets(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_packets(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found")


@router.get("/{capture_id}/conversations")
async def get_conversations(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_conversations(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found")


@router.get("/{capture_id}/protocols")
async def get_protocols(capture_id: str) -> dict[str, Any]:
    manager = get_capture_manager()
    try:
        return manager.get_protocols(capture_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found")

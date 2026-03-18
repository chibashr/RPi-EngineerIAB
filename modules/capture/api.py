from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from services.api_gateway.response import error_response, success_response

from .manager import get_capture_manager

router = APIRouter()


@router.get("/interfaces")
async def list_interfaces() -> Any:
    manager = get_capture_manager()
    return success_response(manager.list_interfaces())


@router.post("/start")
async def start_capture(payload: dict[str, Any] = Body(...)) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.start_capture(payload), status_code=201)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError:
        return error_response(
            "INTERNAL_ERROR",
            "Capture start failed",
            status_code=500,
        )


@router.get("/active")
async def list_active() -> Any:
    manager = get_capture_manager()
    return success_response(manager.list_active())


@router.get("/active/{capture_id}")
async def get_active(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_active(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Active capture not found") from None


@router.post("/active/{capture_id}/stop")
async def stop_capture(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.stop_capture(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Active capture not found") from None


@router.get("/completed")
async def list_completed() -> Any:
    manager = get_capture_manager()
    return success_response(manager.list_completed())


@router.get("/completed/{capture_id}")
async def get_completed(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_completed(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Completed capture not found") from None


@router.delete("/completed/{capture_id}")
async def delete_completed(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.delete_completed(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Completed capture not found") from None


@router.get("/completed/{capture_id}/download")
async def download_completed(capture_id: str) -> FileResponse:
    manager = get_capture_manager()
    try:
        path = manager.get_capture_file_path(capture_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Capture file not found") from None
    return FileResponse(path=str(path), filename=path.name)


@router.get("/{capture_id}/stats")
async def get_stats(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_stats(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found") from None


@router.get("/{capture_id}/packets")
async def get_packets(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_packets(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found") from None


@router.get("/{capture_id}/conversations")
async def get_conversations(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_conversations(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found") from None


@router.get("/{capture_id}/protocols")
async def get_protocols(capture_id: str) -> Any:
    manager = get_capture_manager()
    try:
        return success_response(manager.get_protocols(capture_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Capture not found") from None

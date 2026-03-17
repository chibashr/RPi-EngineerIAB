from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from .manager import get_remote_console_manager

router = APIRouter()


@router.get("/targets")
async def list_targets() -> dict[str, list[dict[str, Any]]]:
    manager = get_remote_console_manager()
    return manager.list_targets()


@router.get("/targets/{target_id}")
async def get_target(target_id: str) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.get_target(target_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Target not found")


@router.post("/targets")
async def create_target(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.create_target(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/targets/{target_id}")
async def update_target(
    target_id: str,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.update_target(target_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Target not found")


@router.delete("/targets/{target_id}")
async def delete_target(target_id: str) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.delete_target(target_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Target not found")


@router.post("/sessions")
async def create_session(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.create_session(payload)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/sessions")
async def list_sessions() -> dict[str, Any]:
    manager = get_remote_console_manager()
    return manager.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    manager = get_remote_console_manager()
    try:
        return manager.delete_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile

from . import manager

router = APIRouter()


@router.get("/status")
async def get_status() -> dict[str, Any]:
    try:
        return manager.get_status()
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/config")
async def get_config() -> dict[str, Any]:
    try:
        return manager.load_config()
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.put("/config")
async def update_config(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    data = payload or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid configuration payload")
    try:
        return manager.apply_config(data)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/users")
async def list_users() -> dict[str, list[dict[str, Any]]]:
    try:
        users = manager.list_users()
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"users": users}


@router.post("/users")
async def create_user(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    data = payload or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid user payload")
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    keys = data.get("ssh_public_keys") or []
    if not isinstance(keys, list):
        raise HTTPException(
            status_code=400,
            detail="ssh_public_keys must be a list",
        )
    try:
        manager.create_user(username, password, keys)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"created": username}


@router.delete("/users/{username}")
async def delete_user(username: str) -> dict[str, Any]:
    try:
        manager.delete_user(username)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": username}


@router.put("/users/{username}/password")
async def update_password(
    username: str,
    payload: dict[str, Any] | None = Body(default=None),
) -> dict[str, Any]:
    data = payload or {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    password = str(data.get("password") or "")
    try:
        manager.set_password(username, password)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"updated": username}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    subpath: str = "",
) -> dict[str, Any]:
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="File is required")
    try:
        content = await file.read()
        return manager.save_upload(file.filename, content, subpath or None)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/files")
async def list_files(subpath: str = Query("")) -> dict[str, Any]:
    try:
        return manager.list_files(subpath or None)
    except manager.FileshareUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

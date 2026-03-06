"""File share API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, File, Form, Query, UploadFile

from lib.module_logger import get_module_logger
from services.api_gateway.response import error_response, success_response

from . import main, user_store

logger = get_module_logger(__name__)
router = APIRouter(tags=["file_share"])


def _resolve_subpath(share_root: Path, subpath: Optional[str]) -> Path:
    rel = Path(subpath or "").as_posix().lstrip("/")
    target = (share_root / rel).resolve()
    if share_root not in target.parents and target != share_root:
        raise ValueError("Invalid path")
    return target


def _list_dir(target: Path) -> List[Dict[str, object]]:
    items = []
    for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
        stat = entry.stat()
        items.append(
            {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return items


@router.get("/status")
def status():
    return success_response(main.get_status())


@router.get("/config")
def get_config():
    return success_response(main.load_config())


@router.put("/config")
def update_config(payload: Optional[dict] = Body(default=None)):
    data = payload or {}
    if not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Invalid configuration payload", status_code=400)
    try:
        config = main.apply_config(data)
        logger.info("File share config updated via API")
    except ValueError as exc:
        logger.warning("File share config validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    return success_response(config)


@router.get("/users")
def list_users():
    return success_response({"users": user_store.list_users()})


@router.post("/users")
def create_user(payload: Optional[dict] = Body(default=None)):
    data = payload or {}
    if not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Invalid user payload", status_code=400)
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    keys = data.get("ssh_public_keys") or []
    if not isinstance(keys, list):
        return error_response("VALIDATION_ERROR", "ssh_public_keys must be a list", status_code=400)
    try:
        user_store.create_user(username, password, keys)
        logger.info("File share user created: %s", username)
    except ValueError as exc:
        logger.warning("File share user create validation: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    return success_response({"created": username})


@router.delete("/users/{username}")
def delete_user(username: str):
    try:
        user_store.delete_user(username)
        logger.info("File share user deleted: %s", username)
    except ValueError as exc:
        logger.warning("File share user delete: %s", exc)
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    return success_response({"deleted": username})


@router.put("/users/{username}/password")
def update_password(username: str, payload: Optional[dict] = Body(default=None)):
    data = payload or {}
    if not isinstance(data, dict):
        return error_response("VALIDATION_ERROR", "Invalid payload", status_code=400)
    password = str(data.get("password") or "")
    try:
        user_store.set_password(username, password)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    return success_response({"updated": username})


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    subpath: str = Form(""),
):
    if not file or not file.filename:
        return error_response("VALIDATION_ERROR", "File is required", status_code=400)
    config = main.load_config()
    share_root = Path(str(config["share_path"]))
    share_root.mkdir(parents=True, exist_ok=True)
    try:
        target_dir = _resolve_subpath(share_root, subpath or None)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename).name
    destination = target_dir / filename
    content = await file.read()
    destination.write_bytes(content)
    logger.info("File share upload: %s to %s", filename, subpath or "/")
    return success_response({"uploaded": filename, "path": str(destination.relative_to(share_root))})


@router.get("/files")
def list_files(subpath: str = Query("")):
    config = main.load_config()
    share_root = Path(str(config["share_path"]))
    share_root.mkdir(parents=True, exist_ok=True)
    try:
        target = _resolve_subpath(share_root, subpath or None)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), status_code=400)
    if not target.exists():
        return success_response({"items": []})
    if not target.is_dir():
        return error_response("VALIDATION_ERROR", "Path is not a directory", status_code=400)
    return success_response({"items": _list_dir(target)})

"""File share API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from flask import Blueprint, request

from services.api_gateway.response import error_response, success_response

from . import main, user_store

fileshare_bp = Blueprint("file_share", __name__, url_prefix="/api/v1/fileshare")


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


@fileshare_bp.get("/status")
def status():
    return success_response(main.get_status())


@fileshare_bp.get("/config")
def get_config():
    return success_response(main.load_config())


@fileshare_bp.put("/config")
def update_config():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Invalid configuration payload", 400)
    try:
        config = main.apply_config(payload)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    return success_response(config)


@fileshare_bp.get("/users")
def list_users():
    return success_response({"users": user_store.list_users()})


@fileshare_bp.post("/users")
def create_user():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Invalid user payload", 400)
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    keys = payload.get("ssh_public_keys") or []
    if not isinstance(keys, list):
        return error_response("VALIDATION_ERROR", "ssh_public_keys must be a list", 400)
    try:
        user_store.create_user(username, password, keys)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    return success_response({"created": username})


@fileshare_bp.delete("/users/<username>")
def delete_user(username: str):
    try:
        user_store.delete_user(username)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    return success_response({"deleted": username})


@fileshare_bp.put("/users/<username>/password")
def update_password(username: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return error_response("VALIDATION_ERROR", "Invalid payload", 400)
    password = str(payload.get("password") or "")
    try:
        user_store.set_password(username, password)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    return success_response({"updated": username})


@fileshare_bp.post("/upload")
def upload_file():
    if "file" not in request.files:
        return error_response("VALIDATION_ERROR", "File is required", 400)
    file = request.files["file"]
    if not file or not file.filename:
        return error_response("VALIDATION_ERROR", "File is required", 400)
    config = main.load_config()
    share_root = Path(str(config["share_path"]))
    share_root.mkdir(parents=True, exist_ok=True)
    subpath = request.form.get("subpath") or ""
    try:
        target_dir = _resolve_subpath(share_root, subpath)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(file.filename).name
    destination = target_dir / filename
    file.save(str(destination))
    return success_response({"uploaded": filename, "path": str(destination.relative_to(share_root))})


@fileshare_bp.get("/files")
def list_files():
    config = main.load_config()
    share_root = Path(str(config["share_path"]))
    share_root.mkdir(parents=True, exist_ok=True)
    subpath = request.args.get("subpath") or ""
    try:
        target = _resolve_subpath(share_root, subpath)
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    if not target.exists():
        return success_response({"items": []})
    if not target.is_dir():
        return error_response("VALIDATION_ERROR", "Path is not a directory", 400)
    return success_response({"items": _list_dir(target)})


def register_routes(app) -> None:  # type: ignore[no-untyped-def]
    app.register_blueprint(fileshare_bp)

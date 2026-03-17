from __future__ import annotations

from pathlib import Path

from lib.module_logger import get_service_logger

logger = get_service_logger("fileshare")

try:
    from modules.file_share import main as _legacy_main
    from modules.file_share import user_store as _legacy_user_store
except Exception as exc:  # pragma: no cover - defensive
    logger.warning("Legacy file_share backend unavailable: %s", exc)
    _legacy_main = None  # type: ignore[assignment]
    _legacy_user_store = None  # type: ignore[assignment]


class FileshareUnavailable(RuntimeError):
    pass


def _ensure_available() -> tuple[object, object]:
    if _legacy_main is None or _legacy_user_store is None:
        raise FileshareUnavailable("File Share module dependencies not installed (pyftpdlib, paramiko).")
    return _legacy_main, _legacy_user_store


def initialize_fileshare() -> None:
    try:
        legacy_main, _ = _ensure_available()
    except FileshareUnavailable as exc:  # pragma: no cover - environment dependent
        logger.warning("Fileshare unavailable during initialize: %s", exc)
        return
    legacy_main.initialize()  # type: ignore[attr-defined]


def get_status() -> dict[str, object]:
    legacy_main, _ = _ensure_available()
    return legacy_main.get_status()  # type: ignore[attr-defined]


def load_config() -> dict[str, object]:
    legacy_main, _ = _ensure_available()
    return legacy_main.load_config()  # type: ignore[attr-defined]


def apply_config(payload: dict[str, object]) -> dict[str, object]:
    legacy_main, _ = _ensure_available()
    return legacy_main.apply_config(payload)  # type: ignore[attr-defined]


def list_users() -> list[dict[str, object]]:
    _, legacy_users = _ensure_available()
    return legacy_users.list_users()  # type: ignore[attr-defined]


def create_user(username: str, password: str, ssh_public_keys: list[str] | None = None) -> None:
    _, legacy_users = _ensure_available()
    legacy_users.create_user(username, password, ssh_public_keys)  # type: ignore[attr-defined]


def delete_user(username: str) -> None:
    _, legacy_users = _ensure_available()
    legacy_users.delete_user(username)  # type: ignore[attr-defined]


def set_password(username: str, password: str) -> None:
    _, legacy_users = _ensure_available()
    legacy_users.set_password(username, password)  # type: ignore[attr-defined]


def _resolve_subpath(share_root: Path, subpath: str | None) -> Path:
    rel = Path(subpath or "").as_posix().lstrip("/")
    target = (share_root / rel).resolve()
    if share_root not in target.parents and target != share_root:
        raise ValueError("Invalid path")
    return target


def _list_dir(target: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
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


def _get_share_root(config: dict[str, object]) -> Path:
    share_path = Path(str(config.get("share_path") or "") or ".")
    if not share_path.is_absolute():
        legacy_main, _ = _ensure_available()
        legacy_config = legacy_main.load_config()  # type: ignore[attr-defined]
        share_path = Path(str(legacy_config.get("share_path") or "."))
    share_path.mkdir(parents=True, exist_ok=True)
    return share_path


def list_files(subpath: str | None = None) -> dict[str, object]:
    config = load_config()
    share_root = _get_share_root(config)
    try:
        target = _resolve_subpath(share_root, subpath)
    except ValueError as exc:
        raise ValueError(str(exc))
    if not target.exists():
        return {"items": []}
    if not target.is_dir():
        raise ValueError("Path is not a directory")
    return {"items": _list_dir(target)}


def save_upload(filename: str, content: bytes, subpath: str | None = None) -> dict[str, object]:
    config = load_config()
    share_root = _get_share_root(config)
    try:
        target_dir = _resolve_subpath(share_root, subpath)
    except ValueError as exc:
        raise ValueError(str(exc))
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    destination = target_dir / safe_name
    destination.write_bytes(content)
    logger.info("File share upload: %s to %s", safe_name, subpath or "/")
    relative_path = str(destination.relative_to(share_root))
    return {"uploaded": safe_name, "path": relative_path}

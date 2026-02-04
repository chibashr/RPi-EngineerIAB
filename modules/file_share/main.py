"""File share module lifecycle and configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from . import server_ftp, server_sftp


DEFAULT_CONFIG: Dict[str, object] = {
    "share_path": "",
    "enable_ftp": False,
    "enable_sftp_scp": False,
    "ftp_bind_addresses": "0.0.0.0",
    "sftp_bind_addresses": "0.0.0.0",
    "ftp_port": 2121,
    "sftp_port": 2222,
    "ftp_anonymous": "off",
    "ftp_anonymous_write_dir": "",
}


_ftp_service: Optional[server_ftp.FTPService] = None
_sftp_service: Optional[server_sftp.SFTPService] = None
_last_error: Optional[str] = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    env_path = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    base = env_path if env_path.exists() else _repo_root() / "data"
    base.mkdir(parents=True, exist_ok=True)
    module_dir = base / "file_share"
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir


def _config_path() -> Path:
    return _data_dir() / "config.json"


def _default_share_path() -> Path:
    share_dir = _data_dir() / "share"
    share_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(share_dir, 0o750)
    except OSError:
        pass
    return share_dir


def _merge_config(payload: Dict[str, object]) -> Dict[str, object]:
    config = dict(DEFAULT_CONFIG)
    config.update(payload or {})
    share_path = str(config.get("share_path") or "").strip()
    if not share_path or not Path(share_path).is_absolute():
        share_path = str(_default_share_path())
    config["share_path"] = share_path
    config["ftp_port"] = _clamp_port(config.get("ftp_port"), DEFAULT_CONFIG["ftp_port"])
    config["sftp_port"] = _clamp_port(config.get("sftp_port"), DEFAULT_CONFIG["sftp_port"])
    config["ftp_anonymous"] = _normalize_anonymous(config.get("ftp_anonymous"))
    config["ftp_bind_addresses"] = _normalize_addresses(config.get("ftp_bind_addresses"))
    config["sftp_bind_addresses"] = _normalize_addresses(config.get("sftp_bind_addresses"))
    return config


def _normalize_anonymous(value: object) -> str:
    allowed = {"off", "readonly", "readwrite"}
    if isinstance(value, str) and value in allowed:
        return value
    return "off"


def _normalize_addresses(value: object) -> List[str]:
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        values = [v.strip() for v in str(value or "").split(",") if v.strip()]
    return values or ["0.0.0.0"]


def _clamp_port(value: object, default: object) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        port = int(default)
    if port < 1 or port > 65535:
        port = int(default)
    return port


def load_config() -> Dict[str, object]:
    path = _config_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
    else:
        payload = {}
    config = _merge_config(payload if isinstance(payload, dict) else {})
    if not path.exists():
        save_config(config)
    return config


def save_config(config: Dict[str, object]) -> None:
    path = _config_path()
    path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_status() -> Dict[str, object]:
    config = load_config()
    return {
        "config": config,
        "ftp_running": _ftp_service is not None and _ftp_service.is_running,
        "sftp_running": _sftp_service is not None and _sftp_service.is_running,
        "last_error": _last_error,
    }


def apply_config(payload: Dict[str, object]) -> Dict[str, object]:
    config = _merge_config(payload)
    save_config(config)
    _restart_services(config)
    return config


def initialize() -> None:
    config = load_config()
    _restart_services(config)


def shutdown() -> None:
    _stop_services()


def _restart_services(config: Dict[str, object]) -> None:
    global _last_error
    _last_error = None
    _stop_services()
    share_path = Path(str(config["share_path"]))
    share_path.mkdir(parents=True, exist_ok=True)
    if config.get("enable_ftp"):
        try:
            _start_ftp(config)
        except Exception as exc:  # pragma: no cover - defensive guard
            _last_error = f"FTP start failed: {exc}"
    if config.get("enable_sftp_scp"):
        try:
            _start_sftp(config)
        except Exception as exc:  # pragma: no cover - defensive guard
            _last_error = f"SFTP/SCP start failed: {exc}"


def _stop_services() -> None:
    global _ftp_service, _sftp_service
    if _ftp_service is not None:
        _ftp_service.stop()
        _ftp_service = None
    if _sftp_service is not None:
        _sftp_service.stop()
        _sftp_service = None


def _start_ftp(config: Dict[str, object]) -> None:
    global _ftp_service
    _ftp_service = server_ftp.FTPService.from_config(config)
    _ftp_service.start()


def _start_sftp(config: Dict[str, object]) -> None:
    global _sftp_service
    _sftp_service = server_sftp.SFTPService.from_config(config)
    _sftp_service.start()

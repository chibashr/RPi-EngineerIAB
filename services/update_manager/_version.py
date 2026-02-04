from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from lib.module_logger import get_service_logger
from ._git import _git_safe_dir, _is_hash

logger = get_service_logger(__name__)


def _resolve_version_file(config_dir: Path, data_dir: Path) -> Path:
    config_path = config_dir / "version"
    data_path = data_dir / "version"
    if config_path.exists():
        return config_path
    if data_path.exists():
        return data_path
    return config_path


def _current_version(version_file: Path) -> str:
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except OSError:
            pass
    return os.getenv("RPI_ENGINEER_VERSION", "1.0.0")


def _local_git_hash(repo_root: Path) -> Optional[str]:
    if not (repo_root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", *_git_safe_dir(repo_root), "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if _is_hash(value) else None


def _write_version(version_file: Path, data_dir: Path, version: str) -> Path:
    """Write version to config or data dir; fallback to data dir if config is not writable."""
    text = str(version).strip()
    try:
        version_file.parent.mkdir(parents=True, exist_ok=True)
        version_file.write_text(text)
        return version_file
    except OSError:
        pass
    data_version = data_dir / "version"
    try:
        data_version.parent.mkdir(parents=True, exist_ok=True)
        data_version.write_text(text)
        logger.info("Version written to data dir (config dir not writable): %s", data_version)
        return data_version
    except OSError as e:
        raise RuntimeError(
            f"Cannot write version to {version_file} or {data_version}: {e}"
        ) from e

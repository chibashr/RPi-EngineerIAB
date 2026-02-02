"""Logging Service implementation for log viewing and export."""

from __future__ import annotations

import os
import shutil
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional


def _timestamp(ts: Optional[float] = None) -> str:
    if ts is None:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.isoformat()


def _safe_dir(primary: Path, fallback: Path) -> Path:
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class LoggingService:
    """Provide log file listings, filtered reads, and exports."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._log_dir = _safe_dir(
            Path(os.getenv("RPI_ENGINEER_LOG_DIR", "/var/log/rpi-engineer")),
            repo_root / "logs",
        )
        self._export_dir = _safe_dir(
            Path(os.getenv("RPI_ENGINEER_LOG_EXPORT_DIR", "/var/lib/rpi-engineer/exports")),
            repo_root / "data" / "exports",
        )

    def list_logs(self) -> Dict[str, List[Dict[str, object]]]:
        files = []
        if self._log_dir.exists():
            for path in sorted(self._log_dir.glob("*.log")):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                files.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "modified": _timestamp(stat.st_mtime),
                    }
                )
        return {"files": files}

    def _resolve_log_path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name:
            raise ValueError("Invalid log file name")
        if not name.endswith(".log"):
            raise ValueError("Invalid log file name")
        candidate = (self._log_dir / name).resolve()
        if not str(candidate).startswith(str(self._log_dir.resolve())):
            raise ValueError("Invalid log file name")
        return candidate

    def read_log(
        self,
        name: str,
        tail: int = 100,
        level: Optional[str] = None,
        search: Optional[str] = None,
        service: Optional[str] = None,
    ) -> Dict[str, object]:
        path = self._resolve_log_path(name)
        if not path.exists():
            raise FileNotFoundError("Log file not found")
        lines = self._tail_lines(path, tail, level=level, search=search, service=service)
        return {
            "file": name,
            "tail": tail,
            "lines": lines,
            "filters": {"level": level, "search": search, "service": service},
        }

    def export_logs(self, files: Optional[Iterable[str]] = None) -> Path:
        if files:
            selected = [self._resolve_log_path(name) for name in files if name]
        else:
            selected = list(self._log_dir.glob("*.log"))
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        export_path = self._export_dir / f"logs-{timestamp}.zip"
        with zipfile.ZipFile(export_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in selected:
                if path.exists():
                    archive.write(path, arcname=path.name)
        return export_path

    def _tail_lines(
        self,
        path: Path,
        limit: int,
        level: Optional[str] = None,
        search: Optional[str] = None,
        service: Optional[str] = None,
    ) -> List[str]:
        level_key = level.lower() if level else None
        search_key = search.lower() if search else None
        service_key = service.lower() if service else None
        buffer: Deque[str] = deque(maxlen=max(limit, 1))
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if level_key and level_key not in line.lower():
                    continue
                if service_key and service_key not in line.lower():
                    continue
                if search_key and search_key not in line.lower():
                    continue
                buffer.append(line.rstrip("\n"))
        return list(buffer)


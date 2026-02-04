"""Logging Service implementation for log viewing and export."""

from __future__ import annotations

import os
import re
import shutil
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Tuple


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

    def read_all_logs(
        self,
        tail: int = 100,
        level: Optional[str] = None,
        search: Optional[str] = None,
        service: Optional[str] = None,
    ) -> Dict[str, object]:
        """Read logs from all files, merge by timestamp, return sorted."""
        if not self._log_dir.exists():
            return {
                "file": "all",
                "tail": tail,
                "lines": [],
                "filters": {"level": level, "search": search, "service": service},
            }
        
        # Optional timestamp pattern: 2025-02-03 12:34:56,789 or 2025-02-03 12:34:56
        ts_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[,\s]\d+)?)"
        )
        
        all_lines: List[Tuple[str, str]] = []  # (timestamp, line)
        
        for path in sorted(self._log_dir.glob("*.log")):
            try:
                lines = self._tail_lines(path, tail, level=level, search=search, service=service)
                for line in lines:
                    ts_match = ts_pattern.match(line.strip())
                    ts_str = ts_match.group(1) if ts_match else "0000-00-00 00:00:00"
                    # Normalize timestamp for sorting
                    ts_str = ts_str.replace("T", " ").replace(",", ".")
                    all_lines.append((ts_str, line))
            except (OSError, ValueError):
                continue
        
        # Sort by timestamp, then return just the lines
        all_lines.sort(key=lambda x: x[0])
        merged_lines = [line for _, line in all_lines]
        
        return {
            "file": "all",
            "tail": tail,
            "lines": merged_lines,
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

    def get_recent_log_alerts(
        self, limit: int = 50
    ) -> List[Dict[str, object]]:
        """
        Read recent WARNING and ERROR lines from all log files and return
        them as alert-shaped dicts for unified alerting.
        Returns list of {severity, message, timestamp} (newest first).
        """
        alerts: List[Dict[str, object]] = []
        # Match common formats: "DATE TIME - name - LEVEL - msg" or "LEVEL - msg"
        level_pattern = re.compile(
            r"^(?P<prefix>.*?)\s+-\s+(?:ERROR|WARNING)\s+-\s+(?P<message>.+)$",
            re.IGNORECASE,
        )
        simple_level = re.compile(
            r"^(?P<prefix>.*?)\s+(?:ERROR|WARNING)\s+[:\-]?\s*(?P<message>.+)$",
            re.IGNORECASE,
        )
        # Optional leading timestamp: 2025-02-03 12:34:56,789 or 2025-02-03 12:34:56
        ts_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:,\d+)?)"
        )

        def parse_line(line: str) -> Optional[Tuple[str, str, str]]:
            line_lower = line.lower()
            if " error " in line_lower or " - error - " in line_lower:
                severity = "critical"
            elif " warning " in line_lower or " - warning - " in line_lower:
                severity = "warning"
            else:
                return None
            message = line
            for pattern in (level_pattern, simple_level):
                m = pattern.search(line)
                if m:
                    message = (m.group("message") or "").strip() or line
                    break
            ts_str = _timestamp()
            ts_match = ts_pattern.match(line.strip())
            if ts_match:
                try:
                    raw = ts_match.group(1).replace("T", " ").replace(",", ".")
                    dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
                    ts_str = dt.replace(tzinfo=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    pass
            return (severity, message, ts_str)

        if not self._log_dir.exists():
            return []
        read_limit = 300
        for path in sorted(self._log_dir.glob("*.log"), reverse=True):
            if len(alerts) >= limit:
                break
            try:
                lines = self._tail_lines(
                    path, read_limit, level=None, search=None, service=None
                )
            except (OSError, ValueError):
                continue
            for line in reversed(lines):
                if len(alerts) >= limit:
                    break
                parsed = parse_line(line)
                if parsed:
                    severity, message, ts_str = parsed
                    alerts.append(
                        {
                            "severity": severity,
                            "message": message[:500],
                            "timestamp": ts_str,
                            "source": "log",
                        }
                    )
        alerts.sort(key=lambda a: (a.get("timestamp") or ""), reverse=True)
        return alerts[:limit]


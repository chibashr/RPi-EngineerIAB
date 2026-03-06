"""Logging Service implementation for log viewing, export, and rotation daemon."""

from __future__ import annotations

import json
import os
import re
import signal
import shutil
import time
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

    def list_logs(self) -> Dict[str, object]:
        files = []
        available_services = self._discover_available_services()
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
        out: Dict[str, object] = {"files": files}
        out["available_services"] = available_services
        return out

    def _resolve_log_path(self, name: str) -> Path:
        if not name or "/" in name or "\\" in name:
            raise ValueError("Invalid log file name")
        if not name.endswith(".log"):
            raise ValueError("Invalid log file name")
        candidate = (self._log_dir / name).resolve()
        if not str(candidate).startswith(str(self._log_dir.resolve())):
            raise ValueError("Invalid log file name")
        return candidate

    def _discover_available_services(self) -> List[str]:
        """Discover service log files (exclude rotated .log.1, .log.2, etc.)."""
        if not self._log_dir.exists():
            return []
        return sorted(
            f.stem for f in self._log_dir.glob("*.log") if not f.name.endswith(".1")
        )

    def _tail_log(self, path: Path, n: int) -> List[str]:
        """Read last n lines efficiently (seek from end for large files)."""
        if not path.exists() or n <= 0:
            return []
        n = min(n, 1000)
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return []
                chunk_size = min(8192, size)
                f.seek(max(0, size - chunk_size * 4))
                data = f.read()
                lines = data.splitlines()
                return lines[-n:] if len(lines) >= n else lines
        except OSError:
            return []

    def _parse_log_line(
        self, line: str, service_name: str
    ) -> Optional[Dict[str, object]]:
        """Parse plain text or JSON log line into {timestamp, level, service, message}."""
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                ts = obj.get("timestamp") or ""
                lvl = str(obj.get("level", "INFO")).upper()
                svc = str(obj.get("service", service_name))
                msg = str(obj.get("message", line))
                return {"timestamp": ts, "level": lvl, "service": svc, "message": msg}
        except (json.JSONDecodeError, TypeError):
            pass
        plain_re = re.compile(
            r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (\w+) \[(\w+)\] (.+)$"
        )
        m = plain_re.match(line)
        if m:
            ts_raw, lvl, svc, msg = m.groups()
            try:
                dt = datetime.strptime(ts_raw[:19], "%Y-%m-%d %H:%M:%S")
                ms = int(ts_raw[20:23]) if len(ts_raw) > 19 and ts_raw[19:20] == "," else 0
                ts_iso = dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                ts_iso += f".{ms:03d}Z" if ms else "Z"
            except (ValueError, TypeError):
                ts_iso = ts_raw
            return {"timestamp": ts_iso, "level": lvl, "service": svc, "message": msg}
        return None

    def _level_rank(self, level: str) -> int:
        rank = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        return rank.get(str(level).upper(), 0)

    def _lines_to_entries(
        self,
        lines: List[str],
        default_service: Optional[str],
        min_level: Optional[str],
    ) -> List[Dict[str, object]]:
        """Parse lines into structured entries, optionally filter by min_level."""
        min_rank = self._level_rank(min_level) if min_level else 0
        entries: List[Dict[str, object]] = []
        for line in lines:
            parsed = self._parse_log_line(line, default_service or "unknown")
            if not parsed:
                continue
            if self._level_rank(parsed["level"]) < min_rank:
                continue
            entries.append(parsed)
        return entries

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
        svc_name = path.stem
        entries = self._lines_to_entries(lines, svc_name, level)
        out: Dict[str, object] = {
            "file": name,
            "tail": tail,
            "lines": lines,
            "filters": {"level": level, "search": search, "service": service},
        }
        out["entries"] = entries
        out["available_services"] = self._discover_available_services()
        return out

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
                "entries": [],
                "available_services": [],
            }
        
        # Optional timestamp pattern: 2025-02-03 12:34:56,789 or 2025-02-03 12:34:56
        ts_pattern = re.compile(
            r"^(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}(?:[,\s]\d+)?)"
        )
        
        all_lines: List[Tuple[str, str]] = []  # (timestamp, line)
        paths = sorted(self._log_dir.glob("*.log"))
        if service and service.lower() != "all":
            paths = [p for p in paths if p.stem == service]
        
        for path in paths:
            try:
                # When service=all, don't filter line content by service
                tail_service = None if (not service or str(service).lower() == "all") else service
                lines = self._tail_lines(path, tail, level=level, search=search, service=tail_service)
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
        entries = self._lines_to_entries(merged_lines, None, level)
        out: Dict[str, object] = {
            "file": "all",
            "tail": tail,
            "lines": merged_lines,
            "filters": {"level": level, "search": search, "service": service},
        }
        out["entries"] = entries
        out["available_services"] = self._discover_available_services()
        return out

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


def _run_rotation(log_dir: Path, max_size_mb: int, retain_days: int) -> None:
    """Rotate log files exceeding max_size_mb; remove rotated files older than retain_days."""
    if not log_dir.exists():
        return
    max_bytes = max_size_mb * 1024 * 1024
    cutoff = time.time() - (retain_days * 86400)
    for path in sorted(log_dir.glob("*.log")):
        try:
            if path.stat().st_size > max_bytes:
                # Rotate: .log -> .log.1, .log.1 -> .log.2, etc.
                for n in range(9, 0, -1):
                    old = log_dir / f"{path.stem}.log.{n}"
                    new = log_dir / f"{path.stem}.log.{n + 1}"
                    if old.exists():
                        if new.exists():
                            new.unlink()
                        old.rename(new)
                path.rename(log_dir / f"{path.stem}.log.1")
        except OSError:
            continue
    # Remove old rotated files
    for path in log_dir.glob("*.log.*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            continue


def _daemon_main() -> None:
    """Run logging daemon: periodic rotation and retention cleanup."""
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from lib.module_logger import get_service_logger

    logger = get_service_logger("services.logging_service.manager")
    logger.info("Logging daemon started")

    log_dir = _safe_dir(
        Path(os.getenv("RPI_ENGINEER_LOG_DIR", "/var/log/rpi-engineer")),
        repo_root / "logs",
    )
    interval = int(os.getenv("RPI_ENGINEER_LOG_ROTATE_INTERVAL", "3600"))
    max_size_mb = int(os.getenv("RPI_ENGINEER_LOG_MAX_SIZE_MB", "10"))
    retain_days = int(os.getenv("RPI_ENGINEER_LOG_RETAIN_DAYS", "7"))

    stop = False

    def _on_signal(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    while not stop:
        try:
            _run_rotation(log_dir, max_size_mb, retain_days)
        except Exception as exc:
            logger.warning("Log rotation failed: %s", exc)
        for _ in range(interval):
            if stop:
                break
            time.sleep(1)
    logger.info("Logging daemon stopped")


if __name__ == "__main__":
    _daemon_main()

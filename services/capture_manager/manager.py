"""Capture Manager implementation for packet capture lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lib.module_logger import get_service_logger
from services.network_manager import NetworkManager

logger = get_service_logger(__name__)


def _capture_dir() -> Path:
    """Persistent capture dir: RPI_ENGINEER_DATA_DIR/captures or repo/data/captures fallback."""
    base = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
    path = base / "captures"
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        path = _REPO_ROOT / "data" / "captures"
        path.mkdir(parents=True, exist_ok=True)
        return path


def _metadata_path() -> Path:
    """Path to persisted capture metadata index."""
    return _capture_dir() / "captures.json"


@dataclass
class CaptureJob:
    capture_id: str
    interface: str
    name: str
    filter: Optional[str] = None
    duration_seconds: Optional[int] = None
    max_size_mb: Optional[int] = None
    started_at: str = field(default_factory=lambda: _timestamp())
    stopped_at: Optional[str] = None
    file_path: Optional[Path] = None
    process: Optional[subprocess.Popen] = None
    packet_count: Optional[int] = None
    byte_count: Optional[int] = None


def _load_metadata() -> Dict[str, dict]:
    """Load persisted capture metadata from disk."""
    path = _metadata_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load capture metadata: %s", exc)
        return {}


def _save_metadata(metadata: Dict[str, dict]) -> None:
    """Persist capture metadata to disk."""
    path = _metadata_path()
    try:
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to save capture metadata: %s", exc)


class CaptureManager:
    """Manage tcpdump captures and analysis."""

    def __init__(self) -> None:
        self._active: Dict[str, CaptureJob] = {}
        self._completed: Dict[str, CaptureJob] = {}
        self._network_manager = NetworkManager()
        self._load_completed_from_disk()

    def list_interfaces(self) -> Dict[str, List[str]]:
        try:
            ifaces = self._network_manager.list_interfaces().get("interfaces") or []
            interfaces = [iface["id"] for iface in ifaces if isinstance(iface, dict) and iface.get("id")]
        except Exception as exc:
            logger.warning("NetworkManager list_interfaces failed: %s; using fallback", exc)
            interfaces = _fallback_interface_names()
        if not interfaces:
            interfaces = _fallback_interface_names()
        return {"interfaces": interfaces}

    def start_capture(self, payload: Dict[str, object]) -> Dict[str, object]:
        interface = payload.get("interface")
        if not interface:
            raise ValueError("interface is required")
        capture_id = str(uuid.uuid4())
        name = payload.get("name") or f"capture-{capture_id[:8]}"
        filter_expr = payload.get("filter")
        duration_seconds = payload.get("duration_seconds")
        max_size_mb = payload.get("max_size_mb")

        capture_dir = _capture_dir()
        capture_dir.mkdir(parents=True, exist_ok=True)
        file_path = capture_dir / f"{capture_id}.pcap"

        job = CaptureJob(
            capture_id=capture_id,
            interface=str(interface),
            name=str(name),
            filter=str(filter_expr) if filter_expr else None,
            duration_seconds=int(duration_seconds) if duration_seconds else None,
            max_size_mb=int(max_size_mb) if max_size_mb else None,
            file_path=file_path,
        )

        if os.getenv("RPI_ENGINEER_DRY_RUN", "0") == "1":
            self._active[capture_id] = job
            return self._job_payload(job)
        if not _which("tcpdump"):
            logger.error("tcpdump not installed")
            raise RuntimeError("tcpdump not installed")
        cmd = ["tcpdump", "-i", job.interface, "-U", "-w", str(file_path)]
        if job.max_size_mb:
            cmd += ["-C", str(job.max_size_mb), "-W", "1"]
        if job.filter:
            cmd += split_bpf_filter(job.filter)
        job.process = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self._active[capture_id] = job
        logger.info("Capture started id=%s interface=%s filter=%r", capture_id[:8], job.interface, job.filter)
        if job.duration_seconds:
            threading.Thread(
                target=self._stop_after, args=(capture_id, job.duration_seconds), daemon=True
            ).start()
        if job.max_size_mb:
            threading.Thread(
                target=self._stop_on_size, args=(capture_id, job.max_size_mb), daemon=True
            ).start()
        return self._job_payload(job)

    def list_active(self) -> Dict[str, List[Dict[str, object]]]:
        return {"captures": [self._job_payload(job) for job in self._active.values()]}

    def get_active(self, capture_id: str) -> Dict[str, object]:
        job = self._active.get(capture_id)
        if not job:
            raise KeyError("Active capture not found")
        return self._job_payload(job)

    def stop_capture(self, capture_id: str) -> Dict[str, object]:
        job = self._active.pop(capture_id, None)
        if not job:
            raise KeyError("Active capture not found")
        if job.process and job.process.poll() is None:
            job.process.terminate()
        job.stopped_at = _timestamp()
        if job.file_path and job.file_path.exists() and _which("tshark"):
            stats = _tshark_stats(job.file_path)
            job.packet_count = stats.get("packet_count", 0)
            job.byte_count = stats.get("byte_count", 0)
        self._completed[capture_id] = job
        self._persist_completed()
        packets = job.packet_count or 0
        logger.info("Capture stopped id=%s packets=%d", capture_id[:8], packets)
        return self._job_payload(job)

    def list_completed(self) -> Dict[str, List[Dict[str, object]]]:
        return {"captures": [self._job_payload(job) for job in self._completed.values()]}

    def get_completed(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id)
        if not job:
            raise KeyError("Completed capture not found")
        return self._job_payload(job)

    def delete_completed(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.pop(capture_id, None)
        if not job:
            raise KeyError("Completed capture not found")
        if job.file_path and job.file_path.exists():
            try:
                job.file_path.unlink()
            except OSError as exc:
                logger.warning("Failed to delete capture file %s: %s", job.file_path, exc)
        self._persist_completed()
        logger.info("Completed capture deleted: %s (%s)", capture_id[:8], job.name)
        return {"capture_id": capture_id, "deleted": True}

    def get_stats(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id) or self._active.get(capture_id)
        if not job or not job.file_path or not job.file_path.exists():
            raise KeyError("Capture not found")
        stats = {"packet_count": 0, "byte_count": 0}
        if _which("tshark"):
            stats = _tshark_stats(job.file_path)
        file_size = None
        try:
            file_size = job.file_path.stat().st_size
        except OSError:
            pass
        return {
            "packet_count": stats.get("packet_count", 0),
            "byte_count": stats.get("byte_count", 0),
            "file_size": file_size,
            "duration_seconds": _duration_seconds(job),
            "protocols": {},
            "start_time": job.started_at,
            "end_time": job.stopped_at,
        }

    def get_packets(self, capture_id: str) -> Dict[str, object]:
        job = self.get_job(capture_id)
        if not job or not job.file_path or not job.file_path.exists():
            raise KeyError("Capture not found")
        return {"packets": _tshark_packets(job.file_path)}

    def get_conversations(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id)
        if not job or not job.file_path:
            raise KeyError("Capture not found")
        return {"conversations": _tshark_conversations(job.file_path)}

    def get_protocols(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id)
        if not job or not job.file_path:
            raise KeyError("Capture not found")
        return {"protocols": _tshark_protocols(job.file_path)}

    def get_job(self, capture_id: str) -> Optional[CaptureJob]:
        return self._active.get(capture_id) or self._completed.get(capture_id)

    def _load_completed_from_disk(self) -> None:
        """Restore completed captures from persisted metadata."""
        meta = _load_metadata()
        capture_dir = _capture_dir()
        for cid, entry in meta.items():
            if not isinstance(entry, dict):
                continue
            file_path = capture_dir / f"{cid}.pcap"
            if not file_path.exists():
                continue
            job = CaptureJob(
                capture_id=cid,
                interface=entry.get("interface", ""),
                name=entry.get("name", cid[:8]),
                filter=entry.get("filter"),
                duration_seconds=entry.get("duration_seconds"),
                max_size_mb=entry.get("max_size_mb"),
                started_at=entry.get("started_at", _timestamp()),
                stopped_at=entry.get("stopped_at"),
                file_path=file_path,
                packet_count=entry.get("packet_count"),
                byte_count=entry.get("byte_count"),
            )
            self._completed[cid] = job

    def _persist_completed(self) -> None:
        """Write completed captures metadata to disk."""
        meta = {
            cid: {
                "capture_id": job.capture_id,
                "interface": job.interface,
                "name": job.name,
                "filter": job.filter,
                "duration_seconds": job.duration_seconds,
                "max_size_mb": job.max_size_mb,
                "started_at": job.started_at,
                "stopped_at": job.stopped_at,
                "packet_count": job.packet_count,
                "byte_count": job.byte_count,
            }
            for cid, job in self._completed.items()
        }
        _save_metadata(meta)

    def _job_payload(self, job: CaptureJob) -> Dict[str, object]:
        payload = {
            "capture_id": job.capture_id,
            "interface": job.interface,
            "name": job.name,
            "filter": job.filter,
            "duration_seconds": job.duration_seconds,
            "max_size_mb": job.max_size_mb,
            "started_at": job.started_at,
            "stopped_at": job.stopped_at,
            "file_path": str(job.file_path) if job.file_path else "",
        }
        if job.packet_count is not None:
            payload["packet_count"] = job.packet_count
        if job.byte_count is not None:
            payload["byte_count"] = job.byte_count
        if job.file_path and job.file_path.exists():
            try:
                payload["file_size"] = job.file_path.stat().st_size
            except OSError:
                pass
        return payload

    def _stop_after(self, capture_id: str, duration_seconds: int) -> None:
        time.sleep(duration_seconds)
        if capture_id in self._active:
            try:
                self.stop_capture(capture_id)
            except Exception:
                return

    def _stop_on_size(self, capture_id: str, max_size_mb: int) -> None:
        max_bytes = max_size_mb * 1024 * 1024
        while capture_id in self._active:
            job = self._active.get(capture_id)
            if not job or not job.file_path:
                return
            try:
                if job.file_path.exists() and job.file_path.stat().st_size >= max_bytes:
                    self.stop_capture(capture_id)
                    return
            except OSError:
                return
            time.sleep(1)


def _capinfos_stats(path: Path) -> Dict[str, int]:
    """Prefer capinfos for packet/byte counts; more reliable than tshark io,stat."""
    capinfos = _which("capinfos")
    if not capinfos:
        return {}
    result = subprocess.run(
        [capinfos, "-c", "-d", "-M", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    packet_count = 0
    byte_count = 0
    for line in result.stdout.splitlines():
        m = re.match(r"Number of packets:\s*(\d+)", line, re.IGNORECASE)
        if m:
            packet_count = int(m.group(1))
            continue
        m = re.match(r"Total length(?:\s+of packets)?:\s*([\d.]+)", line, re.IGNORECASE)
        if m:
            byte_count = int(float(m.group(1)))
    if packet_count or byte_count:
        return {"packet_count": packet_count, "byte_count": byte_count}
    return {}


def _tshark_stats(path: Path) -> Dict[str, int]:
    capinfos_result = _capinfos_stats(path)
    if capinfos_result and (
        capinfos_result.get("packet_count", 0) > 0 or capinfos_result.get("byte_count", 0) > 0
    ):
        return {
            "packet_count": capinfos_result.get("packet_count", 0),
            "byte_count": capinfos_result.get("byte_count", 0),
        }
    result = subprocess.run(
        ["tshark", "-r", str(path), "-q", "-z", "io,stat,0"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"packet_count": 0, "byte_count": 0}
    packet_count = 0
    byte_count = 0
    for line in result.stdout.splitlines():
        if line.strip().startswith("Interval"):
            continue
        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
            for i, p in enumerate(parts):
                if p.isdigit() and packet_count == 0 and i >= 1:
                    packet_count = int(p)
                    break
            for i, p in enumerate(parts):
                try:
                    v = int(float(p))
                    if v > byte_count and packet_count > 0:
                        byte_count = v
                except ValueError:
                    pass
            if packet_count and not byte_count and len(parts) >= 4:
                try:
                    byte_count = int(float(parts[3]))
                except ValueError:
                    pass
    return {"packet_count": packet_count, "byte_count": byte_count}


def _tshark_packets(path: Path) -> List[Dict[str, object]]:
    if not _which("tshark"):
        return []
    result = subprocess.run(
        ["tshark", "-r", str(path), "-T", "json", "-c", "100"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def _tshark_conversations(path: Path) -> List[str]:
    if not _which("tshark"):
        return []
    result = subprocess.run(
        ["tshark", "-r", str(path), "-q", "-z", "conv,ip"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _tshark_protocols(path: Path) -> Dict[str, int]:
    if not _which("tshark"):
        return {}
    result = subprocess.run(
        ["tshark", "-r", str(path), "-q", "-z", "io,phs"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}
    protocols: Dict[str, int] = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            name = name.strip()
            value = value.strip()
            if value.isdigit():
                protocols[name] = int(value)
    return protocols


def _duration_seconds(job: CaptureJob) -> int:
    if not job.stopped_at:
        return 0
    try:
        start = time.mktime(time.strptime(job.started_at, "%Y-%m-%dT%H:%M:%SZ"))
        end = time.mktime(time.strptime(job.stopped_at, "%Y-%m-%dT%H:%M:%SZ"))
        return int(end - start)
    except Exception:
        return 0


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def split_bpf_filter(filter_expr: str) -> List[str]:
    tokens = shlex.split(filter_expr)
    if any(token.startswith("-") for token in tokens):
        raise ValueError("Invalid filter expression")
    return tokens


def _which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def _fallback_interface_names() -> List[str]:
    """Fallback when NetworkManager fails: read /sys/class/net or run ip link."""
    names: List[str] = []
    net_dir = Path("/sys/class/net")
    if net_dir.exists():
        for p in net_dir.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                names.append(p.name)
    if names:
        return sorted(names)
    if _which("ip"):
        try:
            result = subprocess.run(
                ["ip", "-o", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.strip().split(":")
                    if len(parts) >= 2:
                        names.append(parts[1].strip().split("@")[0])
        except (OSError, subprocess.TimeoutExpired):
            pass
    return sorted(set(names)) if names else []

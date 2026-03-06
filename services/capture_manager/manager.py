"""Capture Manager implementation for packet capture lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
import os
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
CAPTURE_DIR = Path("/opt/rpi-engineer/data/captures")


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


class CaptureManager:
    """Manage tcpdump captures and analysis."""

    def __init__(self) -> None:
        self._active: Dict[str, CaptureJob] = {}
        self._completed: Dict[str, CaptureJob] = {}
        self._network_manager = NetworkManager()

    def list_interfaces(self) -> Dict[str, List[str]]:
        interfaces = [
            iface["id"] for iface in self._network_manager.list_interfaces()["interfaces"]
        ]
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

        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CAPTURE_DIR / f"{name}.pcap"

        job = CaptureJob(
            capture_id=capture_id,
            interface=str(interface),
            name=str(name),
            filter=str(filter_expr) if filter_expr else None,
            duration_seconds=int(duration_seconds) if duration_seconds else None,
            max_size_mb=int(max_size_mb) if max_size_mb else None,
            file_path=file_path,
        )

        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
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
        self._completed[capture_id] = job
        packets = 0
        if job.file_path and job.file_path.exists() and _which("tshark"):
            packets = _tshark_stats(job.file_path).get("packet_count", 0)
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
            job.file_path.unlink()
        logger.info("Completed capture deleted: %s (%s)", capture_id[:8], job.name)
        return {"capture_id": capture_id, "deleted": True}

    def get_stats(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id) or self._active.get(capture_id)
        if not job or not job.file_path or not job.file_path.exists():
            raise KeyError("Capture not found")
        stats = {"packet_count": 0, "byte_count": 0}
        if _which("tshark"):
            stats = _tshark_stats(job.file_path)
        return {
            "packet_count": stats.get("packet_count", 0),
            "byte_count": stats.get("byte_count", 0),
            "duration_seconds": _duration_seconds(job),
            "protocols": {},
            "start_time": job.started_at,
            "end_time": job.stopped_at,
        }

    def get_packets(self, capture_id: str) -> Dict[str, object]:
        job = self._completed.get(capture_id)
        if not job or not job.file_path:
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

    def _job_payload(self, job: CaptureJob) -> Dict[str, object]:
        return {
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


def _tshark_stats(path: Path) -> Dict[str, int]:
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
            if len(parts) >= 4 and parts[1].isdigit():
                packet_count = int(parts[1])
                try:
                    byte_count = int(float(parts[3]))
                except ValueError:
                    byte_count = 0
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

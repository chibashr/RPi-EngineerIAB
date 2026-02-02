"""System Manager implementation for system status and control."""

from __future__ import annotations

import os
import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


@dataclass
class ServiceStatus:
    name: str
    status: str


class SystemManager:
    """Collect system status, info, and basic controls."""

    def __init__(self) -> None:
        self._service_names = [
            "api_gateway",
            "system_manager",
            "network_manager",
            "serial_manager",
            "capture_manager",
            "update_manager",
            "module_manager",
            "logging_service",
            "monitor_service",
        ]

    def get_status(self) -> Dict[str, object]:
        services = {svc: self._get_service_state(svc) for svc in self._service_names}
        resources = {
            "cpu_percent": self._cpu_percent(),
            "memory_percent": self._memory_percent(),
            "disk_percent": self._disk_percent(),
            "temperature_c": self._temperature_c(),
        }
        return {
            "status": "healthy",
            "services": services,
            "resources": resources,
            "uptime_seconds": int(self._uptime_seconds()),
        }

    def get_info(self) -> Dict[str, object]:
        return {
            "hostname": socket.gethostname(),
            "version": self._version(),
            "model": self._device_model(),
            "os": self._os_string(),
        }

    def list_services(self) -> Dict[str, List[Dict[str, str]]]:
        services = [
            {"name": name, "status": self._get_service_state(name)}
            for name in self._service_names
        ]
        return {"services": services}

    def control_service(self, service: str, action: str) -> Dict[str, str]:
        if action not in {"start", "stop", "restart"}:
            raise ValueError("Unsupported action")
        if not self._systemctl_available():
            raise RuntimeError("systemctl not available")
        unit = self._normalize_unit(service)
        subprocess.run(
            ["systemctl", action, unit],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"service": service, "action": action, "status": "ok"}

    def power_action(self, action: str) -> Dict[str, object]:
        if action not in {"shutdown", "reboot"}:
            raise ValueError("Unsupported power action")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {"action": action, "scheduled": False}
        if not self._systemctl_available():
            raise RuntimeError("systemctl not available")
        cmd = "poweroff" if action == "shutdown" else "reboot"
        subprocess.Popen(["systemctl", cmd])
        return {"action": action, "scheduled": True}

    def save_settings(self, settings: Dict[str, object]) -> Dict[str, object]:
        hostname = settings.get("hostname")
        timezone = settings.get("timezone")
        preferred_mode = settings.get("preferred_mode")
        dry_run = os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1"
        result = {"applied": False}
        if hostname:
            if not dry_run:
                if _which("hostnamectl"):
                    subprocess.run(
                        ["hostnamectl", "set-hostname", str(hostname)],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif platform.system().lower() != "windows":
                    hostname_file = Path("/etc/hostname")
                    hostname_file.write_text(str(hostname).strip() + "\n")
            result["hostname"] = hostname
        if timezone:
            if not dry_run:
                if _which("timedatectl"):
                    subprocess.run(
                        ["timedatectl", "set-timezone", str(timezone)],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif platform.system().lower() != "windows":
                    timezone_link = Path("/etc/localtime")
                    zoneinfo_path = Path(f"/usr/share/zoneinfo/{timezone}")
                    if zoneinfo_path.exists():
                        if timezone_link.exists() or timezone_link.is_symlink():
                            timezone_link.unlink()
                        timezone_link.symlink_to(zoneinfo_path)
            result["timezone"] = timezone
        if preferred_mode:
            result["preferred_mode"] = preferred_mode
        result["applied"] = not dry_run
        return result

    def _systemctl_available(self) -> bool:
        return platform.system().lower() != "windows" and _which("systemctl") is not None

    def _normalize_unit(self, service: str) -> str:
        return service if service.endswith(".service") else f"{service}.service"

    def _get_service_state(self, service: str) -> str:
        if not self._systemctl_available():
            return "unknown"
        unit = self._normalize_unit(service)
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return "running"
        if result.stdout.strip() == "inactive":
            return "stopped"
        return "unknown"

    def _cpu_percent(self) -> float:
        if psutil:
            return float(psutil.cpu_percent(interval=0.1))
        return 0.0

    def _memory_percent(self) -> float:
        if psutil:
            return float(psutil.virtual_memory().percent)
        return 0.0

    def _disk_percent(self) -> float:
        if psutil:
            return float(psutil.disk_usage("/").percent)
        return 0.0

    def _temperature_c(self) -> Optional[float]:
        if platform.system().lower() == "windows":
            return None
        thermal_root = Path("/sys/class/thermal")
        if not thermal_root.exists():
            return None
        for zone in thermal_root.glob("thermal_zone*/temp"):
            try:
                raw = zone.read_text().strip()
                if raw:
                    value = float(raw)
                    return value / 1000.0 if value > 1000 else value
            except OSError:
                continue
        return None

    def _uptime_seconds(self) -> float:
        if psutil:
            return time.time() - psutil.boot_time()
        uptime_path = Path("/proc/uptime")
        if uptime_path.exists():
            try:
                raw = uptime_path.read_text().split()[0]
                return float(raw)
            except (OSError, ValueError, IndexError):
                return 0.0
        return 0.0

    def _device_model(self) -> str:
        model_path = Path("/proc/device-tree/model")
        if model_path.exists():
            try:
                return model_path.read_text().strip("\x00").strip()
            except OSError:
                pass
        return platform.machine()

    def _os_string(self) -> str:
        return f"{platform.system()} {platform.release()}"

    def _version(self) -> str:
        return os.getenv("RPI_ENGINEER_VERSION", "1.0.0")


def _which(binary: str) -> Optional[str]:
    for path in os.getenv("PATH", "").split(os.pathsep):
        candidate = Path(path) / binary
        if candidate.exists():
            return str(candidate)
    return None

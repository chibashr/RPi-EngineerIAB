"""System Manager implementation for system status and control."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import os
import platform
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from lib.module_logger import get_service_logger

logger = get_service_logger(__name__)


@dataclass
class ServiceStatus:
    name: str
    status: str


# Service definitions: logical name, systemd unit (no .service suffix), category.
# Core = app services from bin/install.sh configure_services(); system = nginx, hotspot, etc.;
# optional = remote access tools that may not be installed.
SERVICE_DEFINITIONS = [
    # Core app services (must match bin/install.sh configure_services())
    ("api_gateway", "rpi-engineer-api", "core"),
    ("system_manager", "rpi-engineer-system", "core"),
    ("network_manager", "rpi-engineer-network", "core"),
    ("serial_manager", "rpi-engineer-serial", "core"),
    ("capture_manager", "rpi-engineer-capture", "core"),
    ("update_manager", "rpi-engineer-update", "core"),
    ("logging_service", "rpi-engineer-logging", "core"),
    ("monitor_service", "rpi-engineer-monitor", "core"),
    ("rpi_engineer_master", "rpi-engineer", "core"),
    # System services the app and modules rely on
    ("nginx", "nginx", "system"),
    ("wlan0_setup", "rpi-engineer-wlan0", "system"),
    ("hostapd", "hostapd", "system"),
    ("dnsmasq", "dnsmasq", "system"),
    # Optional (remote access; may not be installed)
    ("anydesk", "anydesk", "optional"),
    ("teamviewer", "teamviewerd", "optional"),
    ("vnc", "vncserver@1", "optional"),
]

# Logical name -> systemd unit, for control and state lookup.
SERVICE_UNIT_MAP = {name: unit for name, unit, _ in SERVICE_DEFINITIONS}


def _category_for_service(name: str) -> str:
    """Return category for a logical service name."""
    for n, _, cat in SERVICE_DEFINITIONS:
        if n == name:
            return cat
    return "core"


class SystemManager:
    """Collect system status, info, and basic controls."""

    def __init__(self) -> None:
        self._service_names = list(SERVICE_UNIT_MAP.keys())
        if psutil:
            psutil.cpu_percent()  # Warm up baseline for interval=None calls

    def get_status(self) -> Dict[str, object]:
        services = self._get_all_service_states()
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
        states = self._get_all_service_states()
        services = [
            {
                "name": name,
                "status": states.get(name, "unknown"),
                "category": _category_for_service(name),
            }
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
        logger.info("Service action service=%s action=%s", service, action)
        return {"service": service, "action": action, "status": "ok"}

    def control_services_bulk(
        self, services: List[str], action: str
    ) -> List[Dict[str, object]]:
        """Run start/stop/restart on multiple services; returns one result per service."""
        if action not in {"start", "stop", "restart"}:
            raise ValueError("Unsupported action")
        results: List[Dict[str, object]] = []
        for service in services:
            try:
                result = self.control_service(service, action)
                results.append({**result, "error": None})
            except (ValueError, RuntimeError) as exc:
                results.append(
                    {
                        "service": service,
                        "action": action,
                        "status": "error",
                        "error": str(exc),
                    }
                )
        return results

    def power_action(self, action: str) -> Dict[str, object]:
        if action not in {"shutdown", "reboot"}:
            raise ValueError("Unsupported power action")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {"action": action, "scheduled": False}
        if not self._systemctl_available():
            raise RuntimeError("systemctl not available")
        cmd = "poweroff" if action == "shutdown" else "reboot"
        logger.warning("Power command issued action=%s", action)
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
        """Return systemd unit name (with .service). Resolves logical name to install unit."""
        base = SERVICE_UNIT_MAP.get(service, service)
        return base if base.endswith(".service") else f"{base}.service"

    def _get_service_state(self, service: str) -> str:
        if not self._systemctl_available():
            return "unknown"
        unit = self._normalize_unit(service)
        # Use show ActiveState for reliable, machine-parseable state (avoids
        # is-active exit-code quirks and "unknown" on some systems when inactive).
        result = subprocess.run(
            ["systemctl", "show", "--property=ActiveState", "--value", unit],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = (result.stdout or "").strip().lower()
        return self._parse_active_state(out)

    def _get_all_service_states(self) -> Dict[str, str]:
        """Get states of all services with a single systemctl call."""
        if not self._systemctl_available():
            return {svc: "unknown" for svc in self._service_names}
        units = [self._normalize_unit(svc) for svc in self._service_names]
        try:
            result = subprocess.run(
                ["systemctl", "show", "--property=ActiveState", "--value"] + units,
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = (result.stdout or "").strip().splitlines()
            states = {}
            for i, svc in enumerate(self._service_names):
                if i < len(lines):
                    states[svc] = self._parse_active_state(lines[i].strip().lower())
                else:
                    states[svc] = "unknown"
            return states
        except (subprocess.TimeoutExpired, OSError):
            return {svc: "unknown" for svc in self._service_names}

    def _parse_active_state(self, state: str) -> str:
        """Convert systemctl ActiveState to friendly status string."""
        if state == "active":
            return "running"
        if state == "inactive":
            return "stopped"
        if state == "failed":
            return "failed"
        if state == "activating":
            return "starting"
        if state == "deactivating":
            return "stopping"
        return "unknown"

    def _cpu_percent(self) -> float:
        if psutil:
            return float(psutil.cpu_percent(interval=None))
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

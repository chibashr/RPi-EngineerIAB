"""Remote access status and info collection."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.network_manager import NetworkManager

logger = logging.getLogger(__name__)

REMOTE_ACCESS_CONFIG_DIR = Path(
    os.getenv("RPI_ENGINEER_CONFIG_DIR", "/etc/rpi-engineer")
)
REMOTE_ACCESS_CONFIG_FILE = REMOTE_ACCESS_CONFIG_DIR / "remote_access.conf"


class RemoteAccessManager:
    """Collect remote access tool status and connection IDs."""

    def __init__(self) -> None:
        self._network_manager = NetworkManager()

    def get_status(self) -> Dict[str, List[Dict[str, object]]]:
        tools = []
        for tool in ("anydesk", "teamviewer", "vnc", "rpi_connect"):
            tools.append(self._tool_status(tool))
        return {"tools": tools}

    def get_info(self) -> Dict[str, Dict[str, str]]:
        ids = {
            "anydesk": self._anydesk_id() or "",
            "teamviewer": self._teamviewer_id() or "",
            "vnc": self._vnc_connection_id() or "",
            "rpi_connect": self._rpi_connect_id() or "",
        }
        status = {
            "anydesk": "running" if self._process_running("anydesk") else "stopped",
            "teamviewer": "running" if self._process_running("teamviewerd") else "stopped",
            "vnc": "running" if self._process_running("x11vnc") else "stopped",
            "rpi_connect": "running" if self._rpi_connect_running() else "stopped",
        }
        return {"connection_ids": ids, "status": status}

    def _tool_status(self, tool: str) -> Dict[str, object]:
        connection_id = ""
        ready = False
        status = "stopped"
        if tool == "anydesk":
            connection_id = self._anydesk_id() or ""
            status = "running" if self._process_running("anydesk") else "stopped"
            ready = bool(connection_id)
        elif tool == "teamviewer":
            connection_id = self._teamviewer_id() or ""
            status = "running" if self._process_running("teamviewerd") else "stopped"
            ready = bool(connection_id)
        elif tool == "vnc":
            connection_id = self._vnc_connection_id() or ""
            status = "running" if self._process_running("x11vnc") else "stopped"
            ready = bool(connection_id)
        elif tool == "rpi_connect":
            connection_id = self._rpi_connect_id() or ""
            status = "running" if self._rpi_connect_running() else "stopped"
            ready = bool(connection_id)
        return {
            "name": tool,
            "status": status,
            "connection_id": connection_id,
            "ready": ready,
        }

    def _get_remote_access_config(self) -> Dict[str, Any]:
        """Read remote_access.conf; return parsed JSON or empty dict."""
        if not REMOTE_ACCESS_CONFIG_FILE.is_file():
            return {}
        try:
            with open(REMOTE_ACCESS_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Could not read remote_access config: %s", e)
            return {}

    def _anydesk_id(self) -> Optional[str]:
        # Prefer live CLI output; fall back to ID stored at install time
        if shutil.which("anydesk"):
            result = subprocess.run(
                ["anydesk", "--get-id"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                formatted = _format_id(result.stdout.strip())
                if formatted:
                    return formatted
        config = self._get_remote_access_config()
        raw = config.get("anydesk", {}).get("id") or ""
        if not raw:
            return None
        return _format_id(str(raw).strip()) or None

    def _teamviewer_id(self) -> Optional[str]:
        # Prefer live CLI output; fall back to ID stored at install time
        if shutil.which("teamviewer"):
            result = subprocess.run(
                ["teamviewer", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout:
                match = re.search(r"TeamViewer ID:\s*(\d+)", result.stdout)
                if match:
                    return _format_id(match.group(1))
        config = self._get_remote_access_config()
        raw = config.get("teamviewer", {}).get("id") or ""
        if not raw:
            return None
        return _format_id(str(raw).strip()) or None

    def _vnc_connection_id(self) -> Optional[str]:
        ip = self._primary_ip()
        if not ip:
            return None
        return f"{ip}:5901"

    def _rpi_connect_id(self) -> Optional[str]:
        """Raspberry Pi Connect: no numeric ID; return access URL."""
        if not self._rpi_connect_running():
            return None
        return "connect.raspberrypi.com"

    def _rpi_connect_running(self) -> bool:
        """Check if rpi-connect or rpi-connect-lite is running."""
        if os.name == "nt":
            return False
        # rpi-connect runs as user service; check for rpi-connectd or rpi-connect
        for proc in ("rpi-connectd", "rpi-connect"):
            if self._process_running(proc):
                return True
        # Fallback: check if rpi-connect command exists and status indicates signed in
        if shutil.which("rpi-connect"):
            result = subprocess.run(
                ["rpi-connect", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "Signed in: yes" in result.stdout:
                return True
        return False

    def _primary_ip(self) -> Optional[str]:
        default_iface = self._network_manager._default_route_interface()
        if default_iface:
            try:
                data = self._network_manager.get_interface(default_iface)
                ip_address = data.get("ip_address")
                if isinstance(ip_address, str) and ip_address:
                    return ip_address
            except Exception as exc:
                logger.debug(
                    "Failed to load interface data for %s: %s", default_iface, exc
                )
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except OSError:
            return None

    def _process_running(self, process: str) -> bool:
        if os.name == "nt":
            return False
        if shutil.which("pgrep"):
            result = subprocess.run(
                ["pgrep", "-x", process],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        if shutil.which("systemctl"):
            result = subprocess.run(
                ["systemctl", "is-active", f"{process}.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return result.returncode == 0
        return False


def _format_id(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return " ".join([digits[i : i + 3] for i in range(0, len(digits), 3)])

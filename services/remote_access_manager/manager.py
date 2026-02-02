"""Remote access status and info collection."""

from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import subprocess
from typing import Dict, List, Optional

from services.network_manager import NetworkManager

logger = logging.getLogger(__name__)


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
            "teamviewer": "running" if self._process_running("teamviewer") else "stopped",
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
            status = "running" if self._process_running("teamviewer") else "stopped"
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

    def _anydesk_id(self) -> Optional[str]:
        if not shutil.which("anydesk"):
            return None
        result = subprocess.run(
            ["anydesk", "--get-id"], capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        return _format_id(result.stdout.strip())

    def _teamviewer_id(self) -> Optional[str]:
        if not shutil.which("teamviewer"):
            return None
        result = subprocess.run(
            ["teamviewer", "info"], capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        match = re.search(r"TeamViewer ID:\s*(\d+)", result.stdout)
        if not match:
            return None
        return _format_id(match.group(1))

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

"""Remote access status and info collection."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.module_logger import get_service_logger
from services.network_manager import NetworkManager

logger = get_service_logger(__name__)

REMOTE_ACCESS_CONFIG_DIR = Path(
    os.getenv("RPI_ENGINEER_CONFIG_DIR", "/etc/rpi-engineer")
)
REMOTE_ACCESS_CONFIG_FILE = REMOTE_ACCESS_CONFIG_DIR / "remote_access.conf"
# Native config paths for ID fallback when app config is missing/unreadable
ANYDESK_SERVICE_CONF = Path("/etc/anydesk/service.conf")
TEAMVIEWER_GLOBAL_CONF = Path("/opt/teamviewer/config/global.conf")
TEAMVIEWER_ETC_CONF = Path("/etc/teamviewer/global.conf")  # Debian/TeamViewer host package
TEAMVIEWER_LOG_DIR = Path("/var/log/teamviewer")


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
        password = ""
        if tool == "anydesk":
            connection_id = self._anydesk_id() or ""
            status = "running" if self._process_running("anydesk") else "stopped"
            ready = bool(connection_id)
            config = self._get_remote_access_config()
            password = (config.get("anydesk") or {}).get("password") or ""
        elif tool == "teamviewer":
            connection_id = self._teamviewer_id() or ""
            status = "running" if self._process_running("teamviewerd") else "stopped"
            ready = bool(connection_id)
            config = self._get_remote_access_config()
            password = (config.get("teamviewer") or {}).get("password") or ""
        elif tool == "vnc":
            connection_id = self._vnc_connection_id() or ""
            status = "running" if self._process_running("x11vnc") else "stopped"
            ready = bool(connection_id)
        elif tool == "rpi_connect":
            connection_id = self._rpi_connect_id() or ""
            status = "running" if self._rpi_connect_running() else "stopped"
            ready = bool(connection_id)
        out: Dict[str, object] = {
            "name": tool,
            "status": status,
            "connection_id": connection_id,
            "ready": ready,
        }
        if tool in ("anydesk", "teamviewer") and isinstance(password, str):
            out["password"] = password
        return out

    def _get_remote_access_config(self) -> Dict[str, Any]:
        """Read remote_access.conf; return parsed JSON or empty dict.
        Tries direct read first; on permission error, tries sudo read-remote-config.sh.
        """
        try:
            if REMOTE_ACCESS_CONFIG_FILE.is_file():
                with open(REMOTE_ACCESS_CONFIG_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except OSError as e:
            if getattr(e, "errno", None) != 13:  # EACCES
                logger.debug("Could not read remote_access config: %s", e)
                return {}
            # Permission denied: try sudo helper so dashboard can show passwords
            config = self._read_remote_config_via_sudo()
            if config is not None:
                return config
            logger.debug("Could not read remote_access config (permission denied): %s", e)
        except json.JSONDecodeError as e:
            logger.debug("Could not parse remote_access config: %s", e)
        return {}

    def _read_remote_config_via_sudo(self) -> Optional[Dict[str, Any]]:
        """Read remote_access.conf via sudo read-remote-config.sh. Returns None on failure."""
        root = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        script = root / "bin" / "read-remote-config.sh"
        if not script.is_file():
            return None
        try:
            result = subprocess.run(
                ["sudo", str(script)],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "RPI_ENGINEER_CONFIG_DIR": str(REMOTE_ACCESS_CONFIG_FILE.parent)},
                check=False,
            )
            if result.returncode != 0 or not result.stdout:
                return None
            return json.loads(result.stdout)
        except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
            return None

    def _anydesk_id_from_native_config(self) -> Optional[str]:
        """Read AnyDesk ID from /etc/anydesk/service.conf when app config is unavailable."""
        if not ANYDESK_SERVICE_CONF.is_file():
            return None
        try:
            text = ANYDESK_SERVICE_CONF.read_text(encoding="utf-8", errors="replace")
            # Common key: ad.anynet.id = 123456789 or similar
            for line in text.splitlines():
                if "id" in line.lower() and "=" in line:
                    match = re.search(r"=\s*(\d{9,10})\s*$", line.strip())
                    if match:
                        return _format_id(match.group(1))
            # Fallback: any 9–10 digit number in file
            match = re.search(r"\b(\d{9,10})\b", text)
            if match:
                return _format_id(match.group(1))
        except OSError as e:
            logger.debug("Could not read AnyDesk service.conf: %s", e)
        return None

    def _teamviewer_id_from_native_config(self) -> Optional[str]:
        """Read TeamViewer ID from config or logs when app config is unavailable."""
        for conf_path in (TEAMVIEWER_GLOBAL_CONF, TEAMVIEWER_ETC_CONF):
            if conf_path.is_file():
                try:
                    text = conf_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    match = re.search(r"ClientID\s*=\s*(\d+)", text, re.IGNORECASE)
                    if match:
                        return _format_id(match.group(1))
                except OSError as e:
                    logger.debug("Could not read TeamViewer config %s: %s", conf_path, e)
        if TEAMVIEWER_LOG_DIR.is_dir():
            try:
                for log in sorted(TEAMVIEWER_LOG_DIR.glob("*.log"), reverse=True):
                    try:
                        text = log.read_text(encoding="utf-8", errors="replace")
                        match = re.search(r"id[=\s]+(\d{9,10})\b", text, re.IGNORECASE)
                        if match:
                            return _format_id(match.group(1))
                    except OSError:
                        continue
            except OSError as e:
                logger.debug("Could not read TeamViewer log dir: %s", e)
        return None

    def _anydesk_id(self) -> Optional[str]:
        # 1) Live CLI 2) App config (remote_access.conf) 3) AnyDesk native config
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
        if raw:
            return _format_id(str(raw).strip()) or None
        return self._anydesk_id_from_native_config()

    def _teamviewer_id(self) -> Optional[str]:
        # 1) Live CLI 2) App config (remote_access.conf) 3) TeamViewer config/logs
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
        if raw:
            return _format_id(str(raw).strip()) or None
        return self._teamviewer_id_from_native_config()

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

    def set_password(self, tool: str, password: str) -> Optional[str]:
        """Set unattended password for anydesk or teamviewer. Returns None on success, error message on failure."""
        if tool not in ("anydesk", "teamviewer"):
            return f"Unsupported tool: {tool}"
        if not password:
            return "Password is required"
        root = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        script = root / "bin" / "set-remote-password.sh"
        if not script.is_file():
            return "Password reset script not found"
        data_dir = Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer"))
        data_dir.mkdir(parents=True, exist_ok=True)
        pw_file = None
        try:
            fd, pw_file = tempfile.mkstemp(
                prefix=".remote-pw-", suffix=".tmp", dir=str(data_dir)
            )
            try:
                os.write(fd, password.encode("utf-8"))
            finally:
                os.close(fd)
            os.chmod(pw_file, 0o600)
            result = subprocess.run(
                ["sudo", str(script), "--password-file", pw_file, tool],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace").strip()
                if "sudo" in err.lower() and ("terminal" in err.lower() or "password is required" in err.lower()):
                    script_path = str(script)
                    return (
                        "Password reset requires passwordless sudo for the script. "
                        f"On the device, run the installer again, or create /etc/sudoers.d/rpi-engineer-set-remote-password with: "
                        f"rpi-engineer ALL=(root) NOPASSWD: {script_path}"
                    )
                return err or "Failed to set password"
            return None
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning("set_password failed for %s: %s", tool, e)
            return str(e)
        finally:
            if pw_file and os.path.exists(pw_file):
                try:
                    os.unlink(pw_file)
                except OSError:
                    pass


def _format_id(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return " ".join([digits[i : i + 3] for i in range(0, len(digits), 3)])

"""Network Manager implementation for interface and routing operations."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
import os
import platform
import shutil
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

from lib.module_logger import get_service_logger

logger = get_service_logger(__name__)
PROFILE_DIR = Path("/etc/rpi-engineer/network_profiles")
CONFIG_DIR = Path("/etc/rpi-engineer/network_configs")
HOTSPOT_SECRET_PATH = Path("/etc/rpi-engineer/hotspot.secret")
HOTSPOT_SHARE_CONFIG = CONFIG_DIR / "hotspot_share.json"


@dataclass
class NetworkRoute:
    destination: str
    gateway: str
    interface: Optional[str] = None


class NetworkManager:
    """Manage network interfaces, routing, and profiles."""

    def list_interfaces(self) -> Dict[str, List[Dict[str, object]]]:
        interfaces = [self._build_interface(iface) for iface in self._interface_names()]
        return {"interfaces": interfaces}

    def get_interface(self, interface_id: str) -> Dict[str, object]:
        if interface_id not in self._interface_names():
            raise KeyError("Interface not found")
        return self._build_interface(interface_id)

    def update_interface(self, interface_id: str, config: Dict[str, object]) -> Dict[str, object]:
        if interface_id not in self._interface_names():
            raise KeyError("Interface not found")
        mode = config.get("mode")
        if mode not in {"dhcp", "static"}:
            raise ValueError("Mode must be dhcp or static")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            self._save_interface_config(interface_id, config)
            return {"interface": interface_id, "mode": mode, "applied": False}
        try:
            if mode == "dhcp":
                self._apply_dhcp(interface_id)
            else:
                self._apply_static(interface_id, config)
            self.ensure_wan_priority()
            logger.info("Interface state change iface=%s state=%s", interface_id, mode)
        except Exception as exc:
            logger.warning("Interface config failed iface=%s error=%s", interface_id, exc)
            raise
        return {"interface": interface_id, "mode": mode, "applied": True}

    def list_routes(self) -> Dict[str, List[Dict[str, str]]]:
        return {"routes": [route.__dict__ for route in self._routes()]}

    def list_current_routes(self) -> Dict[str, List[Dict[str, object]]]:
        return {"routes": self._current_routes()}

    def add_route(self, payload: Dict[str, object]) -> Dict[str, object]:
        destination = payload.get("destination")
        gateway = payload.get("gateway")
        interface = payload.get("interface")
        if not destination or not gateway:
            raise ValueError("destination and gateway are required")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            self._save_route(NetworkRoute(destination, gateway, interface))
            return {"destination": destination, "gateway": gateway, "interface": interface}
        cmd = ["ip", "route", "add", str(destination), "via", str(gateway)]
        if interface:
            cmd += ["dev", str(interface)]
        subprocess.run(cmd, check=True)
        return {"destination": destination, "gateway": gateway, "interface": interface}

    def list_profiles(self) -> Dict[str, List[Dict[str, object]]]:
        profiles = []
        for path in sorted(PROFILE_DIR.glob("*.json")):
            try:
                payload = json.loads(path.read_text())
                profiles.append(
                    {
                        "name": payload.get("name", path.stem),
                        "description": payload.get("description", ""),
                        "saved_at": payload.get("saved_at"),
                        "interfaces": payload.get("interfaces", []),
                        "routes": payload.get("routes", []),
                    }
                )
            except (OSError, json.JSONDecodeError):
                continue
        return {"profiles": profiles}

    def save_profile(self, payload: Dict[str, object]) -> Dict[str, object]:
        name = payload.get("name")
        if not name:
            raise ValueError("Profile name is required")
        description = payload.get("description", "")
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "name": name,
            "description": description,
            "saved_at": _timestamp(),
            "interfaces": self.list_interfaces()["interfaces"],
            "routes": self.list_routes()["routes"],
        }
        path = PROFILE_DIR / f"{name}.json"
        path.write_text(json.dumps(data, indent=2))
        logger.info("Network profile saved: %s", name)
        return {"name": name, "description": description}

    def load_profile(self, name: str) -> Dict[str, object]:
        path = self._find_profile_by_name(name)
        if not path or not path.exists():
            raise KeyError("Profile not found")
        payload = json.loads(path.read_text())
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {"name": name, "applied": False}
        for iface in payload.get("interfaces", []):
            iface_id = iface.get("id")
            config = iface.get("config")
            if iface_id and config:
                self.update_interface(iface_id, config)
        logger.info("Profile loaded name=%s", name)
        return {"name": name, "applied": True}

    def _find_profile_by_name(self, name: str) -> Optional[Path]:
        """Find profile file by name (matches payload name or path stem)."""
        for path in PROFILE_DIR.glob("*.json"):
            try:
                payload = json.loads(path.read_text())
                if payload.get("name") == name:
                    return path
                if path.stem == name:
                    return path
            except (OSError, json.JSONDecodeError):
                continue
        return None

    def delete_profile(self, name: str) -> Dict[str, object]:
        path = self._find_profile_by_name(name)
        if not path:
            raise KeyError("Profile not found")
        path.unlink()
        logger.info("Network profile deleted: %s", name)
        return {"name": name, "deleted": True}

    def update_profile(self, name: str, payload: Dict[str, object]) -> Dict[str, object]:
        path = self._find_profile_by_name(name)
        if not path:
            raise KeyError("Profile not found")
        data = json.loads(path.read_text())
        new_name = payload.get("name")
        new_description = payload.get("description")
        if new_name is not None and str(new_name).strip():
            data["name"] = str(new_name).strip()
        if new_description is not None:
            data["description"] = str(new_description)
        data["saved_at"] = _timestamp()
        final_name = data["name"]
        new_path = PROFILE_DIR / f"{final_name}.json"
        if new_path.resolve() != path.resolve():
            new_path.write_text(json.dumps(data, indent=2))
            path.unlink()
        else:
            path.write_text(json.dumps(data, indent=2))
        return {"name": final_name, "description": data.get("description", "")}

    def get_status(self) -> Dict[str, object]:
        wan_interface = self._default_route_interface()
        wan_status = "connected" if self._check_connectivity() else "disconnected"
        hotspot_status = "active" if self._hotspot_active() else "inactive"
        hotspot_config = self._get_hotspot_config() or {}
        return {
            "wan_interface": wan_interface or "",
            "wan_status": wan_status,
            "hotspot_status": hotspot_status,
            "ssid": hotspot_config.get("ssid", ""),
            "channel": hotspot_config.get("channel", ""),
            "last_test": _timestamp(),
            "clients": self._hotspot_clients(),
        }

    def reset_network(self, preserve_hotspot: bool = False) -> Dict[str, object]:
        dry_run = os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1"
        if dry_run:
            return {"reset": True, "preserve_hotspot": preserve_hotspot, "applied": False}
        if platform.system().lower() == "windows":
            raise RuntimeError("Network reset not supported on Windows")
        hotspot_config = None
        if preserve_hotspot:
            hotspot_config = self._get_hotspot_config()
        for iface in self._interface_names():
            if preserve_hotspot and iface.startswith("wlan"):
                continue
            try:
                subprocess.run(["ip", "link", "set", iface, "down"], check=False)
                subprocess.run(["ip", "addr", "flush", "dev", iface], check=False)
            except Exception:
                pass
        if preserve_hotspot and hotspot_config:
            self._restore_hotspot_config(hotspot_config)
        return {"reset": True, "preserve_hotspot": preserve_hotspot, "applied": True}

    def create_vlan(self, payload: Dict[str, object]) -> Dict[str, object]:
        parent = payload.get("parent")
        vlan_id = payload.get("vlan_id")
        name = payload.get("name")
        if not parent or vlan_id is None:
            raise ValueError("parent and vlan_id are required")
        if not isinstance(vlan_id, int) or vlan_id < 1 or vlan_id > 4094:
            raise ValueError("vlan_id must be between 1 and 4094")
        vlan_name = name or f"{parent}.{vlan_id}"
        dry_run = os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1"
        if dry_run:
            return {"parent": parent, "vlan_id": vlan_id, "name": vlan_name, "applied": False}
        if platform.system().lower() == "windows":
            raise RuntimeError("VLAN creation not supported on Windows")
        if not _which("ip"):
            raise RuntimeError("ip command not available")
        if parent not in self._interface_names():
            raise ValueError("Parent interface not found")
        subprocess.run(
            ["ip", "link", "add", "link", parent, "name", vlan_name, "type", "vlan", "id", str(vlan_id)],
            check=True,
        )
        subprocess.run(["ip", "link", "set", vlan_name, "up"], check=True)
        logger.info("VLAN created: %s on %s (id=%s)", vlan_name, parent, vlan_id)
        return {"parent": parent, "vlan_id": vlan_id, "name": vlan_name, "applied": True}

    def configure_hotspot(self, payload: Dict[str, object]) -> Dict[str, object]:
        ssid = payload.get("ssid")
        password = payload.get("password")
        channel = payload.get("channel", 6)
        if not ssid:
            raise ValueError("SSID is required")
        dry_run = os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1"
        if dry_run:
            return {"ssid": ssid, "channel": channel, "applied": False}
        if platform.system().lower() == "windows":
            raise RuntimeError("Hotspot configuration not supported on Windows")
        if not _which("systemctl"):
            raise RuntimeError("systemctl not available")
        hostapd_config = Path("/etc/hostapd/hostapd.conf")
        hostapd_config.parent.mkdir(parents=True, exist_ok=True)
        config_content = f"""interface=wlan0
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
wpa=2
wpa_passphrase={password or ""}
wpa_key_mgmt=WPA-PSK
"""
        hostapd_config.write_text(config_content)
        # Persist credentials so they survive reboot (applied by setup-wlan0-hotspot.sh at boot)
        HOTSPOT_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
        HOTSPOT_SECRET_PATH.write_text(f"{ssid}\n{password or ''}\n")
        try:
            os.chmod(HOTSPOT_SECRET_PATH, 0o600)
        except OSError:
            pass
        subprocess.run(["systemctl", "restart", "hostapd"], check=False)
        logger.info("Hotspot started interface=wlan0 ssid=%s", ssid)
        return {"ssid": ssid, "channel": channel, "applied": True}

    def _interface_names(self) -> List[str]:
        if psutil:
            return list(psutil.net_if_addrs().keys())
        if _which("ip"):
            try:
                data = _run_ip_json(["addr"])
                return [entry.get("ifname") for entry in data if entry.get("ifname")]
            except (OSError, json.JSONDecodeError):
                pass
        return []

    def _build_interface(self, name: str) -> Dict[str, object]:
        addrs = self._interface_addrs(name)
        stats = self._interface_stats(name)
        ip_address = addrs.get("ip_address")
        gateway, metric = self._gateway_for(name)
        iface_type = self._interface_type(name)
        out = {
            "id": name,
            "name": name,
            "friendly_name": self._friendly_name(name),
            "type": iface_type,
            "status": "up" if stats.get("isup") else "down",
            "ip_address": ip_address,
            "netmask": addrs.get("netmask"),
            "gateway": gateway,
            "metric": metric,
            "role": self._role_for(name, iface_type),
            "mac_address": addrs.get("mac_address"),
            "mtu": stats.get("mtu"),
            "speed_mbps": stats.get("speed"),
            "driver": self._driver_for(name),
        }
        if iface_type == "wifi":
            ssid, password = self._get_hotspot_credentials()
            out["ssid"] = ssid
            out["password"] = password
        out["share_with_hotspot"] = name in self._get_share_interfaces()
        return out

    def _interface_addrs(self, name: str) -> Dict[str, Optional[str]]:
        if psutil:
            ip_address = None
            mac_address = None
            netmask = None
            af_link = getattr(psutil, "AF_LINK", None)
            for addr in psutil.net_if_addrs().get(name, []):
                if addr.family == socket.AF_INET:
                    ip_address = addr.address
                    netmask = addr.netmask
                if af_link and addr.family == af_link:
                    mac_address = addr.address
            return {"ip_address": ip_address, "mac_address": mac_address, "netmask": netmask}
        if _which("ip"):
            try:
                data = _run_ip_json(["addr", "show", "dev", name])
                if data:
                    addr_info = data[0].get("addr_info", [])
                    for entry in addr_info:
                        if entry.get("family") == "inet":
                            ip_address = entry.get("local")
                            prefix = entry.get("prefixlen")
                            netmask = _cidr_to_netmask(prefix) if prefix is not None else None
                            return {
                                "ip_address": ip_address,
                                "mac_address": None,
                                "netmask": netmask,
                            }
            except (OSError, json.JSONDecodeError):
                pass
        return {"ip_address": None, "mac_address": None, "netmask": None}

    def _interface_stats(self, name: str) -> Dict[str, Optional[object]]:
        if psutil:
            stats = psutil.net_if_stats().get(name)
            if stats:
                return {"isup": stats.isup, "mtu": stats.mtu, "speed": stats.speed}
        return {"isup": False, "mtu": None, "speed": None}

    def _gateway_for(self, name: str) -> Tuple[Optional[str], Optional[int]]:
        if not _which("ip"):
            return None, None
        result = subprocess.run(
            ["ip", "route", "show", "default", "dev", name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None, None
        parts = result.stdout.strip().split()
        gateway = None
        metric = None
        if "via" in parts:
            idx = parts.index("via")
            if idx + 1 < len(parts):
                gateway = parts[idx + 1]
        if "metric" in parts:
            idx = parts.index("metric")
            if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                metric = int(parts[idx + 1])
        if metric is None:
            metric = 100 if name.startswith("usb") else 200 if name.startswith("eth") else None
        return gateway, metric

    def _routes(self) -> List[NetworkRoute]:
        routes = []
        if not _which("ip"):
            return routes
        output = subprocess.run(["ip", "route"], capture_output=True, text=True)
        if output.returncode != 0:
            return routes
        for line in output.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            destination = parts[0]
            gateway = ""
            interface = None
            if "via" in parts:
                gateway = parts[parts.index("via") + 1]
            if "dev" in parts:
                interface = parts[parts.index("dev") + 1]
            routes.append(NetworkRoute(destination, gateway, interface))
        return routes

    def _current_routes(self) -> List[Dict[str, object]]:
        if not _which("ip"):
            return []
        try:
            data = _run_ip_json(["route"])
            routes = []
            for entry in data:
                destination = entry.get("dst") or "default"
                routes.append(
                    {
                        "destination": destination,
                        "gateway": entry.get("gateway") or "",
                        "interface": entry.get("dev") or "",
                        "source": entry.get("prefsrc") or "",
                        "metric": entry.get("metric"),
                        "protocol": entry.get("protocol") or "",
                        "scope": entry.get("scope") or "",
                    }
                )
            return routes
        except (OSError, json.JSONDecodeError):
            return [route.__dict__ for route in self._routes()]

    def _default_route_interface(self) -> Optional[str]:
        if not _which("ip"):
            return None
        output = subprocess.run(
            ["ip", "route", "show", "default"], capture_output=True, text=True
        )
        if output.returncode != 0:
            return None
        for line in output.stdout.splitlines():
            parts = line.split()
            if "dev" in parts:
                return parts[parts.index("dev") + 1]
        return None

    # Quad9 (https://quad9.net/) for connectivity: 9.9.9.9 (IP), quad9.net (DNS).
    _CONNECTIVITY_IP = "9.9.9.9"
    _CONNECTIVITY_DNS = "quad9.net"

    def _check_dns(self) -> bool:
        """Return True if quad9.net resolves (DNS confirmation)."""
        try:
            socket.gethostbyname(self._CONNECTIVITY_DNS)
            return True
        except OSError:
            return False

    def _check_connectivity(self) -> bool:
        """Return True if system has internet: ping 9.9.9.9 + resolve quad9.net."""
        if platform.system().lower() == "windows":
            return False
        ping = subprocess.run(
            ["ping", "-c", "1", "-W", "1", self._CONNECTIVITY_IP],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if ping.returncode != 0:
            return False
        return self._check_dns()

    def _check_connectivity_via_interface(self, interface_id: str) -> bool:
        """Return True if the given interface can reach internet (ping 9.9.9.9 via that interface)."""
        if platform.system().lower() == "windows":
            return False
        if interface_id not in self._interface_names():
            return False
        ping = subprocess.run(
            ["ping", "-c", "1", "-W", "2", "-I", interface_id, self._CONNECTIVITY_IP],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return ping.returncode == 0

    def _ordered_wan_candidates(self) -> List[str]:
        """Return interface names in WAN preference order: USB first, then ethernet. Excludes wlan (hotspot)."""
        names = self._interface_names()
        usb = sorted(n for n in names if n.startswith("usb"))
        eth = sorted(n for n in names if n.startswith("eth"))
        return usb + eth

    def ensure_wan_priority(self) -> Dict[str, object]:
        """
        Prefer USB for WAN; if unavailable or no internet, fail over to ethernet.
        Sets default route to the first internet-capable interface in preference order.
        """
        if platform.system().lower() == "windows":
            return {"wan_interface": None, "internet_capable": False, "applied": False}
        if not _which("ip"):
            return {"wan_interface": None, "internet_capable": False, "applied": False}
        for iface in self._ordered_wan_candidates():
            gateway, _ = self._gateway_for(iface)
            if not gateway:
                continue
            stats = self._interface_stats(iface)
            if not stats.get("isup"):
                continue
            if not self._check_connectivity_via_interface(iface):
                continue
            metric = 100 if iface.startswith("usb") else 200
            subprocess.run(
                ["ip", "route", "replace", "default", "via", gateway, "dev", iface, "metric", str(metric)],
                check=False,
            )
            logger.debug("WAN priority set to %s (internet capable)", iface)
            return {
                "wan_interface": iface,
                "internet_capable": True,
                "applied": True,
            }
        default = self._default_route_interface()
        if not self._check_connectivity():
            logger.warning("No WAN connectivity; default route: %s", default)
        return {
            "wan_interface": default,
            "internet_capable": self._check_connectivity(),
            "applied": False,
        }

    def _hotspot_active(self) -> bool:
        if platform.system().lower() == "windows":
            return False
        if _which("systemctl"):
            result = subprocess.run(
                ["systemctl", "is-active", "hostapd"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
        return False

    def _hotspot_clients(self) -> List[Dict[str, object]]:
        if platform.system().lower() == "windows":
            return []
        clients: Dict[str, Dict[str, object]] = {}

        def ensure(mac: str) -> Dict[str, object]:
            if mac not in clients:
                clients[mac] = {"mac": mac}
            return clients[mac]

        hostapd = self._hostapd_stations()
        for mac, station in hostapd.items():
            entry = ensure(mac)
            entry.update(station)

        for lease in self._dnsmasq_leases():
            mac = lease.get("mac")
            if not mac:
                continue
            entry = ensure(mac)
            entry.update(lease)

        for neigh in self._arp_neighbors():
            mac = neigh.get("mac")
            if not mac:
                continue
            entry = ensure(mac)
            entry.update(neigh)

        return list(clients.values())

    def _hostapd_stations(self) -> Dict[str, Dict[str, object]]:
        if not _which("hostapd_cli"):
            return {}
        result = subprocess.run(
            ["hostapd_cli", "all_sta"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {}
        return _parse_hostapd_all_sta(result.stdout)

    def _dnsmasq_leases(self) -> List[Dict[str, object]]:
        lease_paths = [
            Path("/var/lib/misc/dnsmasq.leases"),
            Path("/var/lib/dnsmasq/dnsmasq.leases"),
        ]
        for path in lease_paths:
            if path.exists():
                try:
                    lines = path.read_text().splitlines()
                except OSError:
                    continue
                leases = []
                for line in lines:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    leases.append(
                        {
                            "lease_expires": parts[0],
                            "mac": parts[1],
                            "ip": parts[2],
                            "hostname": parts[3] if parts[3] != "*" else "",
                        }
                    )
                return leases
        return []

    def _arp_neighbors(self) -> List[Dict[str, object]]:
        if not _which("ip"):
            return []
        result = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True)
        if result.returncode != 0:
            return []
        neighbors = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            ip_address = parts[0]
            mac = None
            interface = None
            if "lladdr" in parts:
                idx = parts.index("lladdr")
                if idx + 1 < len(parts):
                    mac = parts[idx + 1]
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    interface = parts[idx + 1]
            if mac:
                neighbors.append({"ip": ip_address, "mac": mac, "interface": interface or ""})
        return neighbors

    def _role_for(self, name: str, iface_type: str) -> str:
        """WAN = interface can reach internet (9.9.9.9 + quad9.net DNS). LAN = hotspot or no internet."""
        if iface_type == "wifi" and name.startswith("wlan"):
            return "lan"
        if platform.system().lower() == "windows":
            return "wan"  # heuristic when connectivity checks unavailable
        if self._check_connectivity_via_interface(name) and self._check_dns():
            return "wan"
        return "lan"

    def _interface_type(self, name: str) -> str:
        if name.startswith("usb"):
            return "usb"
        if name.startswith("eth"):
            return "ethernet"
        if name.startswith("wlan"):
            return "wifi"
        return "unknown"

    def _friendly_name(self, name: str) -> str:
        if name.startswith("usb"):
            return "USB Jetpack"
        if name.startswith("eth"):
            return "Ethernet"
        if name.startswith("wlan"):
            return "WiFi Hotspot"
        return name

    def _driver_for(self, name: str) -> Optional[str]:
        if not _which("ethtool"):
            return None
        result = subprocess.run(
            ["ethtool", "-i", name], capture_output=True, text=True
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line.startswith("driver:"):
                return line.split(":", 1)[1].strip()
        return None

    def _apply_dhcp(self, interface_id: str) -> None:
        if platform.system().lower() == "windows":
            raise RuntimeError("DHCP not supported on Windows")
        subprocess.run(["dhclient", "-r", interface_id], check=False)
        subprocess.run(["dhclient", interface_id], check=True)

    def _apply_static(self, interface_id: str, config: Dict[str, object]) -> None:
        ip_address = config.get("ip_address")
        netmask = config.get("netmask")
        gateway = config.get("gateway")
        if not ip_address or not netmask:
            raise ValueError("ip_address and netmask required for static mode")
        if platform.system().lower() == "windows":
            raise RuntimeError("Static config not supported on Windows")
        cidr = _netmask_to_cidr(str(netmask))
        subprocess.run(["ip", "addr", "flush", "dev", interface_id], check=True)
        subprocess.run(
            ["ip", "addr", "add", f"{ip_address}/{cidr}", "dev", interface_id],
            check=True,
        )
        if gateway:
            subprocess.run(
                ["ip", "route", "replace", "default", "via", str(gateway), "dev", interface_id],
                check=True,
            )

    def _save_interface_config(self, interface_id: str, config: Dict[str, object]) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = CONFIG_DIR / f"{interface_id}.json"
        payload = {"interface": interface_id, "config": config, "saved_at": _timestamp()}
        path.write_text(json.dumps(payload, indent=2))

    def _save_route(self, route: NetworkRoute) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        path = CONFIG_DIR / "routes.json"
        payload = []
        if path.exists():
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                payload = []
        payload.append(route.__dict__)
        path.write_text(json.dumps(payload, indent=2))

    def _get_hotspot_credentials(self) -> Tuple[str, str]:
        """Return (ssid, password) for the WiFi hotspot from hostapd config or hotspot.secret."""
        if platform.system().lower() == "windows":
            return ("", "")
        config = self._get_hotspot_config()
        ssid = (config.get("ssid") or "").strip()
        password = (config.get("wpa_passphrase") or "").strip()
        if not ssid and HOTSPOT_SECRET_PATH.exists():
            try:
                lines = HOTSPOT_SECRET_PATH.read_text().strip().splitlines()
                if lines:
                    ssid = (lines[0] or "").strip()
                if len(lines) > 1:
                    password = (lines[1] or "").strip()
            except OSError:
                pass
        return (ssid, password)

    def _get_hotspot_config(self) -> Optional[Dict[str, object]]:
        hostapd_config = Path("/etc/hostapd/hostapd.conf")
        if not hostapd_config.exists():
            return None
        try:
            content = hostapd_config.read_text()
            config = {}
            for line in content.splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
            return config
        except OSError:
            return None

    def _get_share_interfaces(self) -> List[str]:
        """Return list of interface names configured to share with hotspot."""
        if not HOTSPOT_SHARE_CONFIG.exists():
            return []
        try:
            data = json.loads(HOTSPOT_SHARE_CONFIG.read_text())
            names = data.get("interfaces", [])
            return [n for n in names if isinstance(n, str)]
        except (OSError, json.JSONDecodeError):
            return []

    def _set_share_interfaces(self, interfaces: List[str]) -> None:
        """Persist interfaces that share with hotspot."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {"interfaces": list(interfaces), "updated_at": _timestamp()}
        HOTSPOT_SHARE_CONFIG.write_text(json.dumps(data, indent=2))

    def set_interface_share_hotspot(self, interface_id: str, enabled: bool) -> Dict[str, object]:
        """
        Enable or disable sharing this interface's connection with the wireless hotspot.
        When enabled, enables IPv4 forwarding and adds iptables FORWARD/MASQUERADE
        so hotspot clients can reach the internet and other networks via this interface.
        """
        if interface_id not in self._interface_names():
            raise KeyError("Interface not found")
        if interface_id.startswith("wlan"):
            raise ValueError("Cannot share wlan interface with hotspot (it is the hotspot)")
        dry_run = os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1"
        # Only one interface can share at a time; enabling one replaces any other
        if enabled:
            current = [interface_id]
        else:
            current = []
        self._set_share_interfaces(current)
        if dry_run:
            return {"interface": interface_id, "share_with_hotspot": enabled, "applied": False}
        if platform.system().lower() == "windows":
            return {"interface": interface_id, "share_with_hotspot": enabled, "applied": False}
        self._apply_hotspot_share()
        logger.info("Share with hotspot toggled iface=%s enabled=%s", interface_id, enabled)
        return {"interface": interface_id, "share_with_hotspot": enabled, "applied": True}

    def _apply_hotspot_share(self) -> None:
        """Apply ip_forward and iptables rules for interfaces sharing with hotspot."""
        if not _which("iptables"):
            return
        # Enable IPv4 forwarding (requires root when API runs as service user)
        sysctl_path = _which("sysctl") or "/usr/sbin/sysctl"
        if sysctl_path:
            r = _run_priv([sysctl_path, "-w", "net.ipv4.ip_forward=1"])
            if r.returncode != 0:
                logger.warning("Could not enable ip_forward: %s", r.stderr or r.stdout)
        interfaces = self._get_share_interfaces()
        if not interfaces:
            # No share interfaces; still ensure ESTABLISHED,RELATED for any install rules
            _iptables_ensure_established_related()
            return
        # Ensure ESTABLISHED,RELATED is first so return traffic is allowed (required for NAT)
        _iptables_ensure_established_related()
        # Remove stale rules for interfaces no longer in config
        for iface in self._interface_names():
            if iface.startswith("wlan"):
                continue
            comment = f"rpi-engineer-share:{iface}"
            _iptables_delete(None, "FORWARD", ["-i", "wlan0", "-o", iface, "-j", "ACCEPT"], comment)
            _iptables_delete("nat", "POSTROUTING", ["-o", iface, "-j", "MASQUERADE"], comment)
        # Add rules for configured share interfaces
        for iface in interfaces:
            if iface not in self._interface_names():
                continue
            comment = f"rpi-engineer-share:{iface}"
            _iptables_append(None, "FORWARD", ["-i", "wlan0", "-o", iface, "-j", "ACCEPT"], comment)
            _iptables_append("nat", "POSTROUTING", ["-o", iface, "-j", "MASQUERADE"], comment)

    def _restore_hotspot_config(self, config: Dict[str, object]) -> None:
        hostapd_config = Path("/etc/hostapd/hostapd.conf")
        hostapd_config.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(f"{k}={v}" for k, v in config.items())
        hostapd_config.write_text(content)
        if _which("systemctl"):
            subprocess.run(["systemctl", "restart", "hostapd"], check=False)


def _run_ip_json(args: List[str]) -> List[Dict[str, object]]:
    output = subprocess.check_output(["ip", "-j"] + args, text=True)
    return json.loads(output)


def _netmask_to_cidr(netmask: str) -> int:
    return sum(bin(int(part)).count("1") for part in netmask.split("."))


def _cidr_to_netmask(prefix_len: int) -> str:
    if prefix_len is None:
        return ""
    mask = (0xFFFFFFFF << (32 - int(prefix_len))) & 0xFFFFFFFF
    return ".".join(str((mask >> (8 * shift)) & 255) for shift in [3, 2, 1, 0])


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def _run_priv(cmd: List[str]) -> subprocess.CompletedProcess:
    """Run command; use sudo when not root (API runs as service user)."""
    try:
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            return subprocess.run(cmd, capture_output=True, text=True)
    except (AttributeError, OSError):
        pass
    sudo = _which("sudo")
    if sudo:
        return subprocess.run([sudo] + cmd, capture_output=True, text=True)
    return subprocess.run(cmd, capture_output=True, text=True)


def _parse_hostapd_all_sta(output: str) -> Dict[str, Dict[str, object]]:
    stations: Dict[str, Dict[str, object]] = {}
    current = None
    for line in output.splitlines():
        line = line.strip()
        if not line:
            current = None
            continue
        if _looks_like_mac(line):
            current = line.lower()
            stations[current] = {"mac": current}
            continue
        if current and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "signal" and value.lstrip("-").isdigit():
                stations[current]["signal_dbm"] = int(value)
            elif key == "rx_rate_info":
                stations[current]["rx_rate"] = value
            elif key == "tx_rate_info":
                stations[current]["tx_rate"] = value
            elif key == "connected_time" and value.isdigit():
                stations[current]["connected_time"] = int(value)
    return stations


def _iptables_ensure_established_related() -> None:
    """Ensure FORWARD allows ESTABLISHED,RELATED (return traffic for NAT). Required for hotspot share."""
    if not _which("iptables"):
        return
    ipt = _which("iptables") or "/usr/sbin/iptables"
    rule = ["-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"]
    comment = "rpi-engineer-share:established"
    check = [ipt, "-C", "FORWARD"] + rule + ["-m", "comment", "--comment", comment]
    append = [ipt, "-I", "FORWARD", "1"] + rule + ["-m", "comment", "--comment", comment]
    if _run_priv(check).returncode != 0:
        _run_priv(append)


def _iptables_append(table: Optional[str], chain: str, rule_args: List[str], comment: str) -> None:
    """Append iptables rule if not already present."""
    ipt = _which("iptables") or "/usr/sbin/iptables"
    base = [ipt] + (["-t", table] if table else [])
    rule = rule_args + ["-m", "comment", "--comment", comment]
    check = base + ["-C", chain] + rule
    append = base + ["-A", chain] + rule
    if _run_priv(check).returncode != 0:
        _run_priv(append)


def _iptables_delete(table: Optional[str], chain: str, rule_args: List[str], comment: str) -> None:
    """Delete iptables rule if present."""
    ipt = _which("iptables") or "/usr/sbin/iptables"
    base = [ipt] + (["-t", table] if table else [])
    cmd = base + ["-D", chain] + rule_args + ["-m", "comment", "--comment", comment]
    _run_priv(cmd)


def _looks_like_mac(value: str) -> bool:
    parts = value.split(":")
    if len(parts) != 6:
        return False
    for part in parts:
        if len(part) != 2:
            return False
        try:
            int(part, 16)
        except ValueError:
            return False
    return True


def _main() -> None:
    """Run periodic WAN priority check for failover when USB is lost (used by rpi-engineer-network service)."""
    import signal
    manager = NetworkManager()
    interval = int(os.getenv("RPI_ENGINEER_WAN_CHECK_INTERVAL", "60"))
    logger.info("Network manager daemon starting (WAN check interval=%ss)", interval)
    stop = False

    def _sig(_signum: int, _frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    while not stop:
        if platform.system().lower() != "windows":
            manager.ensure_wan_priority()
        time.sleep(interval)


if __name__ == "__main__":
    _main()

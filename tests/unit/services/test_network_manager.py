import json
import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

from services.network_manager import manager as network_manager


@pytest.mark.unit
def test_ordered_wan_candidates_prefers_usb_then_eth(monkeypatch):
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0", "usb0", "wlan0", "usb1"])
    assert manager._ordered_wan_candidates() == ["usb0", "usb1", "eth0"]


@pytest.mark.unit
def test_check_connectivity_via_interface_unknown_returns_false(monkeypatch):
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0"])
    assert manager._check_connectivity_via_interface("nonexistent") is False


@pytest.mark.unit
def test_ensure_wan_priority_windows_returns_not_applied(monkeypatch):
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Windows")
    manager = network_manager.NetworkManager()
    out = manager.ensure_wan_priority()
    assert out["applied"] is False
    assert out["internet_capable"] is False


@pytest.mark.unit
def test_ensure_wan_priority_no_ip_returns_not_applied(monkeypatch):
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(network_manager, "_which", lambda _: None)
    manager = network_manager.NetworkManager()
    out = manager.ensure_wan_priority()
    assert out["applied"] is False


@pytest.mark.unit
def test_ensure_wan_priority_applies_to_first_internet_capable(monkeypatch):
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")
    monkeypatch.setattr(network_manager, "_which", lambda b: "/usr/bin/ip" if b == "ip" else None)
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "_ordered_wan_candidates", lambda: ["usb0", "eth0"])
    monkeypatch.setattr(manager, "_gateway_for", lambda name: ("192.168.1.1", 100) if name == "usb0" else ("10.0.0.1", 200))
    monkeypatch.setattr(manager, "_interface_stats", lambda _: {"isup": True})
    monkeypatch.setattr(manager, "_check_connectivity_via_interface", lambda iface: iface == "usb0")
    monkeypatch.setattr(manager, "_default_route_interface", lambda: None)
    monkeypatch.setattr(manager, "_check_connectivity", lambda: False)
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(network_manager.subprocess, "run", fake_run)
    out = manager.ensure_wan_priority()
    assert out["wan_interface"] == "usb0"
    assert out["internet_capable"] is True
    assert out["applied"] is True
    assert "ip" in calls[0] and "route" in calls[0] and "replace" in calls[0] and "usb0" in calls[0]


@pytest.mark.unit
def test_netmask_to_cidr():
    assert network_manager._netmask_to_cidr("255.255.255.0") == 24
    assert network_manager._netmask_to_cidr("255.255.0.0") == 16


@pytest.mark.unit
def test_update_interface_dry_run_saves_config(tmp_path, monkeypatch):
    monkeypatch.setattr(network_manager, "CONFIG_DIR", tmp_path)
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0"])

    result = manager.update_interface("eth0", {"mode": "dhcp"})

    assert result["applied"] is False
    saved = tmp_path / "eth0.json"
    assert saved.exists()
    payload = json.loads(saved.read_text())
    assert payload["interface"] == "eth0"


@pytest.mark.unit
def test_add_route_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(network_manager, "CONFIG_DIR", tmp_path)
    manager = network_manager.NetworkManager()
    result = manager.add_route({"destination": "10.0.0.0/24", "gateway": "10.0.0.1"})

    assert result["destination"] == "10.0.0.0/24"
    assert (tmp_path / "routes.json").exists()


@pytest.mark.unit
def test_save_and_load_profile_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(network_manager, "PROFILE_DIR", tmp_path)
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "list_interfaces", lambda: {"interfaces": []})
    monkeypatch.setattr(manager, "list_routes", lambda: {"routes": []})

    saved = manager.save_profile({"name": "lab", "description": "Lab profile"})
    assert saved["name"] == "lab"

    load_result = manager.load_profile("lab")
    assert load_result["applied"] is False


@pytest.mark.unit
def test_delete_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(network_manager, "PROFILE_DIR", tmp_path)
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "list_interfaces", lambda: {"interfaces": []})
    monkeypatch.setattr(manager, "list_routes", lambda: {"routes": []})
    manager.save_profile({"name": "lab", "description": "Lab"})
    assert (tmp_path / "lab.json").exists()

    result = manager.delete_profile("lab")
    assert result["deleted"] is True
    assert not (tmp_path / "lab.json").exists()


@pytest.mark.unit
def test_update_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(network_manager, "PROFILE_DIR", tmp_path)
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "list_interfaces", lambda: {"interfaces": []})
    monkeypatch.setattr(manager, "list_routes", lambda: {"routes": []})
    manager.save_profile({"name": "lab", "description": "Original"})

    result = manager.update_profile("lab", {"description": "Updated"})
    assert result["description"] == "Updated"
    data = json.loads((tmp_path / "lab.json").read_text())
    assert data["description"] == "Updated"


# --- Tests for parallel connectivity and DNS fixes ---


@pytest.mark.unit
def test_role_for_uses_precomputed_dns_ok_true(monkeypatch):
    """_role_for uses dns_ok=True without calling _check_dns."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")
    dns_called = {"count": 0}

    def mock_check_dns():
        dns_called["count"] += 1
        return True

    monkeypatch.setattr(manager, "_check_dns", mock_check_dns)

    role = manager._role_for("eth0", "ethernet", connectivity={"eth0": True}, dns_ok=True)

    assert role == "wan"
    assert dns_called["count"] == 0, "_check_dns should not be called when dns_ok is provided"


@pytest.mark.unit
def test_role_for_uses_precomputed_dns_ok_false(monkeypatch):
    """_role_for uses dns_ok=False without calling _check_dns."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")

    role = manager._role_for("eth0", "ethernet", connectivity={"eth0": True}, dns_ok=False)

    assert role == "lan"


@pytest.mark.unit
def test_role_for_falls_back_to_check_dns_when_dns_ok_none(monkeypatch):
    """_role_for calls _check_dns when dns_ok is None (backward compatibility)."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")
    dns_called = {"count": 0}

    def mock_check_dns():
        dns_called["count"] += 1
        return True

    monkeypatch.setattr(manager, "_check_dns", mock_check_dns)

    role = manager._role_for("eth0", "ethernet", connectivity={"eth0": True}, dns_ok=None)

    assert role == "wan"
    assert dns_called["count"] == 1, "_check_dns should be called when dns_ok is None"


@pytest.mark.unit
def test_check_all_interface_connectivity_empty_list(monkeypatch):
    """Empty interface list returns empty dict."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")

    result = manager._check_all_interface_connectivity([])

    assert result == {}


@pytest.mark.unit
def test_check_all_interface_connectivity_all_wlan_skipped(monkeypatch):
    """wlan interfaces are skipped (always considered lan)."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")
    ping_called = {"count": 0}

    def mock_run(*args, **kwargs):
        ping_called["count"] += 1
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(network_manager.subprocess, "run", mock_run)

    result = manager._check_all_interface_connectivity(["wlan0", "wlan1"])

    assert result == {"wlan0": False, "wlan1": False}
    assert ping_called["count"] == 0, "Ping should not be called for wlan interfaces"


@pytest.mark.unit
def test_check_all_interface_connectivity_mixed_results(monkeypatch):
    """Returns correct connectivity state for each interface."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")

    def mock_run(cmd, **kwargs):
        if "-I" in cmd:
            iface_idx = cmd.index("-I") + 1
            iface = cmd[iface_idx]
            return subprocess.CompletedProcess(cmd, 0 if iface == "eth0" else 1)
        return subprocess.CompletedProcess(cmd, 1)

    monkeypatch.setattr(network_manager.subprocess, "run", mock_run)

    result = manager._check_all_interface_connectivity(["eth0", "usb0", "wlan0"])

    assert result["eth0"] is True
    assert result["usb0"] is False
    assert result["wlan0"] is False


@pytest.mark.unit
def test_check_all_interface_connectivity_handles_oserror(monkeypatch):
    """OSError in subprocess returns False for that interface."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Linux")

    def mock_run(cmd, **kwargs):
        raise OSError("ping not found")

    monkeypatch.setattr(network_manager.subprocess, "run", mock_run)

    result = manager._check_all_interface_connectivity(["eth0"])

    assert result["eth0"] is False


@pytest.mark.unit
def test_check_all_interface_connectivity_windows_all_false(monkeypatch):
    """On Windows, all interfaces return False."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(network_manager.platform, "system", lambda: "Windows")

    result = manager._check_all_interface_connectivity(["eth0", "usb0"])

    assert result == {"eth0": False, "usb0": False}


@pytest.mark.unit
def test_list_interfaces_checks_dns_once(monkeypatch):
    """list_interfaces calls _check_dns only once, not per-interface."""
    manager = network_manager.NetworkManager()
    dns_called = {"count": 0}

    def mock_check_dns():
        dns_called["count"] += 1
        return True

    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0", "usb0", "wlan0"])
    monkeypatch.setattr(manager, "_check_all_interface_connectivity", lambda names: {n: True for n in names})
    monkeypatch.setattr(manager, "_check_dns", mock_check_dns)
    monkeypatch.setattr(manager, "_build_interface", lambda name, connectivity=None, dns_ok=None: {"id": name, "dns_ok_passed": dns_ok})

    result = manager.list_interfaces()

    assert dns_called["count"] == 1, "_check_dns should be called exactly once"
    assert len(result["interfaces"]) == 3


@pytest.mark.unit
def test_build_interface_receives_dns_ok_parameter(monkeypatch):
    """_build_interface receives and uses the dns_ok parameter."""
    manager = network_manager.NetworkManager()
    build_calls = []

    original_build = manager._build_interface

    def mock_build(name, connectivity=None, dns_ok=None):
        build_calls.append({"name": name, "dns_ok": dns_ok})
        return {"id": name}

    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0", "usb0"])
    monkeypatch.setattr(manager, "_check_all_interface_connectivity", lambda names: {})
    monkeypatch.setattr(manager, "_check_dns", lambda: True)
    monkeypatch.setattr(manager, "_build_interface", mock_build)

    manager.list_interfaces()

    assert len(build_calls) == 2
    assert all(c["dns_ok"] is True for c in build_calls)


@pytest.mark.unit
def test_get_interface_works_without_precomputed_connectivity(monkeypatch):
    """Single interface lookup doesn't require batch connectivity check (backward compat)."""
    manager = network_manager.NetworkManager()
    monkeypatch.setattr(manager, "_interface_names", lambda: ["eth0"])
    monkeypatch.setattr(manager, "_interface_addrs", lambda _: {"ip_address": "192.168.1.1", "mac_address": None, "netmask": "255.255.255.0"})
    monkeypatch.setattr(manager, "_interface_stats", lambda _: {"isup": True, "mtu": 1500, "speed": 1000})
    monkeypatch.setattr(manager, "_gateway_for", lambda _: ("192.168.1.254", 100))
    monkeypatch.setattr(manager, "_driver_for", lambda _: "e1000")
    monkeypatch.setattr(manager, "_share_interfaces_runtime", lambda: [])
    monkeypatch.setattr(manager, "_check_connectivity_via_interface", lambda _: True)
    monkeypatch.setattr(manager, "_check_dns", lambda: True)

    result = manager.get_interface("eth0")

    assert result["id"] == "eth0"
    assert result["role"] == "wan"

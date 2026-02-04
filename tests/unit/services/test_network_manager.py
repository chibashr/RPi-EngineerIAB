import json

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

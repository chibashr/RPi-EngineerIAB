import json

import pytest

from services.network_manager import manager as network_manager


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

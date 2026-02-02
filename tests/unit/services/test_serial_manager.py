import types

import pytest

from services.serial_manager import manager as serial_manager


@pytest.mark.unit
def test_chipset_from_vid_parses_values():
    assert serial_manager._chipset_from_vid("0x0403") == "FTDI"
    assert serial_manager._chipset_from_vid(0x067B) == "Prolific"
    assert serial_manager._chipset_from_vid("bad") == "Unknown"


@pytest.mark.unit
def test_list_devices_uses_configs(monkeypatch):
    manager = serial_manager.SerialManager()
    monkeypatch.setattr(
        manager,
        "_scan_devices",
        lambda: [
            {"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "Device", "chipset": "FTDI"}
        ],
    )
    manager._device_configs["/dev/ttyUSB0"] = {"friendly_name": "Router A", "baud_rate": 115200}

    devices = manager.list_devices()["devices"]

    assert devices[0]["friendly_name"] == "Router A"
    assert devices[0]["baud_rate"] == 115200


@pytest.mark.unit
def test_create_session_writes_log(tmp_path, monkeypatch):
    manager = serial_manager.SerialManager()
    monkeypatch.setattr(serial_manager, "LOG_DIR", tmp_path)
    monkeypatch.setattr(manager, "_scan_devices", lambda: [{"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "Device", "chipset": "FTDI"}])
    monkeypatch.setattr(serial_manager, "serial", types.SimpleNamespace())

    payload = manager.create_session({"device_id": "/dev/ttyUSB0"})

    assert payload["device_id"] == "/dev/ttyUSB0"
    assert (tmp_path / f"{payload['session_id']}.log").exists()

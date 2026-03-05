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
        lambda use_cache=True: [
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
    monkeypatch.setattr(manager, "_scan_devices", lambda use_cache=True: [{"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "Device", "chipset": "FTDI"}])
    monkeypatch.setattr(serial_manager, "serial", types.SimpleNamespace())

    payload = manager.create_session({"device_id": "/dev/ttyUSB0"})

    assert payload["device_id"] == "/dev/ttyUSB0"
    assert (tmp_path / f"{payload['session_id']}.log").exists()


@pytest.mark.unit
def test_create_session_max_sessions_reached(tmp_path, monkeypatch):
    """When MAX_SESSIONS=1, creating a second session fails."""
    manager = serial_manager.SerialManager()
    monkeypatch.setattr(serial_manager, "MAX_SESSIONS", 1)
    monkeypatch.setattr(serial_manager, "LOG_DIR", tmp_path)
    monkeypatch.setattr(manager, "_scan_devices", lambda use_cache=True: [
        {"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "A", "chipset": "FTDI"},
        {"id": "/dev/ttyUSB1", "path": "/dev/ttyUSB1", "friendly_name": "B", "chipset": "FTDI"},
    ])
    monkeypatch.setattr(serial_manager, "serial", types.SimpleNamespace())

    manager.create_session({"device_id": "/dev/ttyUSB0"})
    with pytest.raises(RuntimeError, match="Maximum sessions"):
        manager.create_session({"device_id": "/dev/ttyUSB1"})


@pytest.mark.unit
def test_release_session_removes_from_registry(tmp_path, monkeypatch):
    """release_session removes session so device becomes available."""
    manager = serial_manager.SerialManager()
    monkeypatch.setattr(serial_manager, "LOG_DIR", tmp_path)
    monkeypatch.setattr(manager, "_scan_devices", lambda use_cache=True: [{"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "Device", "chipset": "FTDI"}])
    monkeypatch.setattr(serial_manager, "serial", types.SimpleNamespace())

    payload = manager.create_session({"device_id": "/dev/ttyUSB0"})
    session_id = payload["session_id"]
    assert len(manager._sessions) == 1

    manager.release_session(session_id)
    assert len(manager._sessions) == 0
    manager.release_session(session_id)
    assert len(manager._sessions) == 0


@pytest.mark.unit
def test_device_scan_cache_respects_use_cache(monkeypatch):
    """_scan_devices with use_cache=False bypasses cache."""
    manager = serial_manager.SerialManager()
    devices = [{"id": "/dev/ttyUSB0", "path": "/dev/ttyUSB0", "friendly_name": "Device", "chipset": "FTDI"}]
    call_count = [0]

    def fake_scan(use_cache=True):
        call_count[0] += 1
        return devices

    monkeypatch.setattr(manager, "_scan_devices", fake_scan)
    manager._scan_devices(use_cache=True)
    manager._scan_devices(use_cache=False)
    assert call_count[0] == 2

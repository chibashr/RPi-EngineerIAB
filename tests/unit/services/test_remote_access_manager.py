import pytest

from services.remote_access_manager.manager import RemoteAccessManager, _format_id


@pytest.mark.unit
def test_format_id_groups_digits():
    assert _format_id("123456789") == "123 456 789"
    assert _format_id("abc") == ""


@pytest.mark.unit
def test_tool_status_uses_process_state(monkeypatch):
    manager = RemoteAccessManager()
    monkeypatch.setattr(manager, "_process_running", lambda _: True)
    monkeypatch.setattr(manager, "_anydesk_id", lambda: "123 456")

    status = manager._tool_status("anydesk")

    assert status["status"] == "running"
    assert status["ready"] is True

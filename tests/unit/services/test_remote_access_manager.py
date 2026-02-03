import shutil

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


@pytest.mark.unit
def test_teamviewer_status_uses_teamviewerd_process(monkeypatch):
    """TeamViewer daemon runs as 'teamviewerd'; status must reflect that."""
    manager = RemoteAccessManager()
    seen = []

    def capture_process(name):
        seen.append(name)
        return name == "teamviewerd"

    monkeypatch.setattr(manager, "_process_running", capture_process)
    monkeypatch.setattr(manager, "_teamviewer_id", lambda: "444 555 666")

    status = manager._tool_status("teamviewer")

    assert "teamviewerd" in seen
    assert status["status"] == "running"
    assert status["connection_id"] == "444 555 666"


@pytest.mark.unit
def test_anydesk_id_fallback_to_config(monkeypatch):
    """When CLI is unavailable, ID is read from remote_access.conf."""
    manager = RemoteAccessManager()
    monkeypatch.setattr(
        manager, "_get_remote_access_config", lambda: {"anydesk": {"id": "111222333"}}
    )
    real_which = shutil.which

    def which_no_anydesk(cmd):
        if cmd == "anydesk":
            return None
        return real_which(cmd)

    monkeypatch.setattr(shutil, "which", which_no_anydesk)
    assert manager._anydesk_id() == "111 222 333"


@pytest.mark.unit
def test_teamviewer_id_fallback_to_etc_config(monkeypatch, tmp_path):
    """When CLI and app config lack ID, TeamViewer ID is read from /etc/teamviewer/global.conf."""
    from pathlib import Path

    from services.remote_access_manager import manager as ram

    etc_conf = tmp_path / "global.conf"
    etc_conf.write_text("[int32]\nClientID = 987654321\n")
    monkeypatch.setattr(ram, "TEAMVIEWER_ETC_CONF", etc_conf)
    monkeypatch.setattr(ram, "TEAMVIEWER_GLOBAL_CONF", tmp_path / "nonexistent.conf")
    monkeypatch.setattr(ram, "TEAMVIEWER_LOG_DIR", tmp_path / "logs")

    manager = RemoteAccessManager()
    monkeypatch.setattr(manager, "_get_remote_access_config", lambda: {})
    real_which = shutil.which

    def which_no_teamviewer(cmd):
        if cmd == "teamviewer":
            return None
        return real_which(cmd)

    monkeypatch.setattr(shutil, "which", which_no_teamviewer)
    assert manager._teamviewer_id() == "987 654 321"

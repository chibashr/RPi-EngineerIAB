import json

import pytest

from services.update_manager import manager as update_manager


@pytest.mark.unit
def test_is_hash_validation():
    assert update_manager._is_hash("a" * 40)
    assert not update_manager._is_hash("short")


@pytest.mark.unit
def test_check_for_updates_no_git(monkeypatch):
    monkeypatch.setattr(update_manager, "_which", lambda _: None)
    manager = update_manager.UpdateManager()

    result = manager.check_for_updates()

    assert result["update_available"] is False
    assert "git not available" in result["release_notes"]
    assert "last_update" in result
    assert "available_since" in result
    assert "available_commit_message" in result
    assert "available_commit_author" in result
    assert "files_changed" in result
    assert result["files_changed"] == []


@pytest.mark.unit
def test_apply_update_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = update_manager.UpdateManager()

    monkeypatch.setattr(
        manager,
        "check_for_updates",
        lambda: {"update_available": True, "available_version": "b" * 40, "current_version": "a" * 40},
    )
    result = manager.apply_update()

    assert result["dry_run"] is True
    assert result["current_version"] == "b" * 40


@pytest.mark.unit
def test_create_and_restore_backup(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    (config_dir / "system.conf").write_text("sample")
    (data_dir / "state.json").write_text(json.dumps({"ok": True}))

    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(data_dir))
    manager = update_manager.UpdateManager()

    backup = manager.create_config_backup(label="test")
    assert backup.exists()

    restore_target = tmp_path / "restore"
    monkeypatch.setattr(manager, "_config_dir", restore_target / "config")
    monkeypatch.setattr(manager, "_data_dir", restore_target / "data")

    result = manager.restore_config(str(backup))
    assert result["restored"] is True
    assert (restore_target / "config" / "system.conf").exists()

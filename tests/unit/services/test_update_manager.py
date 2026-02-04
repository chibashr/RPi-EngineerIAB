import json

import pytest
from pathlib import Path

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
    assert "update_branch" in result


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


@pytest.mark.unit
def test_apply_update_no_update_available(tmp_path, monkeypatch):
    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = update_manager.UpdateManager()
    monkeypatch.setattr(
        manager,
        "check_for_updates",
        lambda: {"update_available": False, "current_version": "a" * 40},
    )
    result = manager.apply_update()
    assert result["status"] == "up_to_date"
    assert result["current_version"] == "a" * 40


@pytest.mark.unit
def test_apply_update_perform_raises_rollback_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "0")
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "backups").mkdir(parents=True)
    manager = update_manager.UpdateManager()
    monkeypatch.setattr(
        manager,
        "check_for_updates",
        lambda: {"update_available": True, "available_version": "b" * 40, "current_version": "a" * 40},
    )
    monkeypatch.setattr(manager, "_perform_update", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("git fetch failed")))
    with pytest.raises(RuntimeError) as exc_info:
        manager.apply_update()
    assert "Update failed" in str(exc_info.value)
    assert "rollback attempted" in str(exc_info.value)


@pytest.mark.unit
def test_rollback_restores_version_to_data_when_config_readonly(tmp_path, monkeypatch):
    """Rollback should succeed by writing version to data dir when config dir is not writable."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    (data_dir / "backups").mkdir()
    (data_dir / "updates").mkdir(parents=True)
    backup_path = data_dir / "backups" / "pre-update-20200101T000000Z.zip"
    with update_manager.zipfile.ZipFile(backup_path, "w", update_manager.zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", '{"version":"1.0"}')
        zf.writestr("config/system.conf", "old")
    state_path = data_dir / "updates" / "state.json"
    state_path.write_text(
        json.dumps({
            "previous_version": "a" * 40,
            "backup_path": str(backup_path),
            "applied_at": "2020-01-01T00:00:00Z",
            "target_version": "b" * 40,
        })
    )
    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(data_dir))
    manager = update_manager.UpdateManager()
    manager._version_file = config_dir / "version"
    result = manager.rollback_update()
    assert result["status"] == "rolled_back"
    assert result["dry_run"] is True  # DRY_RUN is 1 by default
    # With DRY_RUN=0, restore runs; _write_version falls back to data if config not writable
    monkeypatch.setenv("RPI_ENGINEER_DRY_RUN", "0")
    result = manager.rollback_update()
    assert result["status"] == "rolled_back"
    # Version should be restored (to config or data)
    assert manager._current_version() == "a" * 40


@pytest.mark.unit
def test_write_version_fallback_to_data_dir(tmp_path, monkeypatch):
    """_write_version writes to data/version when config dir is not writable."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()
    data_dir.mkdir()
    monkeypatch.setenv("RPI_ENGINEER_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(data_dir))
    manager = update_manager.UpdateManager()
    manager._version_file = config_dir / "version"
    # Simulate config dir not writable by making Path.write_text raise on config/version
    real_write_text = Path.write_text
    def write_text_may_fail(self, content, encoding=None, errors=None):
        if self == config_dir / "version":
            raise OSError(13, "Permission denied")
        real_write_text(self, content, encoding=encoding, errors=errors)
    monkeypatch.setattr(Path, "write_text", write_text_may_fail)
    manager._write_version("abc1234")
    assert (data_dir / "version").read_text().strip() == "abc1234"
    assert manager._version_file == data_dir / "version"

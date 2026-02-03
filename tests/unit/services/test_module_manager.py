import json

import pytest

from services.module_manager.manager import (
    ModuleManager,
    _parse_version,
    _version_gt,
)


@pytest.mark.unit
def test_discover_modules_reads_metadata(tmp_path, monkeypatch):
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "example"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "example", "display_name": "Example", "version": "1.2.3"})
    )

    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))

    manager = ModuleManager()
    modules = manager.list_modules()["modules"]

    assert modules[0]["id"] == "example"
    assert modules[0]["version"] == "1.2.3"


@pytest.mark.unit
def test_resolve_web_asset_bounds_check(tmp_path, monkeypatch):
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "example"
    (module_dir / "web").mkdir(parents=True)
    (module_dir / "module.json").write_text(json.dumps({"name": "example"}))
    (module_dir / "web" / "module.js").write_text("console.log('ok');")

    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))

    manager = ModuleManager()
    asset = manager.resolve_web_asset("example", "module.js")
    assert asset and asset.name == "module.js"
    assert manager.resolve_web_asset("example", "../secrets") is None


def test_parse_version():
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("2.1") == (2, 1)
    assert _parse_version("0") == (0,)
    assert _parse_version("") == (0,)


def test_version_gt():
    assert _version_gt("1.0.1", "1.0.0") is True
    assert _version_gt("1.0.0", "1.0.0") is False
    assert _version_gt("1.0.0", "1.0.1") is False
    assert _version_gt("2.0.0", "1.9.9") is True


@pytest.mark.unit
def test_list_available_from_repo_local(tmp_path, monkeypatch):
    """When repo root has modules/, list_available_from_repo returns them from local disk."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "repo_module"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({
            "name": "repo_module",
            "display_name": "Repo Module",
            "version": "1.0.0",
            "description": "From repo",
        })
    )
    # Manager uses tmp_path as repo root and its own modules dir (can be same or different)
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    # Force repo root to tmp_path so _list_repo_modules_from_local reads from tmp_path/modules
    manager = ModuleManager()
    manager._repo_root = tmp_path
    # Simulate git repo presence
    (tmp_path / ".git").mkdir(exist_ok=True)
    payload = manager.list_available_from_repo()
    assert "available" in payload
    available = payload["available"]
    assert len(available) >= 1
    names = [a["id"] for a in available]
    assert "repo_module" in names

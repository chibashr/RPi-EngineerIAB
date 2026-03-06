import json
import sys

import pytest

from services.module_manager.manager import (
    ModuleManager,
    _github_repo_slug,
    _parse_version,
    _safe_extract,
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


def test_parse_version_non_string():
    assert _parse_version(None) == (0,)
    assert _parse_version(123) == (0,)
    assert _parse_version("1.2.3-beta") == (1, 2, 3)


def test_github_repo_slug():
    assert _github_repo_slug("https://github.com/owner/repo.git") == "owner/repo"
    assert _github_repo_slug("https://github.com/owner/repo") == "owner/repo"
    assert _github_repo_slug("https://example.com/owner/repo") is None
    assert _github_repo_slug("") is None


def test_safe_extract_path_traversal(tmp_path):
    import zipfile

    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../../etc/passwd", "content")
    dest = tmp_path / "extract"
    dest.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        with pytest.raises(RuntimeError, match="unsafe paths"):
            _safe_extract(zf, dest)


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


@pytest.mark.unit
def test_ensure_modules_on_path_adds_modules_dir_to_sys_path(tmp_path, monkeypatch):
    """_ensure_modules_on_path inserts the modules directory into sys.path."""
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "dummy").mkdir()
    (modules_dir / "dummy" / "module.json").write_text(json.dumps({"name": "dummy"}))
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    assert str(modules_dir.resolve()) in sys.path


@pytest.mark.unit
def test_attach_app_resets_routes_registered_when_app_changes(tmp_path, monkeypatch):
    """When attach_app is called with a different app, routes_registered is cleared."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "with_api"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({
            "name": "with_api",
            "display_name": "With API",
            "version": "1.0.0",
            "api_routes": [{"path": "/api/v1/with_api/ok", "methods": ["GET"]}],
        })
    )
    (module_dir / "__init__.py").write_text("")
    (module_dir / "api.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/ok')\n"
        "def ok(): return {'ok': True}\n"
    )
    (module_dir / "main.py").write_text("def initialize(): pass\ndef shutdown(): pass\n")
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    rec = manager._registry.get("with_api")
    assert rec is not None
    app1 = FastAPI()
    manager.attach_app(app1)
    manager.register_module_routes(app1)
    assert rec.routes_registered is True
    app2 = FastAPI()
    manager.attach_app(app2)
    assert rec.routes_registered is False
    manager.register_module_routes(app2)
    assert rec.routes_registered is True
    with TestClient(app2) as client:
        assert client.get("/api/v1/with_api/ok").status_code == 200


@pytest.mark.unit
def test_enable_disable_module_toggles_state_and_persists(tmp_path, monkeypatch):
    """enable_module and disable_module update state and save enabled list."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "toggle_mod"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "toggle_mod", "display_name": "Toggle", "version": "1.0.0"})
    )
    (module_dir / "__init__.py").write_text("")
    (module_dir / "api.py").write_text("def register_routes(app): pass\n")
    (module_dir / "main.py").write_text("def initialize(): pass\ndef shutdown(): pass\n")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(data_dir))
    manager = ModuleManager()
    assert manager.is_enabled("toggle_mod") is False
    manager.enable_module("toggle_mod")
    assert manager.is_enabled("toggle_mod") is True
    state_file = data_dir / "modules" / "state.json"
    assert state_file.exists()
    assert "toggle_mod" in json.loads(state_file.read_text()).get("enabled_modules", [])
    manager.disable_module("toggle_mod")
    assert manager.is_enabled("toggle_mod") is False
    assert "toggle_mod" not in json.loads(state_file.read_text()).get("enabled_modules", [])


@pytest.mark.unit
def test_install_module_already_in_registry(tmp_path, monkeypatch):
    """install_module with module_id already installed returns early."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "existing"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "existing", "display_name": "Existing", "version": "1.0.0"})
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    result = manager.install_module({"module_id": "existing"})
    assert result == {"installed": True, "module_id": "existing"}


@pytest.mark.unit
def test_install_module_from_archive(tmp_path, monkeypatch):
    """install_module from file URL extracts zip and discovers module."""
    import zipfile

    modules_dir = tmp_path / "modules"
    modules_dir.mkdir(parents=True)
    archive_path = tmp_path / "mod.zip"
    mod_root = tmp_path / "archive_mod"
    mod_root.mkdir()
    (mod_root / "module.json").write_text(
        json.dumps({"name": "archive_mod", "version": "1.0.0", "description": "From zip"})
    )
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.write(mod_root / "module.json", "archive_mod/module.json")
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    result = manager.install_module({"module_url": str(archive_path)})
    assert result["installed"] is True
    assert result["module_id"] == "archive_mod"
    assert (modules_dir / "archive_mod" / "module.json").exists()


@pytest.mark.unit
def test_uninstall_module(tmp_path, monkeypatch):
    """uninstall_module removes module dir and registry entry."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "to_remove"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "to_remove", "display_name": "To Remove", "version": "1.0.0"})
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    assert "to_remove" in manager._registry
    result = manager.uninstall_module("to_remove")
    assert result == {"uninstalled": True, "module_id": "to_remove"}
    assert "to_remove" not in manager._registry


@pytest.mark.unit
def test_get_web_components(tmp_path, monkeypatch):
    """get_web_components returns components from enabled modules only."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "with_components"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({
            "name": "with_components",
            "web_components": [{"tag": "my-widget", "path": "widget.js"}],
        })
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    components = manager.get_web_components()
    assert isinstance(components, list)
    manager.enable_module("with_components")
    components = manager.get_web_components()
    assert any(c.get("tag") == "my-widget" and c.get("module_id") == "with_components" for c in components)


@pytest.mark.unit
def test_check_module_updates(tmp_path, monkeypatch):
    """check_module_updates returns structure; with local repo, higher version in repo = update available."""
    installed_dir = tmp_path / "installed"
    repo_modules = tmp_path / "modules"
    (tmp_path / ".git").mkdir(exist_ok=True)
    # Installed module (lower version)
    old_mod = installed_dir / "old_ver"
    old_mod.mkdir(parents=True)
    (old_mod / "module.json").write_text(
        json.dumps({"name": "old_ver", "version": "0.1.0", "description": "Old"})
    )
    # Repo has same module with higher version
    repo_mod = repo_modules / "old_ver"
    repo_mod.mkdir(parents=True)
    (repo_mod / "module.json").write_text(
        json.dumps({"name": "old_ver", "version": "1.0.0", "description": "New"})
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(installed_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    manager._repo_root = tmp_path
    manager.enable_module("old_ver")
    payload = manager.check_module_updates()
    assert "updates" in payload
    updates = payload["updates"]
    assert any(u.get("module_id") == "old_ver" for u in updates)


@pytest.mark.unit
def test_update_module(tmp_path, monkeypatch):
    """update_module overwrites module from repo and preserves enabled state."""
    installed_dir = tmp_path / "installed"
    repo_modules = tmp_path / "modules"
    (tmp_path / ".git").mkdir(exist_ok=True)
    # Installed module
    inst_mod = installed_dir / "to_update"
    inst_mod.mkdir(parents=True)
    (inst_mod / "module.json").write_text(
        json.dumps({"name": "to_update", "version": "1.0.0", "description": "Original"})
    )
    # Repo has updated version
    repo_mod = repo_modules / "to_update"
    repo_mod.mkdir(parents=True)
    (repo_mod / "module.json").write_text(
        json.dumps({"name": "to_update", "version": "2.0.0", "description": "Updated"})
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(installed_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    manager._repo_root = tmp_path
    manager.enable_module("to_update")
    result = manager.update_module("to_update")
    assert result == {"updated": True, "module_id": "to_update"}
    assert (installed_dir / "to_update" / "module.json").read_text().count("2.0.0") >= 1


@pytest.mark.unit
def test_cleanup(tmp_path, monkeypatch):
    """cleanup shuts down all enabled modules."""
    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "cleanup_mod"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "cleanup_mod", "display_name": "Cleanup", "version": "1.0.0"})
    )
    (module_dir / "main.py").write_text(
        "shutdown_called = []\n"
        "def initialize(): pass\n"
        "def shutdown(): shutdown_called.append(1)\n"
    )
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    manager.enable_module("cleanup_mod")
    import importlib
    mod = importlib.import_module("cleanup_mod.main")
    manager.cleanup()
    assert len(mod.shutdown_called) == 1

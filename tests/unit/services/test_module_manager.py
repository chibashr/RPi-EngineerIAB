import json
import sys

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
    from flask import Flask

    modules_dir = tmp_path / "modules"
    module_dir = modules_dir / "with_api"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "with_api", "display_name": "With API", "version": "1.0.0"})
    )
    (module_dir / "__init__.py").write_text("")
    (module_dir / "api.py").write_text(
        "from flask import Blueprint\n"
        "bp = Blueprint('with_api', __name__, url_prefix='/api/v1/with_api')\n"
        "@bp.get('/ok')\n"
        "def ok(): return {'ok': True}\n"
        "def register_routes(app): app.register_blueprint(bp)\n"
    )
    (module_dir / "main.py").write_text("def initialize(): pass\ndef shutdown(): pass\n")
    monkeypatch.setenv("RPI_ENGINEER_MODULES_DIR", str(modules_dir))
    monkeypatch.setenv("RPI_ENGINEER_DATA_DIR", str(tmp_path / "data"))
    manager = ModuleManager()
    rec = manager._registry.get("with_api")
    assert rec is not None
    app1 = Flask(__name__)
    manager.attach_app(app1)
    manager.register_module_routes(app1)
    assert rec.routes_registered is True
    app2 = Flask(__name__)
    manager.attach_app(app2)
    assert rec.routes_registered is False
    manager.register_module_routes(app2)
    assert rec.routes_registered is True
    assert app2.test_client().get("/api/v1/with_api/ok").status_code == 200


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

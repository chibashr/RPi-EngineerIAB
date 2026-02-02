import json

import pytest

from services.module_manager.manager import ModuleManager


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

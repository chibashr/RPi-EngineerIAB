"""Module Manager implementation for module lifecycle and registration."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import importlib.util


def _safe_dir(primary: Path, fallback: Path) -> Path:
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        name = member.filename
        if not name or name.endswith("/"):
            continue
        target = (destination / name).resolve()
        if not str(target).startswith(str(destination)):
            raise RuntimeError("Archive contains unsafe paths")
        archive.extract(member, destination)


@dataclass
class ModuleRecord:
    module_id: str
    name: str
    version: str
    description: str
    path: Path
    enabled: bool = False
    state: str = "installed"
    routes_registered: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


class ModuleManager:
    """Discover, enable, disable, and register modules."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        default_modules = Path("/opt/rpi-engineer/modules")
        self._modules_dir = Path(
            os.getenv(
                "RPI_ENGINEER_MODULES_DIR",
                str(default_modules if default_modules.exists() else repo_root / "modules"),
            )
        )
        self._modules_dir = _safe_dir(self._modules_dir, repo_root / "modules")
        self._data_dir = _safe_dir(
            Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer")),
            repo_root / "data",
        )
        self._state_file = self._data_dir / "modules" / "state.json"
        self._registry: Dict[str, ModuleRecord] = {}
        self._app = None
        self.discover_modules()

    def attach_app(self, app) -> None:  # type: ignore[no-untyped-def]
        self._app = app

    def discover_modules(self) -> Dict[str, List[Dict[str, object]]]:
        self._registry.clear()
        enabled_modules = set(self._load_enabled_modules())
        state_exists = self._state_file.exists()
        for module_dir in sorted(self._modules_dir.iterdir()):
            if not module_dir.is_dir():
                continue
            meta_path = module_dir / "module.json"
            if not meta_path.exists():
                continue
            try:
                metadata = json.loads(meta_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            module_id = metadata.get("name") or module_dir.name
            enabled_by_default = bool(metadata.get("enabled_by_default", False))
            is_enabled = (
                module_id in enabled_modules or (not state_exists and enabled_by_default)
            )
            record = ModuleRecord(
                module_id=module_id,
                name=metadata.get("display_name") or metadata.get("name") or module_id,
                version=metadata.get("version", "0.0.0"),
                description=metadata.get("description", ""),
                path=module_dir,
                enabled=is_enabled,
                metadata=metadata,
            )
            record.state = "enabled" if record.enabled else "disabled"
            self._registry[module_id] = record
        return {"modules": self.list_modules()["modules"]}

    def list_modules(self) -> Dict[str, List[Dict[str, object]]]:
        return {
            "modules": [
                {
                    "id": record.module_id,
                    "name": record.name,
                    "version": record.version,
                    "enabled": record.enabled,
                    "description": record.description,
                    "web_components": record.metadata.get("web_components", []),
                }
                for record in self._registry.values()
            ]
        }

    def is_enabled(self, module_id: str) -> bool:
        record = self._registry.get(module_id)
        return bool(record and record.enabled)

    def install_module(self, payload: Dict[str, object]) -> Dict[str, object]:
        module_id = payload.get("module_id")
        module_url = payload.get("module_url")
        if module_id and module_id in self._registry:
            return {"installed": True, "module_id": module_id}
        if not module_url:
            raise ValueError("module_id or module_url is required")
        module_path = self._install_from_archive(str(module_url))
        self.discover_modules()
        return {"installed": True, "module_id": module_path.name}

    def uninstall_module(self, module_id: str) -> Dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        if record.enabled:
            self.disable_module(module_id)
        shutil.rmtree(record.path, ignore_errors=True)
        self._registry.pop(module_id, None)
        self._save_enabled_modules()
        return {"uninstalled": True, "module_id": module_id}

    def enable_module(self, module_id: str) -> Dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        record.enabled = True
        record.state = "enabled"
        self._save_enabled_modules()
        self._load_module(record)
        return {"enabled": True, "module_id": module_id}

    def disable_module(self, module_id: str) -> Dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        record.enabled = False
        record.state = "disabled"
        self._save_enabled_modules()
        self._shutdown_module(record)
        return {"enabled": False, "module_id": module_id}

    def register_module_routes(self, app) -> None:  # type: ignore[no-untyped-def]
        self.attach_app(app)
        for record in self._registry.values():
            if record.enabled:
                self._load_module(record)

    def get_web_components(self) -> List[Dict[str, object]]:
        components: List[Dict[str, object]] = []
        for record in self._registry.values():
            if not record.enabled:
                continue
            for component in record.metadata.get("web_components", []):
                item = dict(component)
                item["module_id"] = record.module_id
                components.append(item)
        return components

    def resolve_web_asset(self, module_id: str, asset_path: str) -> Optional[Path]:
        record = self._registry.get(module_id)
        if not record:
            return None
        web_root = record.path / "web"
        candidate = (web_root / asset_path).resolve()
        if not str(candidate).startswith(str(web_root.resolve())):
            return None
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    def _load_module(self, record: ModuleRecord) -> None:
        main_path = record.path / "main.py"
        if main_path.exists():
            try:
                module = self._load_python_module(record.module_id, main_path)
            except Exception:
                record.state = "error"
                return
            if module and hasattr(module, "initialize"):
                try:
                    module.initialize()
                except Exception:
                    record.state = "error"
        api_path = record.path / "api.py"
        if api_path.exists() and self._app and not record.routes_registered:
            try:
                module = self._load_python_module(f"{record.module_id}_api", api_path)
            except Exception:
                record.state = "error"
                return
            if module and hasattr(module, "register_routes"):
                try:
                    module.register_routes(self._app)
                    record.routes_registered = True
                except Exception:
                    record.state = "error"

    def _shutdown_module(self, record: ModuleRecord) -> None:
        main_path = record.path / "main.py"
        if not main_path.exists():
            return
        try:
            module = self._load_python_module(record.module_id, main_path)
        except Exception:
            record.state = "error"
            return
        if module and hasattr(module, "shutdown"):
            try:
                module.shutdown()
            except Exception:
                record.state = "error"

    def _load_python_module(self, name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, str(path))
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_enabled_modules(self) -> List[str]:
        if not self._state_file.exists():
            return []
        try:
            payload = json.loads(self._state_file.read_text())
        except (OSError, json.JSONDecodeError):
            return []
        return list(payload.get("enabled_modules", []))

    def _save_enabled_modules(self) -> None:
        enabled = [mid for mid, record in self._registry.items() if record.enabled]
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"enabled_modules": enabled}, indent=2))

    def _install_from_archive(self, module_url: str) -> Path:
        path = Path(module_url.replace("file://", ""))
        if not path.exists():
            raise RuntimeError("Module archive not found")
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(path, "r") as archive:
                _safe_extract(archive, Path(tmpdir))
            extracted = Path(tmpdir)
            module_root = None
            for meta in extracted.rglob("module.json"):
                module_root = meta.parent
                break
            if not module_root:
                raise RuntimeError("Module archive missing module.json")
            destination = self._modules_dir / module_root.name
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(module_root, destination)
            return destination

"""Module Manager implementation for module lifecycle and registration."""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.module_logger import get_service_logger

# Same repo/branch as app updates (see services.update_manager.manager).
DEFAULT_UPDATE_REPO = "https://github.com/chibashr/RPi-EngineerIAB.git"
DEFAULT_UPDATE_BRANCH = "main"
MODULES_SUBDIR = "modules"


logger = get_service_logger(__name__)


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


def _github_repo_slug(repo_url: str) -> str | None:
    """Return 'owner/repo' for GitHub URLs, else None."""
    if not repo_url or "github.com" not in repo_url:
        return None
    try:
        path = urllib.parse.urlparse(repo_url.rstrip("/")).path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    except Exception:
        pass
    return None


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse semver-like string into comparable tuple; non-numeric segments become 0."""
    if not version or not isinstance(version, str):
        return (0,)
    parts = re.sub(r"[^0-9.]", "", version).strip(".").split(".") or ["0"]
    try:
        return tuple(int(p) for p in parts[:4])
    except ValueError:
        return (0,)


def _version_gt(remote: str, local: str) -> bool:
    """True if remote version is strictly greater than local (semver-like)."""
    return _parse_version(remote) > _parse_version(local)


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
    metadata: dict[str, object] = field(default_factory=dict)
    failed: bool = False
    last_error: str | None = None


class ModuleManager:
    """Discover, enable, disable, and register modules."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._repo_root = repo_root
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
        self._registry: dict[str, ModuleRecord] = {}
        self._app = None
        self._status_queue: asyncio.Queue | None = None
        self._ensure_modules_on_path()

    # ------------------------------------------------------------------
    # Discovery / metadata
    # ------------------------------------------------------------------

    def _ensure_modules_on_path(self) -> None:
        """Ensure the modules directory is on sys.path so import_module(module_id.api) resolves."""
        modules_str = str(self._modules_dir.resolve())
        if modules_str not in sys.path:
            sys.path.insert(0, modules_str)

    def discover_modules(self) -> list[dict[str, object]]:
        """Scan modules/*/module.json and return list of metadata dicts.

        The returned dicts have: id, name, version, enabled, status, path, metadata.
        """
        self._registry.clear()
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
            module_id = metadata.get("id") or metadata.get("name") or module_dir.name
            enabled_flag = bool(metadata.get("enabled", True))
            enabled_by_default = bool(metadata.get("enabled_by_default", enabled_flag))
            is_enabled = enabled_flag or enabled_by_default
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
        return [
            {
                "id": r.module_id,
                "name": r.name,
                "version": r.version,
                "enabled": r.enabled,
                "status": r.state,
                "path": str(r.path),
                "metadata": r.metadata,
            }
            for r in self._registry.values()
        ]

    def list_modules(self) -> dict[str, list[dict[str, object]]]:
        return {
            "modules": [
                {
                    "id": record.module_id,
                    "name": record.name,
                    "version": record.version,
                    "enabled": record.enabled,
                    "status": record.state,
                    "description": record.description,
                    "web_components": record.metadata.get("web_components", []),
                }
                for record in self._registry.values()
            ]
        }

    def is_enabled(self, module_id: str) -> bool:
        record = self._registry.get(module_id)
        return bool(record and record.enabled)

    def install_module(self, payload: dict[str, object]) -> dict[str, object]:
        module_id = payload.get("module_id")
        module_url = payload.get("module_url")
        if module_id and module_id in self._registry:
            return {"installed": True, "module_id": module_id}
        if not module_url:
            raise ValueError("module_id or module_url is required")
        module_path = self._install_from_archive(str(module_url))
        self.discover_modules()
        logger.info("Module installed from archive: %s", module_path.name)
        return {"installed": True, "module_id": module_path.name}

    def uninstall_module(self, module_id: str) -> dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        if record.enabled:
            self.disable_module(module_id)
        shutil.rmtree(record.path, ignore_errors=True)
        self._registry.pop(module_id, None)
        self._save_enabled_modules()
        logger.info("Module uninstalled: %s", module_id)
        return {"uninstalled": True, "module_id": module_id}

    def enable_module(self, module_id: str) -> dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        record.enabled = True
        record.state = "enabled"
        self._update_module_enabled_flag(record, True)
        logger.info("Module enabled: %s", module_id)
        self._save_enabled_modules()
        return {"enabled": True, "module_id": module_id}

    def disable_module(self, module_id: str) -> dict[str, object]:
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        record.enabled = False
        record.state = "disabled"
        self._update_module_enabled_flag(record, False)
        logger.info("Module disabled: %s", module_id)
        self._save_enabled_modules()
        self._shutdown_module(record)
        return {"enabled": False, "module_id": module_id}

    def _update_module_enabled_flag(self, record: ModuleRecord, enabled: bool) -> None:
        """Persist enabled flag to module.json for restart-based lifecycle."""
        meta_path = record.path / "module.json"
        if not meta_path.exists():
            return
        try:
            data = json.loads(meta_path.read_text())
            if not isinstance(data, dict):
                return
            data["enabled"] = bool(enabled)
            meta_path.write_text(json.dumps(data, indent=2))
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to update enabled flag for module %s", record.module_id)

    # ------------------------------------------------------------------
    # Core bootstrap: discovery + initialize + websocket registration
    # ------------------------------------------------------------------

    def discover_and_initialize(self, app, status_queue: asyncio.Queue[Any]) -> None:  # type: ignore[no-untyped-def]
        """Discover modules, register their API routers, and initialize enabled ones.

        Called once from create_app() during startup.
        """
        self._app = app
        self._status_queue = status_queue
        self.discover_modules()
        for record in self._registry.values():
            self._register_module_api_routes(record)
        for record in self._registry.values():
            if record.enabled:
                self._initialize_module(record, app, status_queue)
                self._register_module_websockets(record, app)

    def cleanup(self) -> None:
        """Shut down all enabled modules. Call during app lifespan shutdown."""
        for record in self._registry.values():
            if record.enabled:
                self._shutdown_module(record)

    def get_web_components(self) -> list[dict[str, object]]:
        components: list[dict[str, object]] = []
        for record in self._registry.values():
            if not record.enabled:
                continue
            for component in record.metadata.get("web_components", []):
                item = dict(component)
                item["module_id"] = record.module_id
                components.append(item)
        return components

    def resolve_web_asset(self, module_id: str, asset_path: str) -> Path | None:
        """Resolve a module web asset path. Tries registry first, then modules dir on disk."""
        record = self._registry.get(module_id)
        web_root: Path = record.path / "web" if record else self._modules_dir / module_id / "web"
        candidate = (web_root / asset_path).resolve()
        web_root_resolved = web_root.resolve()
        if not str(candidate).startswith(str(web_root_resolved)):
            return None
        if candidate.exists() and candidate.is_file():
            return candidate
        return None

    def _register_module_api_routes(self, record: ModuleRecord) -> None:
        """Register a module's FastAPI router if api.py defines `router`."""
        if record.routes_registered or not self._app:
            return
        api_path = record.path / "api.py"
        if not api_path.exists():
            return
        try:
            module = importlib.import_module(f"{record.module_id}.api")
        except Exception as exc:
            logger.warning("Module load failed id=%s error=%s", record.module_id, exc)
            record.state = "error"
            record.failed = True
            record.last_error = str(exc)
            return
        logger.info("Module loaded id=%s", record.module_id)
        router = getattr(module, "router", None)
        if router is not None:
            try:
                prefix = self._get_module_api_prefix(record)
                self._app.include_router(router, prefix=prefix)
                record.routes_registered = True
                logger.info("Module routes registered id=%s prefix=%s", record.module_id, prefix)
            except Exception as exc:
                logger.warning("Module load failed id=%s error=%s", record.module_id, exc)
                record.state = "error"
                record.failed = True
                record.last_error = str(exc)

    def _get_module_api_prefix(self, record: ModuleRecord) -> str:
        """Derive API prefix from module metadata or convention."""
        routes = record.metadata.get("api_routes") or []
        if routes and isinstance(routes[0], dict):
            path = routes[0].get("path", "")
            if path and "/" in path:
                parts = path.strip("/").split("/")
                if len(parts) >= 3:
                    return "/" + "/".join(parts[:3])
        return f"/api/v1/{record.module_id}"

    def _load_module_main(self, record: ModuleRecord):
        main_path = record.path / "main.py"
        if not main_path.exists():
            return None
        try:
            return importlib.import_module(f"{record.module_id}.main")
        except Exception as exc:
            logger.warning("Module main import failed id=%s error=%s", record.module_id, exc)
            record.state = "error"
            record.failed = True
            record.last_error = str(exc)
            return None

    def _initialize_module(self, record: ModuleRecord, app, status_queue: asyncio.Queue[Any]) -> None:  # type: ignore[no-untyped-def]
        """Invoke module.initialize(app, status_queue) if present; errors are logged and do not stop startup."""
        module = self._load_module_main(record)
        if not module or not hasattr(module, "initialize"):
            return
        try:
            module.initialize(app, status_queue)
            record.state = "running"
            logger.info("Module initialized id=%s", record.module_id)
        except Exception as exc:
            logger.warning("Module initialize failed id=%s error=%s", record.module_id, exc, exc_info=True)
            record.state = "error"
            record.failed = True
            record.last_error = str(exc)

    def _register_module_websockets(self, record: ModuleRecord, app) -> None:  # type: ignore[no-untyped-def]
        """Call module.register_websockets(app) if defined; errors are logged and ignored."""
        module = self._load_module_main(record)
        if not module or not hasattr(module, "register_websockets"):
            return
        try:
            module.register_websockets(app)
            logger.info("Module websockets registered id=%s", record.module_id)
        except Exception as exc:
            logger.warning("Module register_websockets failed id=%s error=%s", record.module_id, exc, exc_info=True)

    def _shutdown_module(self, record: ModuleRecord) -> None:
        module = self._load_module_main(record)
        if not module:
            return
        if module and hasattr(module, "shutdown"):
            try:
                module.shutdown()
                logger.debug("Module shutdown: %s", record.module_id)
            except Exception as exc:
                logger.warning("Module shutdown failed %s: %s", record.module_id, exc)
                record.state = "error"

    def _load_enabled_modules(self) -> list[str]:
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

    def _list_repo_modules_from_local(self) -> list[dict[str, object]]:
        """List modules from repo when running from a clone (modules/ under repo root)."""
        repo_modules = self._repo_root / MODULES_SUBDIR
        if not repo_modules.is_dir():
            return []
        out: list[dict[str, object]] = []
        for module_dir in sorted(repo_modules.iterdir()):
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
            out.append(
                {
                    "id": module_id,
                    "name": metadata.get("display_name") or metadata.get("name") or module_id,
                    "version": metadata.get("version", "0.0.0"),
                    "description": metadata.get("description", ""),
                }
            )
        return out

    def _list_repo_modules_from_github(self, repo_slug: str, branch: str) -> list[dict[str, object]]:
        """List modules from GitHub API (contents/modules, then each module.json)."""
        out: list[dict[str, object]] = []
        try:
            url = f"https://api.github.com/repos/{repo_slug}/contents/{MODULES_SUBDIR}?ref={urllib.parse.quote(branch)}"
            req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        for item in data:
            if not isinstance(item, dict) or item.get("type") != "dir":
                continue
            name = item.get("name")
            if not name or name.startswith("."):
                continue
            try:
                meta_url = f"https://api.github.com/repos/{repo_slug}/contents/{MODULES_SUBDIR}/{name}/module.json?ref={urllib.parse.quote(branch)}"
                req2 = urllib.request.Request(meta_url, headers={"Accept": "application/vnd.github.v3+json"})
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    meta_data = json.loads(resp2.read().decode())
                content_b64 = meta_data.get("content") if isinstance(meta_data, dict) else None
                if not content_b64:
                    continue
                meta_json = json.loads(base64.b64decode(content_b64).decode())
            except Exception:
                continue
            module_id = meta_json.get("name") or name
            out.append(
                {
                    "id": module_id,
                    "name": meta_json.get("display_name") or meta_json.get("name") or module_id,
                    "version": meta_json.get("version", "0.0.0"),
                    "description": meta_json.get("description", ""),
                }
            )
        return out

    def list_available_from_repo(self) -> dict[str, object]:
        """List modules available in the app update repo; mark installed and update availability."""
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        repo_modules_dir = self._repo_root / MODULES_SUBDIR
        from_local = repo_modules_dir.is_dir() and (self._repo_root / ".git").is_dir()
        if from_local:
            raw = self._list_repo_modules_from_local()
        else:
            slug = _github_repo_slug(repo)
            if not slug:
                return {"available": [], "message": "Repo URL is not a GitHub repo."}
            raw = self._list_repo_modules_from_github(slug, branch)
        installed = {r.module_id: r for r in self._registry.values()}
        available: list[dict[str, object]] = []
        for m in raw:
            mid = m.get("id") or m.get("name")
            if not mid:
                continue
            rec = installed.get(mid)
            repo_version = str(m.get("version", "0.0.0"))
            entry = dict(m)
            entry["installed"] = rec is not None
            entry["installed_version"] = rec.version if rec else None
            entry["update_available"] = bool(rec and _version_gt(repo_version, rec.version))
            available.append(entry)
        return {"available": available}

    def _download_repo_module(self, module_id: str) -> Path:
        """Fetch module from repo (GitHub archive or local) and copy into _modules_dir. Returns destination path."""
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        repo_modules_dir = self._repo_root / MODULES_SUBDIR
        from_local = repo_modules_dir.is_dir() and (self._repo_root / ".git").is_dir()
        if from_local:
            source = repo_modules_dir / module_id
            if not source.is_dir() or not (source / "module.json").exists():
                raise KeyError(f"Module {module_id!r} not found in repo.")
            destination = self._modules_dir / module_id
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(source, destination)
        slug = _github_repo_slug(repo)
        if not slug:
            raise RuntimeError("Repo URL is not a GitHub repo; cannot fetch module.")
        archive_url = f"https://github.com/{slug}/archive/refs/heads/{urllib.parse.quote(branch)}.zip"
        extract_root: Path | None = None
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            try:
                req = urllib.request.Request(archive_url, headers={"Accept": "application/zip"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    f.write(resp.read())
                f.close()
                with zipfile.ZipFile(f.name, "r") as archive:
                    extract_root = Path(f.name).parent / "repo_extract"
                    extract_root.mkdir(exist_ok=True)
                    try:
                        _safe_extract(archive, extract_root)
                    except Exception:
                        shutil.rmtree(extract_root, ignore_errors=True)
                        raise
                top = next(extract_root.iterdir(), None)
                if not top or not top.is_dir():
                    shutil.rmtree(extract_root, ignore_errors=True)
                    raise RuntimeError("Invalid repo archive layout.")
                source = top / MODULES_SUBDIR / module_id
                if not source.is_dir() or not (source / "module.json").exists():
                    shutil.rmtree(extract_root, ignore_errors=True)
                    raise KeyError(f"Module {module_id!r} not found in repo.")
                destination = self._modules_dir / module_id
                if destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                shutil.copytree(source, destination)
            finally:
                try:
                    os.unlink(f.name)
                except OSError:
                    pass
                if extract_root is not None and extract_root.exists():
                    shutil.rmtree(extract_root, ignore_errors=True)

    def install_module_from_repo(self, module_id: str) -> dict[str, object]:
        """Install a module from the app update repo (same repo/branch as app updates)."""
        if not module_id or not isinstance(module_id, str):
            raise ValueError("module_id is required")
        self._download_repo_module(module_id.strip())
        self.discover_modules()
        return {"installed": True, "module_id": module_id.strip()}

    def check_module_updates(self) -> dict[str, object]:
        """For each installed module, report if a newer version is available in the repo."""
        payload = self.list_available_from_repo()
        available_list = payload.get("available") or []
        updates: list[dict[str, object]] = []
        for m in available_list:
            if not m.get("installed"):
                continue
            if m.get("update_available"):
                updates.append(
                    {
                        "module_id": m.get("id"),
                        "name": m.get("name"),
                        "current_version": m.get("installed_version"),
                        "available_version": m.get("version"),
                    }
                )
        return {"updates": updates}

    def update_module(self, module_id: str) -> dict[str, object]:
        """Update an installed module from the repo (overwrites files; enabled state preserved)."""
        record = self._registry.get(module_id)
        if not record:
            raise KeyError("Module not found")
        self._download_repo_module(module_id)
        self.discover_modules()
        logger.info("Module updated from repo: %s", module_id)
        return {"updated": True, "module_id": module_id}

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

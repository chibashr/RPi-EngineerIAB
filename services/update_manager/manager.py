"""Update Manager implementation for update and backup operations."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


DEFAULT_UPDATE_REPO = "https://github.com/chibashr/RPi-EngineerIAB.git"
DEFAULT_UPDATE_BRANCH = "main"

# Required web assets (relative to web/) for offline UI. All must exist after update.
REQUIRED_WEB_ASSETS = [
    "index.html",
    "css/base.css",
    "css/theme.css",
    "css/layout.css",
    "css/components.css",
    "css/pages/simple.css",
    "js/pages/simple.js",
    "js/api.js",
    "js/theme.js",
    "advanced/index.html",
]

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dir(primary: Path, fallback: Path) -> Path:
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _which(binary: str) -> Optional[str]:
    return shutil.which(binary)


def _is_hash(value: str) -> bool:
    return bool(value) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


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
class UpdateState:
    previous_version: str
    backup_path: str
    applied_at: str
    target_version: str


class UpdateManager:
    """Manage update checks, application, and rollback."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        self._repo_root = repo_root
        self._data_dir = _safe_dir(
            Path(os.getenv("RPI_ENGINEER_DATA_DIR", "/var/lib/rpi-engineer")),
            repo_root / "data",
        )
        self._config_dir = _safe_dir(
            Path(os.getenv("RPI_ENGINEER_CONFIG_DIR", "/etc/rpi-engineer")),
            repo_root / "config",
        )
        self._version_file = self._resolve_version_file()
        self._state_file = self._data_dir / "updates" / "state.json"
        self._backups_dir = _safe_dir(self._data_dir / "backups", self._data_dir)
        self._staging_dir = _safe_dir(self._data_dir / "staging", self._data_dir)

    def check_for_updates(self) -> Dict[str, object]:
        current_version = self._current_version()
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        if not _which("git"):
            return {
                "current_version": current_version,
                "update_available": False,
                "available_version": "",
                "release_notes": "git not available on this system.",
            }
        result = subprocess.run(
            ["git", "ls-remote", repo, branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Unable to check updates")
        available = result.stdout.split()[0] if result.stdout.strip() else ""
        current_hash = current_version if _is_hash(current_version) else self._local_git_hash()
        if not current_hash:
            return {
                "current_version": current_version,
                "update_available": False,
                "available_version": "",
                "release_notes": "Version comparison unavailable.",
            }
        update_available = bool(available and available != current_hash)
        return {
            "current_version": current_hash,
            "update_available": update_available,
            "available_version": available,
            "release_notes": "Release notes available after staging.",
        }

    def apply_update(self) -> Dict[str, object]:
        update_info = self.check_for_updates()
        if not update_info.get("update_available"):
            return {"status": "up_to_date", "current_version": update_info["current_version"]}
        backup_path = self.create_config_backup(label="pre-update")
        previous_version = self._current_version()
        target_version = str(update_info.get("available_version") or previous_version)
        state = UpdateState(
            previous_version=previous_version,
            backup_path=str(backup_path),
            applied_at=_timestamp(),
            target_version=target_version,
        )
        self._write_state(state)
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {
                "status": "applied",
                "dry_run": True,
                "previous_version": previous_version,
                "current_version": target_version,
                "backup_path": str(backup_path),
            }
        try:
            self._perform_update(target_version)
        except Exception as exc:
            try:
                self.rollback_update()
            except Exception as rollback_exc:
                logger.warning("Rollback failed after update error: %s", rollback_exc)
            raise RuntimeError(f"Update failed; rollback attempted: {exc}") from exc
        return {
            "status": "applied",
            "dry_run": False,
            "previous_version": previous_version,
            "current_version": target_version,
            "backup_path": str(backup_path),
        }

    def rollback_update(self) -> Dict[str, object]:
        state = self._read_state()
        if not state:
            raise RuntimeError("No update state available for rollback")
        backup_path = Path(state.backup_path)
        if not backup_path.exists():
            raise RuntimeError("Backup archive not found for rollback")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {
                "status": "rolled_back",
                "dry_run": True,
                "version": state.previous_version,
                "backup_path": state.backup_path,
            }
        self.restore_config(str(backup_path))
        self._write_version(state.previous_version)
        return {
            "status": "rolled_back",
            "dry_run": False,
            "version": state.previous_version,
            "backup_path": state.backup_path,
        }

    def create_config_backup(self, label: str = "config") -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"{label}-{timestamp}.zip"
        backup_path = self._backups_dir / backup_name
        excludes = ["captures", "serial_logs", "logs", "tmp", "backups", "exports"]
        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "version": "1.0",
                "created": _timestamp(),
                "label": label,
                "source_version": self._current_version(),
                "includes": ["config", "data"],
                "excludes": excludes,
            }
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            if self._config_dir.exists():
                self._add_dir_to_archive(
                    archive, self._config_dir, Path("config"), exclude_names=[]
                )
            if self._data_dir.exists():
                self._add_dir_to_archive(
                    archive, self._data_dir, Path("data"), exclude_names=excludes
                )
        return backup_path

    def restore_config(self, backup_file: str) -> Dict[str, object]:
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise RuntimeError("Backup file not found")
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(backup_path, "r") as archive:
                _safe_extract(archive, Path(tmpdir))
            extracted = Path(tmpdir)
            config_root = extracted / "config"
            data_root = extracted / "data"
            if config_root.exists():
                self._restore_tree(config_root, self._config_dir)
            else:
                self._restore_tree(extracted, self._config_dir, skip_manifest=True)
            if data_root.exists():
                self._restore_tree(data_root, self._data_dir)
        return {
            "restored": True,
            "config_dir": str(self._config_dir),
            "data_dir": str(self._data_dir),
        }

    def _resolve_version_file(self) -> Path:
        config_path = self._config_dir / "version"
        data_path = self._data_dir / "version"
        if config_path.exists():
            return config_path
        if data_path.exists():
            return data_path
        return config_path

    def _current_version(self) -> str:
        if self._version_file.exists():
            try:
                return self._version_file.read_text().strip()
            except OSError:
                pass
        return os.getenv("RPI_ENGINEER_VERSION", "1.0.0")

    def _local_git_hash(self) -> Optional[str]:
        if not (self._repo_root / ".git").exists():
            return None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value if _is_hash(value) else None

    def _write_version(self, version: str) -> None:
        self._version_file.parent.mkdir(parents=True, exist_ok=True)
        self._version_file.write_text(str(version).strip())

    def _write_state(self, state: UpdateState) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "previous_version": state.previous_version,
            "backup_path": state.backup_path,
            "applied_at": state.applied_at,
            "target_version": state.target_version,
        }
        self._state_file.write_text(json.dumps(payload, indent=2))

    def _apply_web_permissions(self, root_dir: Path) -> None:
        """Re-apply nginx config and web root permissions so 403 is fixed after update."""
        script = root_dir / "bin" / "apply-web-permissions.sh"
        if script.exists():
            try:
                result = subprocess.run(
                    ["sudo", str(script)],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode != 0:
                    logger.warning(
                        "apply-web-permissions.sh failed (rc=%s): %s",
                        result.returncode,
                        result.stderr.strip() or result.stdout.strip(),
                    )
                return
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
                logger.warning("Could not run apply-web-permissions.sh: %s", e)
        # Fallback when script missing: apply web root ownership so nginx can serve.
        web_dir = root_dir / "web"
        if web_dir.is_dir():
            try:
                subprocess.run(
                    ["sudo", "chown", "-R", "www-data:www-data", str(web_dir)],
                    capture_output=True,
                    timeout=15,
                    check=False,
                )
                for parent in [root_dir.parent, root_dir]:
                    if parent.is_dir():
                        subprocess.run(
                            ["sudo", "chmod", "o+x", str(parent)],
                            capture_output=True,
                            timeout=5,
                            check=False,
                        )
                logger.info("Applied web permissions (fallback; apply-web-permissions.sh missing)")
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.warning("Could not apply web permissions fallback: %s", e)

    def _read_state(self) -> Optional[UpdateState]:
        if not self._state_file.exists():
            return None
        try:
            payload = json.loads(self._state_file.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return UpdateState(
            previous_version=payload.get("previous_version", ""),
            backup_path=payload.get("backup_path", ""),
            applied_at=payload.get("applied_at", ""),
            target_version=payload.get("target_version", ""),
        )

    def _verify_and_repair_web_assets(self, root_dir: Path, staging_dir: Path) -> None:
        """Ensure required web assets exist under root_dir/web; copy from staging if missing."""
        web_root = root_dir / "web"
        staging_web = staging_dir / "web"
        if not staging_web.is_dir():
            return
        missing = [p for p in REQUIRED_WEB_ASSETS if not (web_root / p).exists()]
        if not missing:
            return
        logger.warning("Missing web assets after update: %s; repairing from staging.", missing)
        for subdir in ("css", "js", "advanced", "docs"):
            src = staging_web / subdir
            dst = web_root / subdir
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)
        for path in missing:
            src = staging_web / path
            dst = web_root / path
            if src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        still_missing = [p for p in REQUIRED_WEB_ASSETS if not (web_root / p).exists()]
        if still_missing:
            logger.error("Web assets still missing after repair: %s", still_missing)

    def _perform_update(self, target_version: str) -> None:
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        staging_dir = self._staging_dir / "update"
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo, str(staging_dir)],
            check=True,
        )
        # Critical dirs: replace entirely so we get a clean deploy (avoids 403, service crashes).
        replace_dirs = {"web", "services", "bin", "lib"}
        for item in staging_dir.iterdir():
            if item.name in {".git", ".github"}:
                continue
            destination = root_dir / item.name
            if item.is_dir():
                if item.name in replace_dirs and destination.exists():
                    shutil.rmtree(destination, ignore_errors=True)
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, destination)
        self._verify_and_repair_web_assets(root_dir, staging_dir)
        self._write_version(target_version)
        self._apply_web_permissions(root_dir)

    def _add_dir_to_archive(
        self,
        archive: zipfile.ZipFile,
        root: Path,
        prefix: Path,
        exclude_names: list[str],
    ) -> None:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] in exclude_names:
                continue
            archive.write(path, prefix / rel)

    def _restore_tree(
        self, source: Path, target_root: Path, skip_manifest: bool = False
    ) -> None:
        for path in source.rglob("*"):
            if skip_manifest and path.name == "manifest.json":
                continue
            relative = path.relative_to(source)
            target = target_root / relative
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

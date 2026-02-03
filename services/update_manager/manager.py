"""Update Manager implementation for update and backup operations.

Update checks compare repo refs (commit hashes) between the remote branch
and the local install, not version numbers. The version file may store
either a 40-char git hash (after an in-app update) or a fallback version string.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


DEFAULT_UPDATE_REPO = "https://github.com/chibashr/RPi-EngineerIAB.git"
DEFAULT_UPDATE_BRANCH = "main"

# Core trees to verify on update: every file under these is required and checked.
CORE_DIRS = ("web", "services", "lib", "bin")

# Exclude patterns when discovering core files (path segments or names).
CORE_EXCLUDE = ("__pycache__", ".git", ".pyc")

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


def _github_repo_slug(repo_url: str) -> Optional[str]:
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


def _github_commit_date(repo_slug: str, commit_hash: str) -> Optional[str]:
    """Fetch commit date (ISO) from GitHub API. Returns None on any failure."""
    if not _is_hash(commit_hash):
        return None
    url = f"https://api.github.com/repos/{repo_slug}/commits/{commit_hash}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        commit = data.get("commit") or {}
        author = commit.get("author") or {}
        return author.get("date")  # ISO 8601
    except Exception:
        return None


def _github_tree_blobs(repo_slug: str, commit_ref: str) -> Optional[list[tuple[str, str]]]:
    """Fetch recursive tree for commit; return list of (path, blob_sha) for type blob under CORE_DIRS."""
    if not commit_ref:
        return None
    try:
        url = f"https://api.github.com/repos/{repo_slug}/commits/{commit_ref}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            commit_data = json.loads(resp.read().decode())
        tree_url = (commit_data.get("commit") or {}).get("tree", {}).get("url")
        if not tree_url:
            return None
        req2 = urllib.request.Request(tree_url + "?recursive=1", headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            tree_data = json.loads(resp2.read().decode())
        blobs: list[tuple[str, str]] = []
        for node in tree_data.get("tree") or []:
            if node.get("type") != "blob":
                continue
            path = node.get("path") or ""
            if not path or path.startswith((".git", ".github", "__pycache__")) or ".pyc" in path:
                continue
            top = path.split("/")[0] if "/" in path else path
            if top not in CORE_DIRS:
                continue
            blobs.append((path, node.get("sha") or ""))
        return blobs
    except Exception:
        return None


def _git_blob_sha(content: bytes) -> str:
    """Compute git blob object SHA1 (blob {size}\\0{content})."""
    blob = b"blob " + str(len(content)).encode() + b"\0" + content
    return hashlib.sha1(blob).hexdigest()


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
        """Check for repo changes by comparing remote branch ref to local ref (not version number)."""
        state = self._read_state()
        last_update = state.applied_at if state else None

        current_version = self._current_version()
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        if not _which("git"):
            return {
                "current_version": current_version,
                "update_available": False,
                "available_version": "",
                "release_notes": "git not available on this system.",
                "last_update": last_update,
                "available_since": None,
                "files_changed": [],
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
                "last_update": last_update,
                "available_since": None,
                "files_changed": [],
            }
        ref_differs = bool(available and available != current_hash)
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        files_changed: list[str] = []
        slug = _github_repo_slug(repo)
        if slug and available and _is_hash(available):
            blobs = _github_tree_blobs(slug, available)
            if blobs:
                for path, remote_sha in blobs:
                    local_path = root_dir / path
                    try:
                        content = local_path.read_bytes()
                    except OSError:
                        files_changed.append(path)
                        continue
                    local_sha = _git_blob_sha(content)
                    if local_sha != remote_sha:
                        files_changed.append(path)
        update_available = ref_differs or len(files_changed) > 0
        available_since = None
        if available and update_available and slug:
            available_since = _github_commit_date(slug, available)
        return {
            "current_version": current_hash,
            "update_available": update_available,
            "available_version": available,
            "release_notes": "Release notes available after staging." if update_available else "",
            "last_update": last_update,
            "available_since": available_since,
            "files_changed": files_changed[:200],
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

    def run_reconfigure(self) -> Dict[str, object]:
        """Run install script in reconfigure mode (re-apply config from existing install.conf). Requires root."""
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        install_script = root_dir / "bin" / "install.sh"
        if not install_script.exists():
            raise RuntimeError("Install script not found; run reconfigure from the device where the app is installed.")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {
                "status": "reconfigure_dry_run",
                "message": "Reconfigure would run install.sh with INSTALL_MODE=reconfigure. Set RPI_ENGINEER_DRY_RUN=0 to run.",
            }
        env = {**os.environ, "NONINTERACTIVE": "1", "INSTALL_MODE": "reconfigure"}
        try:
            result = subprocess.run(
                ["sudo", str(install_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Reconfigure timed out after 5 minutes.") from None
        except FileNotFoundError:
            raise RuntimeError("sudo or install script not found.") from None
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or (result.stdout or "").strip()
            raise RuntimeError(f"Reconfigure failed (exit {result.returncode}): {stderr[:500]}")
        return {
            "status": "reconfigured",
            "message": "Configuration re-applied. Reboot recommended for hotspot changes.",
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

    def _list_core_files(self, base: Path) -> list[str]:
        """Return relative paths of all files under base, excluding __pycache__, .git, .pyc."""
        out: list[str] = []
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in path.parts for part in CORE_EXCLUDE):
                continue
            if path.suffix == ".pyc":
                continue
            try:
                rel = path.relative_to(base)
                out.append(str(rel).replace("\\", "/"))
            except ValueError:
                continue
        return out

    def _verify_and_repair_core_assets(self, root_dir: Path, staging_dir: Path) -> None:
        """Ensure every file under web, services, lib, bin exists at root_dir; copy from staging if missing."""
        for dir_name in CORE_DIRS:
            staging_base = staging_dir / dir_name
            root_base = root_dir / dir_name
            if not staging_base.is_dir():
                continue
            expected = self._list_core_files(staging_base)
            missing = [p for p in expected if not (root_base / p).exists()]
            if not missing:
                continue
            logger.warning(
                "Missing %s files after update (%d): repairing from staging.",
                dir_name,
                len(missing),
            )
            if root_base.exists():
                shutil.rmtree(root_base, ignore_errors=True)
            shutil.copytree(staging_base, root_base, dirs_exist_ok=True)
            still_missing = [p for p in expected if not (root_base / p).exists()]
            for p in still_missing:
                src = staging_base / p
                dst = root_base / p
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            still_missing = [p for p in expected if not (root_base / p).exists()]
            if still_missing:
                logger.error("%s still missing after repair: %s", dir_name, still_missing[:20])

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
        self._verify_and_repair_core_assets(root_dir, staging_dir)
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

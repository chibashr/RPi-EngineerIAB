"""Update Manager implementation for update and backup operations.

Update checking is git-pull–style: when the app runs from a git clone, we
look through the repo by fetching the remote branch and comparing HEAD to
origin/<branch>, and list files that differ or are missing so everything is
up to date or present. When not a git repo (e.g. tarball install), we
compare remote tree blobs to the install directory. The version file may
store a 40-char git hash (after an in-app update) or a fallback version string.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from ._backup import _add_dir_to_archive, _restore_tree, _safe_extract
from ._git import _check_updates_via_git, _git_blob_sha, _git_safe_dir, _is_hash
from ._github import _github_commit_info, _github_repo_slug, _github_tree_blobs
from lib.module_logger import get_service_logger
from ._version import _current_version, _local_git_hash, _resolve_version_file, _write_version


DEFAULT_UPDATE_REPO = "https://github.com/chibashr/RPi-EngineerIAB.git"
DEFAULT_UPDATE_BRANCH = "main"

# Core trees to verify on update: every file under these is required and checked.
CORE_DIRS = ("web", "services", "lib", "bin")

# Exclude patterns when discovering core files (path segments or names).
CORE_EXCLUDE = ("__pycache__", ".git", ".pyc")

logger = get_service_logger(__name__)


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


def _sudo_unavailable_message(err: str) -> bool:
    """True if the error indicates sudo cannot run (e.g. container no-new-privileges)."""
    if not err:
        return False
    lower = err.lower()
    return "no new privileges" in lower or "adjust the container" in lower




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
        self._version_file = _resolve_version_file(self._config_dir, self._data_dir)
        self._state_file = self._data_dir / "updates" / "state.json"
        self._state_file_fallback = repo_root / "data" / "updates" / "state.json"
        self._state_file_temp = Path(tempfile.gettempdir()) / "rpi-engineer-updates" / "state.json"
        self._backups_dir = _safe_dir(self._data_dir / "backups", self._data_dir)
        self._staging_dir = _safe_dir(self._data_dir / "staging", self._data_dir)

    def check_for_updates(self) -> Dict[str, object]:
        """Check for updates by looking through the git repo and ensuring files are up to date or present.
        When running from a git clone: fetch origin, compare HEAD to origin/branch, list differing files (git-pull–style).
        When not a git repo: compare remote branch ref and tree blobs to the install directory.
        """
        state = self._read_state()
        last_update = state.applied_at if state else None
        current_version = _current_version(self._version_file)
        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))

        if not _which("git"):
            return self._check_response(
                current_version=current_version,
                update_available=False,
                available_version="",
                release_notes="git not available on this system.",
                last_update=last_update,
                files_changed=[],
                branch=branch,
                root_dir=root_dir,
                repo=repo,
            )

        # Prefer git-pull–style check when the install (or running code) is a git repo
        repo_dir = root_dir if (root_dir / ".git").is_dir() else (
            self._repo_root if (self._repo_root / ".git").is_dir() else None
        )
        if repo_dir is not None:
            git_result = _check_updates_via_git(repo_dir, repo, branch, CORE_DIRS)
            if git_result is not None:
                local_hash, available_hash, files_changed = git_result
                update_available = local_hash != available_hash or len(files_changed) > 0
                available_since = None
                available_commit_message = None
                available_commit_author = None
                slug = _github_repo_slug(repo)
                if slug and update_available:
                    commit_info = _github_commit_info(slug, available_hash)
                    if commit_info:
                        available_since = commit_info.get("date")
                        available_commit_message = commit_info.get("message") or None
                        available_commit_author = commit_info.get("author") or None
                if update_available:
                    logger.info("Update check: available %s -> %s (%d files)", local_hash[:7] if local_hash else "", available_hash[:7] if available_hash else "", len(files_changed))
                return self._check_response(
                    current_version=local_hash,
                    update_available=update_available,
                    available_version=available_hash,
                    release_notes="Release notes available after staging." if update_available else "",
                    last_update=last_update,
                    available_since=available_since,
                    available_commit_message=available_commit_message,
                    available_commit_author=available_commit_author,
                    files_changed=files_changed[:200],
                    branch=branch,
                    root_dir=root_dir,
                    repo=repo,
                )

        # Fallback: not a git repo; compare remote ref and tree blobs to install directory
        result = subprocess.run(
            ["git", "ls-remote", repo, branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Unable to check updates")
        available = result.stdout.split()[0] if result.stdout.strip() else ""
        current_hash = current_version if _is_hash(current_version) else _local_git_hash(self._repo_root)
        if not current_hash:
            return self._check_response(
                current_version=current_version,
                update_available=False,
                available_version="",
                release_notes="Version comparison unavailable.",
                last_update=last_update,
                files_changed=[],
                branch=branch,
                root_dir=root_dir,
                repo=repo,
            )
        ref_differs = bool(available and available != current_hash)
        files_changed = []
        slug = _github_repo_slug(repo)
        if slug and available and _is_hash(available):
            blobs = _github_tree_blobs(slug, available, CORE_DIRS)
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
        available_commit_message = None
        available_commit_author = None
        if available and update_available and slug:
            commit_info = _github_commit_info(slug, available)
            if commit_info:
                available_since = commit_info.get("date")
                available_commit_message = commit_info.get("message") or None
                available_commit_author = commit_info.get("author") or None
        return self._check_response(
            current_version=current_hash,
            update_available=update_available,
            available_version=available,
            release_notes="Release notes available after staging." if update_available else "",
            last_update=last_update,
            available_since=available_since,
            available_commit_message=available_commit_message,
            available_commit_author=available_commit_author,
            files_changed=files_changed[:200],
            branch=branch,
            root_dir=root_dir,
            repo=repo,
        )

    def _manual_update_command(
        self, root_dir: Path, repo: str, branch: str, target_version: str
    ) -> Optional[str]:
        """Build the command to run manually via SSH when in-app update fails (e.g. permissions)."""
        script = root_dir / "bin" / "apply-update.sh"
        if not script.exists():
            return None
        return f'sudo {script} "{repo}" {branch} {root_dir} {self._version_file} {target_version}'

    def _check_response(
        self,
        *,
        current_version: str,
        update_available: bool,
        available_version: str,
        release_notes: str,
        last_update: Optional[str],
        files_changed: list[str],
        branch: str,
        available_since: Optional[str] = None,
        available_commit_message: Optional[str] = None,
        available_commit_author: Optional[str] = None,
        root_dir: Optional[Path] = None,
        repo: Optional[str] = None,
    ) -> Dict[str, object]:
        """Build the standard check_for_updates response dict."""
        out: Dict[str, object] = {
            "current_version": current_version,
            "update_available": update_available,
            "available_version": available_version,
            "release_notes": release_notes,
            "last_update": last_update,
            "available_since": available_since,
            "available_commit_message": available_commit_message,
            "available_commit_author": available_commit_author,
            "files_changed": files_changed,
            "update_branch": branch,
        }
        if update_available and root_dir and repo and available_version:
            cmd = self._manual_update_command(root_dir, repo, branch, available_version)
            if cmd:
                out["manual_update_command"] = cmd
        return out

    def apply_update(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, object]:
        def emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        update_info = self.check_for_updates()
        emit("Checking for updates...")
        if not update_info.get("update_available"):
            emit("No update available. You're up to date.")
            return {"status": "up_to_date", "current_version": update_info["current_version"]}
        emit(f"Update available: {update_info.get('available_version', '')[:7]} (target).")
        emit("Creating pre-update config backup...")
        backup_path = self.create_config_backup(label="pre-update")
        emit(f"Backup created: {backup_path.name}")
        previous_version = _current_version(self._version_file)
        target_version = str(update_info.get("available_version") or previous_version)
        state = UpdateState(
            previous_version=previous_version,
            backup_path=str(backup_path),
            applied_at=_timestamp(),
            target_version=target_version,
        )
        self._write_state(state)
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            emit("Dry run: update not applied (set RPI_ENGINEER_DRY_RUN=0 to apply).")
            return {
                "status": "applied",
                "dry_run": True,
                "previous_version": previous_version,
                "current_version": target_version,
                "backup_path": str(backup_path),
            }
        try:
            emit("Applying update (git fetch + reset)...")
            self._perform_update(target_version, progress_callback=progress_callback)
            emit("Update applied. Re-applying web permissions if needed...")
        except Exception as exc:
            emit(f"Update failed: {exc}")
            emit("Attempting rollback...")
            try:
                self.rollback_update()
                emit("Rollback completed.")
            except Exception as rollback_exc:
                logger.warning("Rollback failed after update error: %s", rollback_exc)
                emit(f"Rollback failed: {rollback_exc}")
                raise RuntimeError(
                    f"Update failed: {exc}. Rollback could not complete: {rollback_exc}"
                ) from exc
            raise RuntimeError(f"Update failed; rollback attempted: {exc}") from exc
        emit("Done.")
        logger.info("Update applied: %s -> %s", previous_version[:7] if previous_version else previous_version, target_version[:7] if target_version else target_version)
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

    def run_reinstall_from_scratch(self) -> Dict[str, object]:
        """Run install script in reinstall_from_scratch mode: remove app dir, then full install using existing install.conf. Requires root."""
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        install_script = root_dir / "bin" / "install.sh"
        if not install_script.exists():
            raise RuntimeError("Install script not found; run reinstall from the device where the app is installed.")
        if os.getenv("RPI_ENGINEER_DRY_RUN", "1") == "1":
            return {
                "status": "reinstall_dry_run",
                "message": "Reinstall from scratch would run install.sh with INSTALL_MODE=reinstall_from_scratch. Set RPI_ENGINEER_DRY_RUN=0 to run.",
            }
        env = {**os.environ, "NONINTERACTIVE": "1", "INSTALL_MODE": "reinstall_from_scratch"}
        try:
            result = subprocess.run(
                ["sudo", str(install_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Reinstall from scratch timed out after 10 minutes.") from None
        except FileNotFoundError:
            raise RuntimeError("sudo or install script not found.") from None
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or (result.stdout or "").strip()
            raise RuntimeError(f"Reinstall from scratch failed (exit {result.returncode}): {stderr[:500]}")
        return {
            "status": "reinstalled",
            "message": "Reinstall from scratch complete. Reboot recommended.",
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
        self._version_file = _write_version(self._version_file, self._data_dir, state.previous_version)
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

        # Prefer sudo script so root can read all config (e.g. remote_access.conf); avoids [Errno 13] Permission denied
        script = self._repo_root / "bin" / "create-config-backup.sh"
        if script.exists():
            try:
                proc = subprocess.run(
                    [
                        "sudo",
                        str(script),
                        str(backup_path),
                        str(self._config_dir),
                        str(self._data_dir),
                        label,
                        _current_version(self._version_file),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                if proc.returncode == 0 and backup_path.exists():
                    return backup_path
            except (OSError, subprocess.TimeoutExpired):
                pass

        # Fallback: create backup in-process; skip unreadable files (e.g. root-only config)
        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = {
                "version": "1.0",
                "created": _timestamp(),
                "label": label,
                "source_version": _current_version(self._version_file),
                "includes": ["config", "data"],
                "excludes": excludes,
            }
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            if self._config_dir.exists():
                _add_dir_to_archive(
                    archive, self._config_dir, Path("config"), exclude_names=[]
                )
            if self._data_dir.exists():
                _add_dir_to_archive(
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
                _restore_tree(config_root, self._config_dir)
            else:
                _restore_tree(extracted, self._config_dir, skip_manifest=True)
            if data_root.exists():
                _restore_tree(data_root, self._data_dir)
        return {
            "restored": True,
            "config_dir": str(self._config_dir),
            "data_dir": str(self._data_dir),
        }

    def _current_version(self) -> str:
        return _current_version(self._version_file)

    def _write_version(self, version: str) -> None:
        self._version_file = _write_version(self._version_file, self._data_dir, version)

    def _write_state(self, state: UpdateState) -> None:
        payload = {
            "previous_version": state.previous_version,
            "backup_path": state.backup_path,
            "applied_at": state.applied_at,
            "target_version": state.target_version,
        }
        text = json.dumps(payload, indent=2)
        for path in (self._state_file, self._state_file_fallback, self._state_file_temp):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                self._state_file = path
                if path == self._state_file_temp:
                    logger.info("Update state written to temp dir (data dirs not writable): %s", path)
                return
            except OSError as e:
                if path == self._state_file_temp:
                    raise RuntimeError(
                        f"Cannot write update state to {self._state_file}, {self._state_file_fallback}, or {path}: {e}"
                    ) from e
                logger.warning("Cannot write update state to %s (%s), trying fallback", path, e)

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
        for path in (self._state_file, self._state_file_fallback, self._state_file_temp):
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text())
                self._state_file = path
                return UpdateState(
                    previous_version=payload.get("previous_version", ""),
                    backup_path=payload.get("backup_path", ""),
                    applied_at=payload.get("applied_at", ""),
                    target_version=payload.get("target_version", ""),
                )
            except (OSError, json.JSONDecodeError):
                if path == self._state_file_temp:
                    return None
                continue
        return None

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

    def _perform_update(
        self,
        target_version: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        def emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        repo = os.getenv("RPI_ENGINEER_UPDATE_REPO", DEFAULT_UPDATE_REPO)
        branch = os.getenv("RPI_ENGINEER_UPDATE_BRANCH", DEFAULT_UPDATE_BRANCH)
        root_dir = Path(os.getenv("RPI_ENGINEER_ROOT", "/opt/rpi-engineer"))
        if (root_dir / ".git").is_dir():
            script = root_dir / "bin" / "apply-update.sh"
            ran_sudo_ok = False
            if script.exists():
                try:
                    emit("Running apply-update.sh (sudo)...")
                    proc = subprocess.run(
                        [
                            "sudo",
                            str(script),
                            repo,
                            branch,
                            str(root_dir),
                            str(self._version_file),
                            target_version,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                    if proc.returncode == 0:
                        ran_sudo_ok = True
                        if proc.stdout and proc.stdout.strip():
                            for line in proc.stdout.strip().splitlines():
                                emit(line)
                        emit("apply-update.sh completed.")
                    else:
                        err = (proc.stderr or "").strip() or (proc.stdout or "").strip()
                        if _sudo_unavailable_message(err):
                            emit("sudo unavailable (e.g. container), trying without sudo...")
                            logger.warning(
                                "sudo unavailable (e.g. container no-new-privileges), attempting update without sudo: %s",
                                err[:200],
                            )
                        else:
                            raise RuntimeError(err or "apply-update.sh failed")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    err = str(exc)
                    if _sudo_unavailable_message(err):
                        emit("sudo failed, trying git in-process...")
                        logger.warning(
                            "sudo failed (e.g. container), attempting update without sudo: %s",
                            err,
                        )
                    else:
                        raise RuntimeError(f"Git update failed: {exc}") from exc
            if not ran_sudo_ok:
                safe_dir = _git_safe_dir(root_dir)
                try:
                    emit("Setting remote origin...")
                    remote = subprocess.run(
                        ["git", *safe_dir, "remote", "get-url", "origin"],
                        cwd=root_dir,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if remote.returncode != 0:
                        subprocess.run(
                            ["git", *safe_dir, "remote", "add", "origin", repo],
                            cwd=root_dir,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    else:
                        subprocess.run(
                            ["git", *safe_dir, "remote", "set-url", "origin", repo],
                            cwd=root_dir,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                    emit("Fetching from origin...")
                    fetch = subprocess.run(
                        ["git", *safe_dir, "fetch", "origin", branch],
                        cwd=root_dir,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )
                    if fetch.returncode != 0:
                        err = (fetch.stderr or "").strip() or (fetch.stdout or "").strip()
                        if "Permission denied" in err or "FETCH_HEAD" in err:
                            raise RuntimeError(
                                "Repository directory is not writable by this user (e.g. .git owned by root). "
                                "Run updates with sudo, or install to a directory owned by the service user."
                            ) from None
                        raise RuntimeError(err or "git fetch failed")
                    emit("Resetting to origin/" + branch + "...")
                    reset = subprocess.run(
                        ["git", *safe_dir, "reset", "--hard", f"origin/{branch}"],
                        cwd=root_dir,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if reset.returncode != 0:
                        err = (reset.stderr or "").strip() or (reset.stdout or "").strip()
                        if "Permission denied" in err or "unable to unlink" in err:
                            raise RuntimeError(
                                "Repository directory is not writable by this user (files owned by root or another user). "
                                "Run the update manually via SSH with the command shown in the Updates page, or make the "
                                "install directory writable by the API user (chmod -R g+w, add user to group). "
                                "See docs/troubleshooting/common-issues.html for details."
                            ) from None
                        raise RuntimeError(err or "git reset failed")
                    emit("Writing version file...")
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise RuntimeError(f"Git update failed: {exc}") from exc
                self._version_file = _write_version(self._version_file, self._data_dir, target_version)
            emit("Applying web permissions...")
            self._apply_web_permissions(root_dir)
            return

        emit("Not a git repo; cloning to staging...")
        staging_dir = self._staging_dir / "update"
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo, str(staging_dir)],
            check=True,
        )
        emit("Copying files to install directory...")
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
        self._version_file = _write_version(self._version_file, self._data_dir, target_version)
        emit("Applying web permissions...")
        self._apply_web_permissions(root_dir)


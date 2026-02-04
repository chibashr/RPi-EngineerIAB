from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Optional


def _is_hash(value: str) -> bool:
    return bool(value) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _git_blob_sha(content: bytes) -> str:
    """Compute git blob object SHA1 (blob {size}\\0{content})."""
    blob = b"blob " + str(len(content)).encode() + b"\0" + content
    return hashlib.sha1(blob).hexdigest()


def _git_safe_dir(repo_dir: Path) -> list[str]:
    """Git 2.35.2+ dubious ownership: allow repo_dir when run by non-owner (e.g. service user)."""
    return ["-c", f"safe.directory={repo_dir}"]


def _check_updates_via_git(
    repo_dir: Path, repo: str, branch: str, core_dirs: tuple[str, ...]
) -> Optional[tuple[str, str, list[str]]]:
    """Run a git-pull–style check: fetch origin, compare HEAD to origin/branch, list differing files."""
    if not repo_dir.is_dir() or not (repo_dir / ".git").is_dir():
        return None
    safe = _git_safe_dir(repo_dir)
    try:
        r = subprocess.run(
            ["git", *safe, "remote", "get-url", "origin"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            subprocess.run(
                ["git", *safe, "remote", "add", "origin", repo],
                cwd=repo_dir,
                capture_output=True,
                check=False,
            )
        else:
            subprocess.run(
                ["git", *safe, "remote", "set-url", "origin", repo],
                cwd=repo_dir,
                capture_output=True,
                check=False,
            )
        fetch = subprocess.run(
            ["git", *safe, "fetch", "origin", branch],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if fetch.returncode != 0:
            return None
        local_ref = subprocess.run(
            ["git", *safe, "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if local_ref.returncode != 0:
            return None
        local_hash = local_ref.stdout.strip()
        if not _is_hash(local_hash):
            return None
        remote_ref = subprocess.run(
            ["git", *safe, "rev-parse", f"origin/{branch}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if remote_ref.returncode != 0:
            return None
        remote_hash = remote_ref.stdout.strip()
        if not _is_hash(remote_hash):
            return None
        diff = subprocess.run(
            ["git", *safe, "diff", "--name-only", "HEAD", f"origin/{branch}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        files_changed: list[str] = []
        if diff.returncode == 0 and diff.stdout:
            for line in diff.stdout.strip().splitlines():
                path = line.strip().replace("\\", "/")
                if not path:
                    continue
                top = path.split("/")[0] if "/" in path else path
                if top in core_dirs:
                    files_changed.append(path)
        return (local_hash, remote_hash, files_changed)
    except (OSError, subprocess.TimeoutExpired):
        return None

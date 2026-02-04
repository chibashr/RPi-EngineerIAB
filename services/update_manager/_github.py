from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Dict, Optional

from ._git import _is_hash


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
    info = _github_commit_info(repo_slug, commit_hash)
    return info.get("date") if info else None


def _github_commit_info(repo_slug: str, commit_hash: str) -> Optional[Dict[str, str]]:
    """Fetch commit date, message, and author from GitHub API. Returns None on any failure."""
    if not _is_hash(commit_hash):
        return None
    url = f"https://api.github.com/repos/{repo_slug}/commits/{commit_hash}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        commit = data.get("commit") or {}
        author = commit.get("author") or {}
        return {
            "date": author.get("date") or "",
            "message": (commit.get("message") or "").strip(),
            "author": author.get("name") or commit.get("author", {}).get("name") or "",
        }
    except Exception:
        return None


def _github_tree_blobs(
    repo_slug: str, commit_ref: str, core_dirs: tuple[str, ...]
) -> Optional[list[tuple[str, str]]]:
    """Fetch recursive tree for commit; return list of (path, blob_sha) for type blob under core dirs."""
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
            if top not in core_dirs:
                continue
            blobs.append((path, node.get("sha") or ""))
        return blobs
    except Exception:
        return None

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from lib.module_logger import get_service_logger

logger = get_service_logger(__name__)


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


def _add_dir_to_archive(
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
        try:
            archive.write(path, prefix / rel)
        except OSError as e:
            logger.warning("Skipping unreadable file in backup: %s (%s)", path, e)


def _restore_tree(source: Path, target_root: Path, skip_manifest: bool = False) -> None:
    """Restore files from source to target_root; skip files that fail with permission errors."""
    for path in source.rglob("*"):
        if skip_manifest and path.name == "manifest.json":
            continue
        relative = path.relative_to(source)
        target = target_root / relative
        try:
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        except OSError as e:
            logger.warning("Skipping restore of %s to %s: %s", path, target, e)

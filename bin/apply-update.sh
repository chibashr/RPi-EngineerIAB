#!/usr/bin/env bash
# Apply in-app update: git fetch + reset in the install repo and write version file.
# Run as root; invoked by the update manager via sudo so the service user can update.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
fi

REPO="${1:?Missing repo URL}"
BRANCH="${2:?Missing branch}"
ROOT_DIR="${3:?Missing root dir}"
VERSION_FILE="${4:?Missing version file path}"
TARGET_VERSION="${5:?Missing target version}"

if [ ! -d "$ROOT_DIR/.git" ]; then
    echo "Not a git repository: $ROOT_DIR" >&2
    exit 1
fi

cd "$ROOT_DIR"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REPO"
git remote set-url origin "$REPO"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

mkdir -p "$(dirname "$VERSION_FILE")"
printf '%s' "$TARGET_VERSION" > "$VERSION_FILE"

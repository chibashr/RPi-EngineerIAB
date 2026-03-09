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

# Ensure git allows this repo (dubious ownership when run as root on root:group dir)
git config --system --add safe.directory "$ROOT_DIR" 2>/dev/null || true

cd "$ROOT_DIR"
git remote get-url origin >/dev/null 2>&1 || git remote add origin "$REPO"
git remote set-url origin "$REPO"
git fetch origin "$BRANCH"
# Show diffs on branch so user can verify what is being updated
if git rev-parse "origin/$BRANCH" >/dev/null 2>&1; then
    echo "--- Changes on branch $BRANCH (HEAD..origin/$BRANCH) ---"
    git log --oneline HEAD.."origin/$BRANCH" 2>/dev/null || true
    git diff --stat HEAD.."origin/$BRANCH" 2>/dev/null || true
    git diff HEAD.."origin/$BRANCH" 2>/dev/null || true
    echo "--- End of diff ---"
fi
git reset --hard "origin/$BRANCH"

mkdir -p "$(dirname "$VERSION_FILE")"
printf '%s' "$TARGET_VERSION" > "$VERSION_FILE"

# Ensure install dir owned by rpi-engineer so in-app updates work when sudo is unavailable next time
SERVICE_USER="${RPI_ENGINEER_SERVICE_USER:-rpi-engineer}"
SERVICE_GROUP="${RPI_ENGINEER_SERVICE_GROUP:-rpi-engineer}"
if getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$ROOT_DIR"
    chmod -R g+w "$ROOT_DIR" 2>/dev/null || true
fi

# Re-apply web permissions (web dir -> www-data for nginx, nginx config, etc.)
# Must run here because we restart the API below, which kills the update manager before it can call apply-web-permissions
APPLY_WEB="$ROOT_DIR/bin/apply-web-permissions.sh"
if [ -x "$APPLY_WEB" ]; then
    "$APPLY_WEB" >> /tmp/rpi-engineer-apply-web.log 2>&1 || true
fi

# Restart services so they pick up the new code
if [ -d /run/systemd/system ]; then
    systemctl restart rpi-engineer rpi-engineer-api rpi-engineer-network rpi-engineer-serial \
        rpi-engineer-capture rpi-engineer-system rpi-engineer-monitor rpi-engineer-update \
        rpi-engineer-logging 2>/dev/null || true
fi

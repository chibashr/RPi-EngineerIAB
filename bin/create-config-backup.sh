#!/usr/bin/env bash
# Create config backup archive (config + data dirs) for pre-update backup.
# Run as root; invoked by the update manager via sudo so all config files (e.g. remote_access.conf) are readable.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
fi

BACKUP_PATH="${1:?Missing backup path}"
CONFIG_DIR="${2:?Missing config dir}"
DATA_DIR="${3:?Missing data dir}"
LABEL="${4:-config}"
SOURCE_VERSION="${5:-}"

# Exclude same dirs as UpdateManager.create_config_backup
DATA_EXCLUDES=(captures serial_logs logs tmp backups exports)

CREATED=$(date -u +%Y-%m-%dT%H:%M:%S+00:00)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/config" "$TMP/data"
cat > "$TMP/manifest.json" <<EOF
{
  "version": "1.0",
  "created": "$CREATED",
  "label": "$LABEL",
  "source_version": "$SOURCE_VERSION",
  "includes": ["config", "data"],
  "excludes": ["captures", "serial_logs", "logs", "tmp", "backups", "exports"]
}
EOF

if [ -d "$CONFIG_DIR" ]; then
    cp -a "$CONFIG_DIR"/* "$TMP/config/" 2>/dev/null || true
fi

if [ -d "$DATA_DIR" ]; then
    for excl in "${DATA_EXCLUDES[@]}"; do
        [ -d "$DATA_DIR/$excl" ] && rm -rf "$TMP/data/$excl" 2>/dev/null || true
    done
    for item in "$DATA_DIR"/*; do
        [ -e "$item" ] || continue
        name=$(basename "$item")
        for excl in "${DATA_EXCLUDES[@]}"; do
            [ "$name" = "$excl" ] && continue 2
        done
        cp -a "$item" "$TMP/data/" 2>/dev/null || true
    done
fi

# Ensure parent dir exists and is writable by service user after we create the zip
mkdir -p "$(dirname "$BACKUP_PATH")"
(cd "$TMP" && zip -r -q "$BACKUP_PATH" .)
chmod 644 "$BACKUP_PATH"
echo "$BACKUP_PATH"

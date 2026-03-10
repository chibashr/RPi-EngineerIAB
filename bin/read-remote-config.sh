#!/usr/bin/env bash
# Output remote_access.conf for the API when it cannot read the file (e.g. root-only).
# Run as root (e.g. sudo). Used by RemoteAccessManager as fallback.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

CONFIG_FILE="${RPI_ENGINEER_CONFIG_DIR:-/etc/rpi-engineer}/remote_access.conf"
if [ -f "$CONFIG_FILE" ]; then
  cat "$CONFIG_FILE"
else
  echo "{}"
fi

#!/usr/bin/env bash
# Standalone uninstall: invokes install script with uninstall mode.
# Usage: sudo ./bin/uninstall.sh
# For non-interactive (remove data/logs): sudo NONINTERACTIVE=1 RPI_ENGINEER_REMOVE_DATA=1 ./bin/uninstall.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
INSTALL_SCRIPT="${SCRIPT_DIR}/install.sh"

if [ ! -f "$INSTALL_SCRIPT" ]; then
    echo "install.sh not found. Run from repo root or ensure bin/install.sh exists." >&2
    exit 1
fi

# When RPI_ENGINEER_REMOVE_DATA=1, uninstall removes data and logs without prompting
export INSTALL_MODE=uninstall
export NONINTERACTIVE="${NONINTERACTIVE:-0}"
export RPI_ENGINEER_REMOVE_DATA="${RPI_ENGINEER_REMOVE_DATA:-0}"
[ "$RPI_ENGINEER_REMOVE_DATA" = "1" ] && export NONINTERACTIVE=1

exec bash "$INSTALL_SCRIPT"

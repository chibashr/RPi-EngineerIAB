#!/usr/bin/env bash
# Verify that RPi Engineer permissions are correctly applied (tcpdump, sudoers, install/config dirs).
# Run as root (or sudo). Exit 0 if all critical checks pass, 1 otherwise.
# Usage: sudo /opt/rpi-engineer/bin/verify-permissions.sh
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${RPI_ENGINEER_CONFIG_DIR:-/etc/rpi-engineer}"
SERVICE_USER="rpi-engineer"
SERVICE_GROUP="rpi-engineer"

FAIL=0

check() {
    local name="$1" ok="$2" msg="${3:-}"
    if [ "$ok" = "yes" ]; then
        echo "OK   $name"
    else
        echo "FAIL $name${msg:+: $msg}"
        FAIL=1
    fi
}

# 1. tcpdump capabilities (packet capture without root; API uses tcpdump)
TCPDUMP="$(command -v tcpdump 2>/dev/null)"
if [ -z "$TCPDUMP" ]; then
    check "tcpdump present" "no" "install tcpdump for packet capture"
else
    CAPS="$(getcap "$TCPDUMP" 2>/dev/null || true)"
    # Accept capabilities in any order (cap_net_raw,cap_net_admin or cap_net_admin,cap_net_raw)
    if echo "$CAPS" | grep -q "cap_net_raw" && echo "$CAPS" | grep -q "cap_net_admin"; then
        check "tcpdump capabilities" "yes"
    else
        check "tcpdump capabilities" "no" "run: sudo setcap cap_net_raw,cap_net_admin=eip $TCPDUMP (or sudo $INSTALL_DIR/bin/apply-web-permissions.sh)"
    fi
fi

# 2. Sudoers rules (web user can run apply-update, apply-web-permissions, create-config-backup)
for name in apply-web-permissions apply-update create-config-backup; do
    SUDOERS_FILE="/etc/sudoers.d/rpi-engineer-$name"
    SCRIPT="$INSTALL_DIR/bin/${name}.sh"
    if [ -f "$SUDOERS_FILE" ] && [ -f "$SCRIPT" ]; then
        if grep -q "$SERVICE_USER ALL=(root) NOPASSWD: $SCRIPT" "$SUDOERS_FILE" 2>/dev/null; then
            check "sudoers $name" "yes"
        else
            check "sudoers $name" "no" "expected $SERVICE_USER NOPASSWD: $SCRIPT"
        fi
    else
        [ ! -f "$SUDOERS_FILE" ] && check "sudoers $name" "no" "missing $SUDOERS_FILE"
        [ ! -f "$SCRIPT" ] && check "sudoers $name" "no" "missing $SCRIPT"
    fi
done

# 3. Install dir owned by service user (updates from web UI)
if [ -d "$INSTALL_DIR" ]; then
    OWNER="$(stat -c "%U" "$INSTALL_DIR" 2>/dev/null || true)"
    if [ "$OWNER" = "$SERVICE_USER" ]; then
        check "install dir ownership" "yes"
    else
        check "install dir ownership" "no" "chown -R $SERVICE_USER:$SERVICE_GROUP $INSTALL_DIR"
    fi
else
    check "install dir exists" "no" "$INSTALL_DIR"
fi

# 4. Config version file writable by group (version file for updates)
if [ -f "$CONFIG_DIR/version" ]; then
    VMODE="$(stat -c "%a %G" "$CONFIG_DIR/version" 2>/dev/null || true)"
    VNUM="${VMODE%% *}"
    VG_BIT=$(( VNUM / 10 % 10 )) 2>/dev/null || VG_BIT=0
    if [ "${VG_BIT:-0}" -ge 2 ] 2>/dev/null; then
        check "config/version writable by group" "yes"
    else
        check "config/version writable by group" "no" "chown root:$SERVICE_GROUP $CONFIG_DIR/version; chmod 664 $CONFIG_DIR/version"
    fi
else
    check "config/version writable by group" "yes"
fi

# 5. Capture dir exists and writable by group (/var/lib/rpi-engineer/captures)
DATA_DIR="${RPI_ENGINEER_DATA_DIR:-/var/lib/rpi-engineer}"
CAPTURES_DIR="$DATA_DIR/captures"
mkdir -p "$CAPTURES_DIR" 2>/dev/null || true
if [ -d "$CAPTURES_DIR" ]; then
    STAT="$(stat -c "%a %G" "$CAPTURES_DIR" 2>/dev/null || true)"
    CMODE="${STAT%% *}"
    CGRP="${STAT#* }"
    C_BIT=$(( CMODE / 10 % 10 ))
    if [ "$CGRP" = "$SERVICE_GROUP" ] && [ "$C_BIT" -ge 2 ] 2>/dev/null; then
        check "captures dir" "yes"
    else
        check "captures dir" "no" "chown -R $SERVICE_USER:$SERVICE_GROUP $CAPTURES_DIR; chmod -R 775 $CAPTURES_DIR"
    fi
else
    check "captures dir" "no" "mkdir -p $CAPTURES_DIR"
fi

# 6. Service user exists and is in dialout (serial)
if getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
    if id -nG "$SERVICE_USER" 2>/dev/null | grep -q dialout; then
        check "service user in dialout" "yes"
    else
        check "service user in dialout" "no" "usermod -a -G dialout $SERVICE_USER (for serial console)"
    fi
else
    check "service user exists" "no" "user $SERVICE_USER not found"
fi

if [ "$FAIL" -eq 1 ]; then
    echo ""
    echo "Some checks failed. Re-apply permissions: sudo $INSTALL_DIR/bin/apply-web-permissions.sh"
    echo "Or re-run the installer (Upgrade) to fix all permissions."
    exit 1
fi
echo ""
echo "All permission checks passed."
exit 0

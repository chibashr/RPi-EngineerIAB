#!/usr/bin/env bash
# Verify that RPi Engineer permissions are correctly applied (dumpcap, sudoers, install/config dirs).
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

# 1. dumpcap capabilities (packet capture without root)
DUMPCAP="$(command -v dumpcap 2>/dev/null)"
if [ -z "$DUMPCAP" ]; then
    check "dumpcap present" "no" "install tshark/wireshark-common for packet capture"
else
    CAPS="$(getcap "$DUMPCAP" 2>/dev/null || true)"
    if echo "$CAPS" | grep -q "cap_net_raw.*cap_net_admin"; then
        check "dumpcap capabilities" "yes"
    else
        check "dumpcap capabilities" "no" "run: sudo setcap cap_net_raw,cap_net_admin=eip $DUMPCAP (or sudo $INSTALL_DIR/bin/apply-web-permissions.sh)"
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

# 3. Install dir group-writable (updates from web UI)
if [ -d "$INSTALL_DIR" ]; then
    STAT="$(stat -c "%a %G" "$INSTALL_DIR" 2>/dev/null || true)"
    MODE="${STAT%% *}"
    GRP="${STAT#* }"
    G_BIT=$((MODE / 10 % 10))
    if [ "$GRP" = "$SERVICE_GROUP" ] && [ "$G_BIT" -ge 2 ] 2>/dev/null; then
        check "install dir group writable" "yes"
    else
        check "install dir group writable" "no" "chown root:$SERVICE_GROUP $INSTALL_DIR; chmod -R g+w $INSTALL_DIR"
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

# 5. Data/captures dir exists and writable by group
CAPTURES_DIR="$INSTALL_DIR/data/captures"
if [ -d "$INSTALL_DIR/data" ]; then
    mkdir -p "$CAPTURES_DIR" 2>/dev/null || true
    if [ -d "$CAPTURES_DIR" ]; then
        STAT="$(stat -c "%a %G" "$CAPTURES_DIR" 2>/dev/null || true)"
        CMODE="${STAT%% *}"
        CGRP="${STAT#* }"
        C_BIT=$(( CMODE / 10 % 10 ))
        if [ "$CGRP" = "$SERVICE_GROUP" ] && [ "$C_BIT" -ge 2 ] 2>/dev/null; then
            check "data/captures dir" "yes"
        else
            check "data/captures dir" "no" "chown -R root:$SERVICE_GROUP $INSTALL_DIR/data; chmod -R 775 $INSTALL_DIR/data"
        fi
    else
        check "data/captures dir" "no" "mkdir -p $CAPTURES_DIR"
    fi
else
    check "data/captures dir" "no" "install dir data missing"
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

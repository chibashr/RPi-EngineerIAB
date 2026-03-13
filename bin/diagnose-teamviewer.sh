#!/usr/bin/env bash
# Diagnose TeamViewer ID retrieval issues
# Run as: sudo bash bin/diagnose-teamviewer.sh
# Or as the rpi-engineer user to test sudoers

set -euo pipefail

echo "=== TeamViewer Diagnostic ==="
echo

# 1. Check if teamviewer is installed
echo "1. Checking TeamViewer installation..."
if command -v teamviewer >/dev/null 2>&1; then
    TEAMVIEWER_PATH="$(command -v teamviewer)"
    echo "   Found: $TEAMVIEWER_PATH"
else
    echo "   ERROR: teamviewer command not found"
    exit 1
fi

# 2. Check if teamviewerd is running
echo
echo "2. Checking TeamViewer daemon..."
if pgrep -x teamviewerd >/dev/null 2>&1; then
    echo "   teamviewerd is running"
else
    echo "   WARNING: teamviewerd is NOT running"
    echo "   Try: sudo systemctl start teamviewerd"
fi

# 3. Check sudoers rules
echo
echo "3. Checking sudoers rules..."
if [ -f /etc/sudoers.d/rpi-engineer ]; then
    echo "   /etc/sudoers.d/rpi-engineer exists"
    if grep -q "teamviewer info" /etc/sudoers.d/rpi-engineer 2>/dev/null; then
        echo "   Has 'teamviewer info' rule"
    else
        echo "   MISSING: 'teamviewer info' rule"
    fi
    if grep -q "teamviewer passwd" /etc/sudoers.d/rpi-engineer 2>/dev/null; then
        echo "   Has 'teamviewer passwd' rule"
    else
        echo "   MISSING: 'teamviewer passwd' rule"
    fi
else
    echo "   WARNING: /etc/sudoers.d/rpi-engineer does not exist"
    echo "   Run the installer to create it"
fi

# 4. Test teamviewer info without sudo
echo
echo "4. Testing 'teamviewer info' (without sudo)..."
echo "   Output:"
teamviewer info 2>&1 | head -20 | sed 's/^/   /'
echo

# 5. Test teamviewer info with sudo
echo
echo "5. Testing 'sudo teamviewer info'..."
echo "   Output:"
if sudo teamviewer info 2>&1 | head -20 | sed 's/^/   /'; then
    echo
else
    echo "   ERROR: sudo teamviewer info failed"
    echo "   This may require passwordless sudo. Check /etc/sudoers.d/rpi-engineer"
fi

# 6. Try to extract ID
echo
echo "6. Attempting to extract TeamViewer ID..."
OUTPUT="$(sudo teamviewer info 2>&1 || true)"
if echo "$OUTPUT" | grep -qi "TeamViewer ID"; then
    ID_LINE="$(echo "$OUTPUT" | grep -i "TeamViewer ID" | head -1)"
    echo "   Found line: $ID_LINE"
    ID="$(echo "$ID_LINE" | sed -n 's/.*TeamViewer[[:space:]]*ID[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/ip')"
    if [ -n "$ID" ]; then
        echo "   Extracted ID: $ID"
    else
        echo "   WARNING: Could not extract numeric ID from line"
    fi
else
    echo "   WARNING: No 'TeamViewer ID' found in output"
    echo "   Full output:"
    echo "$OUTPUT" | sed 's/^/   /'
fi

# 7. Check password file
echo
echo "7. Checking password file..."
PW_FILE="/etc/rpi-engineer/teamviewer_password"
if [ -f "$PW_FILE" ]; then
    echo "   $PW_FILE exists"
    echo "   Permissions: $(stat -c '%a' "$PW_FILE")"
    echo "   Owner: $(stat -c '%U:%G' "$PW_FILE")"
else
    echo "   $PW_FILE does not exist (no password set yet)"
fi

# 8. Check remote_access.conf
echo
echo "8. Checking remote_access.conf..."
CONF_FILE="/etc/rpi-engineer/remote_access.conf"
if [ -f "$CONF_FILE" ]; then
    echo "   $CONF_FILE exists"
    if command -v jq >/dev/null 2>&1; then
        echo "   TeamViewer section:"
        jq '.teamviewer // "not found"' "$CONF_FILE" 2>/dev/null | sed 's/^/   /' || echo "   (could not parse)"
    fi
else
    echo "   $CONF_FILE does not exist"
fi

echo
echo "=== Diagnostic Complete ==="
echo
echo "If 'teamviewer info' shows the ID but sudo version doesn't, add to /etc/sudoers.d/rpi-engineer:"
echo "  rpi-engineer ALL=(root) NOPASSWD: $TEAMVIEWER_PATH info"
echo "  rpi-engineer ALL=(root) NOPASSWD: $TEAMVIEWER_PATH passwd *"

#!/usr/bin/env bash
# Set unattended password for AnyDesk or TeamViewer and update remote_access.conf.
# Run as root (e.g. sudo). Password via --password-file PATH (preferred) or stdin.
# Usage: sudo bin/set-remote-password.sh --password-file /path/to/file anydesk
#        echo -n "newpassword" | sudo bin/set-remote-password.sh anydesk
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (use sudo)." >&2
  exit 1
fi

PASSWORD_FILE=""
TOOL=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --password-file)
      PASSWORD_FILE="${2:-}"
      shift 2
      ;;
    anydesk|teamviewer)
      TOOL="$1"
      shift
      break
      ;;
    *)
      echo "Usage: $0 [--password-file PATH] anydesk|teamviewer" >&2
      exit 1
      ;;
  esac
done

if [ "$TOOL" != "anydesk" ] && [ "$TOOL" != "teamviewer" ]; then
  echo "Usage: $0 [--password-file PATH] anydesk|teamviewer" >&2
  exit 1
fi

PASSWORD=""
if [ -n "$PASSWORD_FILE" ] && [ -f "$PASSWORD_FILE" ]; then
  PASSWORD="$(cat "$PASSWORD_FILE")"
  rm -f "$PASSWORD_FILE"
elif [ -n "$PASSWORD_FILE" ]; then
  echo "Password file not found or not readable." >&2
  exit 1
else
  while IFS= read -r line; do
    PASSWORD="$line"
    break
  done
fi
if [ -z "$PASSWORD" ]; then
  echo "No password read from stdin." >&2
  exit 1
fi

CONFIG_DIR="${RPI_ENGINEER_CONFIG_DIR:-/etc/rpi-engineer}"
CONFIG_FILE="$CONFIG_DIR/remote_access.conf"

have_timeout() {
  command -v timeout >/dev/null 2>&1
}

case "$TOOL" in
  anydesk)
    if command -v anydesk >/dev/null 2>&1; then
      if have_timeout; then
        echo "$PASSWORD" | timeout 12s anydesk --set-password 2>/dev/null || true
      else
        echo "$PASSWORD" | anydesk --set-password 2>/dev/null || true
      fi
    fi
    ;;
  teamviewer)
    if command -v teamviewer >/dev/null 2>&1; then
      if have_timeout; then
        timeout 12s teamviewer passwd "$PASSWORD" 2>/dev/null || true
      else
        teamviewer passwd "$PASSWORD" 2>/dev/null || true
      fi
    fi
    ;;
esac

# Update config so the UI can show the password
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
  jq --arg tool "$TOOL" --arg pass "$PASSWORD" \
    'if $tool == "anydesk" then .anydesk.password = $pass
     elif $tool == "teamviewer" then .teamviewer.password = $pass
     else . end' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
else
  # Create minimal config if missing (use jq to escape password safely)
  if [ ! -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    if [ "$TOOL" = "anydesk" ]; then
      echo '{"anydesk":{},"teamviewer":{}}' | jq --arg pass "$PASSWORD" '.anydesk.password = $pass' > "$CONFIG_FILE" 2>/dev/null || true
    else
      echo '{"anydesk":{},"teamviewer":{}}' | jq --arg pass "$PASSWORD" '.teamviewer.password = $pass' > "$CONFIG_FILE" 2>/dev/null || true
    fi
  fi
fi
exit 0

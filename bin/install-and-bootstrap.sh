#!/usr/bin/env bash

set -euo pipefail

# One-shot installer + bootstrapper for RPi Engineer-in-a-Box.
# - Installs RPi Engineer using the official install.sh
# - Waits for the API to come up
# - Configures WAN (e.g. eth1 Jetpack) via the RPi Engineer API
# - Configures the WiFi hotspot via the RPi Engineer API
#
# Usage (from a fresh Pi, as root):
#   curl -fsSL https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install-and-bootstrap.sh | sudo bash
#
# Tunables (override via environment variables before running):
#   RPI_ENGINEER_INSTALL_URL      - URL for bin/install.sh (when using curl | bash)
#   RPI_ENGINEER_REPO_ARCHIVE_URL - URL of repo archive tarball. Use a mirror if GitHub is unreachable.
#   RPI_ENGINEER_REPO_ARCHIVE_TOP - Top-level dir inside the tarball (default RPi-EngineerIAB-main; mirrors may differ).
#   RPI_ENGINEER_API_BASE        - Base URL for API/nginx (default http://127.0.0.1)
#   RPI_ENGINEER_WAN_IFACE       - Interface to treat as WAN (default eth1)
#   RPI_ENGINEER_HOTSPOT_SSID    - Hotspot SSID (default RPi-Engineer)
#   RPI_ENGINEER_HOTSPOT_PASSWORD - Hotspot password (default changeme1234)

: "${RPI_ENGINEER_INSTALL_URL:=https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install.sh}"
: "${RPI_ENGINEER_REPO_ARCHIVE_URL:=https://github.com/chibashr/RPi-EngineerIAB/archive/refs/heads/main.tar.gz}"
# Top-level directory inside the archive (GitHub uses REPO-main; mirror may differ)
: "${RPI_ENGINEER_REPO_ARCHIVE_TOP:=RPi-EngineerIAB-main}"
: "${RPI_ENGINEER_API_BASE:=http://127.0.0.1}"
: "${RPI_ENGINEER_WAN_IFACE:=eth1}"
: "${RPI_ENGINEER_HOTSPOT_SSID:=RPi-Engineer}"
: "${RPI_ENGINEER_HOTSPOT_PASSWORD:=changeme1234}"

main() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "This script must be run as root (sudo)." >&2
    exit 1
  fi

  export NONINTERACTIVE=1
  export DEBIAN_FRONTEND=noninteractive

  # 1) Prefer an explicitly provided local source tree (no network).
  #    Set RPI_ENGINEER_LOCAL_SRC to a directory containing bin/install.sh.
  if [ -n "${RPI_ENGINEER_LOCAL_SRC:-}" ] && [ -x "${RPI_ENGINEER_LOCAL_SRC}/bin/install.sh" ]; then
    echo "=== Installing RPi Engineer-in-a-Box from local source: ${RPI_ENGINEER_LOCAL_SRC} ==="
    (cd "$RPI_ENGINEER_LOCAL_SRC" && RPI_ENGINEER_SKIP_CLONE=1 bash bin/install.sh)
  # 2) If an existing install is present, re-run its installer (upgrade) without downloading anything.
  elif [ -x "/opt/rpi-engineer/bin/install.sh" ]; then
    echo "=== Existing install detected; running local /opt/rpi-engineer/bin/install.sh (no GitHub access needed) ==="
    (cd /opt/rpi-engineer && RPI_ENGINEER_SKIP_CLONE=1 bash bin/install.sh)
  else
    # 3) Fallback: try to download repo archive (default GitHub; set RPI_ENGINEER_REPO_ARCHIVE_URL for a mirror).
    echo "=== Downloading RPi Engineer source from ${RPI_ENGINEER_REPO_ARCHIVE_URL} ==="
    local tmp_root="/tmp/rpi-engineer-src-$(date +%s)"
    mkdir -p "$tmp_root"
    if ! curl -fsSL "$RPI_ENGINEER_REPO_ARCHIVE_URL" | tar -xz -C "$tmp_root"; then
      echo "Failed to download/extract GitHub archive and no local source or install found." >&2
      exit 1
    fi
    local src_dir="$tmp_root/$RPI_ENGINEER_REPO_ARCHIVE_TOP"
    if [ ! -x "$src_dir/bin/install.sh" ]; then
      echo "install.sh not found in extracted archive (${src_dir}); aborting." >&2
      exit 1
    fi
    echo "=== Installing RPi Engineer-in-a-Box (from GitHub archive) ==="
    (cd "$src_dir" && bash bin/install.sh)
  fi

  echo "=== Waiting for RPi Engineer API to become healthy ==="
  local attempt=0
  local max_attempts=60
  local health_url="${RPI_ENGINEER_API_BASE}/health"

  until curl -fsS "$health_url" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "API did not become healthy after $((max_attempts * 2)) seconds (${health_url})." >&2
      exit 1
    fi
    sleep 2
  done

  echo "=== Configuring WAN interface via RPi Engineer API ==="
  echo "Target WAN interface: ${RPI_ENGINEER_WAN_IFACE}"
  curl -fsS -X PUT "${RPI_ENGINEER_API_BASE}/api/v1/network/interfaces/${RPI_ENGINEER_WAN_IFACE}" \
    -H "Content-Type: application/json" \
    -d "{\"mode\":\"dhcp\"}" >/dev/null

  echo "=== Ensuring WAN priority (USB/ethernet failover) ==="
  curl -fsS -X POST "${RPI_ENGINEER_API_BASE}/api/v1/network/wan-priority" >/dev/null

  echo "=== Configuring WiFi hotspot via RPi Engineer API ==="
  if [ -n "${RPI_ENGINEER_HOTSPOT_SSID}" ]; then
    echo "Hotspot SSID: ${RPI_ENGINEER_HOTSPOT_SSID}"
    curl -fsS -X POST "${RPI_ENGINEER_API_BASE}/api/v1/network/hotspot" \
      -H "Content-Type: application/json" \
      -d "{\"ssid\":\"${RPI_ENGINEER_HOTSPOT_SSID}\",\"password\":\"${RPI_ENGINEER_HOTSPOT_PASSWORD}\",\"channel\":6}" >/dev/null
  else
    echo "RPI_ENGINEER_HOTSPOT_SSID is empty; skipping hotspot configuration." >&2
  fi

  echo "=== Final network status (from API) ==="
  curl -fsS "${RPI_ENGINEER_API_BASE}/api/v1/network/status" || true

  echo
  echo "Bootstrap complete."
  echo "You can now manage networking and other functions from the RPi Engineer web UI."
}

main "$@"


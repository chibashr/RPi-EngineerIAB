#!/usr/bin/env bash

set -euo pipefail

INSTALL_DIR="/opt/rpi-engineer"
CONFIG_DIR="/etc/rpi-engineer"
DATA_DIR="/var/lib/rpi-engineer"
LOG_DIR="/var/log/rpi-engineer"
SERVICE_USER="rpi-engineer"
SERVICE_GROUP="rpi-engineer"
LAN_SUBNET="${RPI_ENGINEER_LAN_SUBNET:-}"

VERSION="1.0.0"
MIN_UBUNTU_VERSION="22.04"
MIN_DEBIAN_VERSION="12"

DEFAULT_HOTSPOT_SSID_PREFIX="RPi-Engineer"
DEFAULT_HOTSPOT_IP="192.168.50.1"
DEFAULT_HOTSPOT_DHCP_START="192.168.50.10"
DEFAULT_HOTSPOT_DHCP_END="192.168.50.100"

REPO_URL="https://github.com/chibashr/RPi-EngineerIAB.git"
BRANCH="main"

INSTALL_LOG="/tmp/rpi-engineer-install-$(date +%Y%m%d-%H%M%S).log"
INSTALL_PROGRESS_FILE="/tmp/rpi-engineer-install.progress"

REMOTE_ACCESS_TOOLS=()
REMOTE_ACCESS_PASSWORD=""
HOTSPOT_PASSWORD=""
HOTSPOT_SSID=""
TARGET_HOSTNAME=""
MODULE_SELECTIONS=()
INSTALL_MODE="fresh"
UPGRADE_SKIP_CONFIG="0"

DEPS_INSTALLED="no"
APP_INSTALLED="no"
SERVICES_CONFIGURED="no"
HOTSPOT_CONFIGURED="no"
REMOTE_CONFIGURED="no"
MODULES_INSTALLED="no"

# When run via 'curl | bash', BASH_SOURCE[0] is unset; use $0 so dirname yields current directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

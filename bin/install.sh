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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

log_info() {
    echo "[INFO] $1" | tee -a "$INSTALL_LOG"
}

log_warn() {
    echo "[WARN] $1" | tee -a "$INSTALL_LOG"
}

log_error() {
    echo "[ERROR] $1" | tee -a "$INSTALL_LOG"
}

log_step() {
    echo "[STEP] $1" | tee -a "$INSTALL_LOG"
}

show_progress() {
    local message="$1"
    echo -n "$message... " | tee -a "$INSTALL_LOG"
}

progress_done() {
    echo "done" | tee -a "$INSTALL_LOG"
}

progress_fail() {
    echo "failed" | tee -a "$INSTALL_LOG"
}

# Repair/continue: track completed steps so an interrupted install can resume
step_already_done() {
    local step="$1"
    [ -f "$INSTALL_PROGRESS_FILE" ] && grep -q "^${step}$" "$INSTALL_PROGRESS_FILE" 2>/dev/null
}

mark_step_done() {
    local step="$1"
    echo "$step" >> "$INSTALL_PROGRESS_FILE"
}

# Progress bar (sticky at bottom of terminal when stdout is a tty)
PROGRESS_BAR_WIDTH=40
PROGRESS_LINES=""
progress_init() {
    if [ ! -t 1 ]; then return 0; fi
    PROGRESS_LINES=$(tput lines 2>/dev/null) || true
    if [ -z "$PROGRESS_LINES" ] || [ "$PROGRESS_LINES" -le 2 ]; then return 0; fi
    tput csr 1 $((PROGRESS_LINES - 1)) 2>/dev/null || true
}

progress_bar() {
    local current="$1"
    local total="$2"
    local label="${3:-}"
    local pct=0
    [ "$total" -gt 0 ] && pct=$((current * 100 / total))
    local filled=$((current * PROGRESS_BAR_WIDTH / total))
    [ "$filled" -gt "$PROGRESS_BAR_WIDTH" ] && filled=$PROGRESS_BAR_WIDTH
    local bar=""
    local i=0
    for ((i = 0; i < PROGRESS_BAR_WIDTH; i++)); do
        [ "$i" -lt "$filled" ] && bar="${bar}#" || bar="${bar}-"
    done
    local max_label_len=40
    [ "${#label}" -gt "$max_label_len" ] && label="${label:0:$((max_label_len - 3))}..."
    local line="[${bar}] ${current}/${total}  ${pct}%  ${label}"
    if [ -t 1 ] && [ -n "$PROGRESS_LINES" ] && [ "$PROGRESS_LINES" -gt 1 ]; then
        tput cup "$PROGRESS_LINES" 0 2>/dev/null || true
        tput el 2>/dev/null || true
        printf '%s' "$line"
        tput cup $((PROGRESS_LINES - 1)) 0 2>/dev/null || true
    fi
    echo "[INFO] Progress: ${current}/${total} (${pct}%) ${label}" >> "$INSTALL_LOG"
}

progress_cleanup() {
    if [ ! -t 1 ]; then return 0; fi
    printf '\033[r' 2>/dev/null || true
    tput csr 0 "${PROGRESS_LINES:-999}" 2>/dev/null || true
}

detect_interrupted_install() {
    [ -f "$INSTALL_PROGRESS_FILE" ]
}

# Read from terminal when script is piped (e.g. curl | bash) so prompts work
# When NONINTERACTIVE=1, callers must set defaults before calling; this no-ops
interactive_read() {
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        return 0
    fi
    if [ -t 0 ]; then
        read "$@"
    else
        [ -e /dev/tty ] && read "$@" < /dev/tty || return 0
    fi
}

debug_pause() {
    if [ "${DEBUG:-0}" = "1" ]; then
        interactive_read -r -p "Press Enter to continue..."
    fi
}

check_root() {
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        log_error "This script must be run as root (use sudo)."
        exit 1
    fi
}

detect_os() {
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VERSION="${VERSION_ID:-unknown}"
        OS_CODENAME="${VERSION_CODENAME:-unknown}"
    else
        log_error "Cannot detect OS version."
        exit 1
    fi
}

check_os_compatibility() {
    case "$OS_ID" in
        ubuntu)
            if command -v dpkg >/dev/null 2>&1; then
                if ! dpkg --compare-versions "$OS_VERSION" ge "$MIN_UBUNTU_VERSION"; then
                    log_error "Ubuntu $OS_VERSION is not supported (min $MIN_UBUNTU_VERSION)."
                    exit 1
                fi
            else
                log_warn "dpkg not found; skipping Ubuntu version check."
            fi
            log_info "Detected OS: Ubuntu $OS_VERSION"
            ;;
        debian|raspbian)
            if [ -n "${OS_CODENAME:-}" ]; then
                case "$OS_CODENAME" in
                    bookworm|trixie) log_info "Detected OS: Raspberry Pi OS / Debian ($OS_CODENAME)" ;;
                    *)
                        log_error "Debian $OS_CODENAME is not supported (Bookworm or later required)."
                        exit 1
                        ;;
                esac
            elif command -v dpkg >/dev/null 2>&1; then
                if ! dpkg --compare-versions "$OS_VERSION" ge "$MIN_DEBIAN_VERSION"; then
                    log_error "Debian $OS_VERSION is not supported (min Bookworm/$MIN_DEBIAN_VERSION)."
                    exit 1
                fi
                log_info "Detected OS: Raspberry Pi OS / Debian $OS_VERSION"
            else
                log_warn "Could not verify Debian version; proceeding."
            fi
            ;;
        *)
            log_error "Unsupported OS: $OS_ID. Supported: Ubuntu 22.04+ or Raspberry Pi OS (Debian Bookworm+)."
            exit 1
            ;;
    esac
}

detect_rpi() {
    if [ -f /proc/device-tree/model ]; then
        local model
        model="$(tr -d '\0' < /proc/device-tree/model)"
        log_info "Detected model: $model"
        if ! echo "$model" | grep -qE "Raspberry Pi (3 Model B Plus|4|5)"; then
            log_warn "Unsupported Raspberry Pi model detected."
        fi
    else
        log_warn "Cannot detect Raspberry Pi model."
    fi
}

check_disk_space() {
    local required_mb=8192
    local available_mb
    available_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
    if [ -z "$available_mb" ] || [ "$available_mb" -lt "$required_mb" ]; then
        log_error "Insufficient disk space (need ${required_mb}MB)."
        exit 1
    fi
}

check_internet() {
    if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
        if ! curl -sf --connect-timeout 5 -o /dev/null https://archive.ubuntu.com/ubuntu/ >/dev/null 2>&1; then
            log_error "No internet connectivity detected."
            exit 1
        fi
    elif ! ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
        log_error "No internet connectivity detected."
        exit 1
    fi
}

# Check that the dpkg database is readable (avoids install failures from corrupted /var/lib/dpkg/status)
check_dpkg_status() {
    if ! command -v dpkg >/dev/null 2>&1; then
        return 0
    fi
    if dpkg --audit >/dev/null 2>&1; then
        return 0
    fi
    log_warn "dpkg database may be corrupted (e.g. /var/lib/dpkg/status has parse errors or unknown characters). Attempting repair..."
    if DEBIAN_FRONTEND=noninteractive dpkg --configure -a >> "$INSTALL_LOG" 2>&1; then
        log_info "dpkg --configure -a completed."
    else
        log_warn "dpkg --configure -a had issues (see $INSTALL_LOG)."
    fi
    if DEBIAN_FRONTEND=noninteractive apt-get install -f -y >> "$INSTALL_LOG" 2>&1; then
        log_info "apt-get install -f completed."
    else
        log_warn "apt-get install -f had issues (see $INSTALL_LOG)."
    fi
    if ! dpkg --audit >/dev/null 2>&1; then
        log_error "dpkg database is still broken. Fix it before re-running this installer:"
        echo "  1. sudo dpkg --configure -a"
        echo "  2. sudo apt-get install -f"
        echo "  3. If errors say 'parsing file .../status near line 0' or 'unknown characters',"
        echo "     /var/lib/dpkg/status is corrupted. Backup: sudo cp /var/lib/dpkg/status /var/lib/dpkg/status.bak"
        echo "     Then remove or fix the corrupt lines (often garbage/binary near the top), or restore from backup."
        exit 1
    fi
}

run_preflight_checks() {
    log_step "Running pre-flight checks"
    check_root
    detect_os
    check_os_compatibility
    detect_rpi
    check_disk_space
    check_internet
    check_dpkg_status
    log_info "Pre-flight checks passed."
}

get_arch() {
    if command -v dpkg >/dev/null 2>&1; then
        dpkg --print-architecture
    else
        uname -m
    fi
}

get_default_hotspot_ssid() {
    local suffix="0000"
    if [ -f /sys/class/net/wlan0/address ]; then
        suffix="$(tr -d ':' < /sys/class/net/wlan0/address | tail -c 5)"
    fi
    echo "${DEFAULT_HOTSPOT_SSID_PREFIX}-${suffix}"
}

get_system_info() {
    local ram_mb
    local storage_mb
    ram_mb="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"
    storage_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
    echo "  OS: ${OS_ID} ${OS_VERSION}"
    echo "  Model: $([ -f /proc/device-tree/model ] && tr -d '\0' < /proc/device-tree/model || echo "Unknown")"
    echo "  RAM: ${ram_mb}MB"
    echo "  Storage: ${storage_mb}MB available"
}

determine_install_mode() {
    if [ "$INSTALL_MODE" = "continue" ]; then
        log_info "Install mode: continue (repair/resume interrupted install)"
        return 0
    fi
    if [ "${NONINTERACTIVE:-0}" = "1" ] && [ "$INSTALL_MODE" = "reconfigure" ]; then
        log_info "Install mode: reconfigure (from environment; will use existing install.conf)"
        return 0
    fi
    if [ "${NONINTERACTIVE:-0}" = "1" ] && [ "$INSTALL_MODE" = "reinstall_from_scratch" ]; then
        log_info "Install mode: reinstall from scratch (from environment; will use existing install.conf)"
        return 0
    fi
    if [ -d "$INSTALL_DIR" ] || [ -d "$CONFIG_DIR" ]; then
        log_warn "Existing installation detected."
        if [ "${NONINTERACTIVE:-0}" != "1" ]; then
            echo "Select install mode:"
            echo "  1) Upgrade (update files and services)"
            echo "  2) Reconfigure (wizard and config only)"
            echo "  3) Abort"
            interactive_read -r -p "Enter choice (1-3) [1]: " choice
        fi
        case "${choice:-1}" in
            1) INSTALL_MODE="upgrade" ;;
            2) INSTALL_MODE="reconfigure" ;;
            3) log_error "Installation aborted by user."; exit 1 ;;
            *) INSTALL_MODE="upgrade" ;;
        esac
        if [ "$INSTALL_MODE" = "upgrade" ]; then
            if [ "${NONINTERACTIVE:-0}" = "1" ]; then
                UPGRADE_SKIP_CONFIG="1"
                log_info "Non-interactive upgrade: using existing configuration."
            else
                echo "Upgrade configuration:"
                echo "  1) Use existing configuration (only choose modules)"
                echo "  2) Re-run full configuration wizard"
                interactive_read -r -p "Enter choice (1-2) [1]: " upgrade_choice
                case "${upgrade_choice:-1}" in
                    1) UPGRADE_SKIP_CONFIG="1"; log_info "Upgrade: using existing configuration; module selection will be shown." ;;
                    2) UPGRADE_SKIP_CONFIG="0"; log_info "Upgrade: re-running full wizard." ;;
                    *) UPGRADE_SKIP_CONFIG="1" ;;
                esac
            fi
        fi
    else
        INSTALL_MODE="fresh"
    fi
    log_info "Install mode: $INSTALL_MODE"
}

# Offer repair/continue when a previous run was interrupted (progress file left behind)
prompt_repair_or_start_over() {
    if ! detect_interrupted_install; then
        return 0
    fi
    log_warn "Interrupted installation detected (progress file present)."
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        log_info "Non-interactive: continuing (repair) installation."
        INSTALL_MODE="continue"
        return 0
    fi
    echo "The previous installation did not finish. You can:"
    echo "  1) Continue / Repair (resume from where it stopped)"
    echo "  2) Start over (discard progress and run a new install)"
    interactive_read -r -p "Enter choice (1-2) [1]: " choice
    case "${choice:-1}" in
        1) INSTALL_MODE="continue"; log_info "Continuing interrupted installation." ;;
        2)
            rm -f "$INSTALL_PROGRESS_FILE"
            log_info "Progress file removed; starting fresh."
            ;;
        *) INSTALL_MODE="continue" ;;
    esac
}

prompt_welcome() {
    log_step "Welcome"
    cat <<'EOF'
============================================================
          RPi Engineer-in-a-Box Installation
                    Version 1.0.0
============================================================
EOF
    echo "This script will install RPi Engineer-in-a-Box on your system."
    echo
    echo "System Information:"
    get_system_info
    echo
    echo "This installation will:"
    echo "  - Install system dependencies"
    echo "  - Configure network interfaces"
    echo "  - Set up WiFi hotspot"
    echo "  - Install selected remote access tool"
    echo "  - Install selected modules"
    echo "  - Configure systemd services"
    echo
    echo "Estimated time: 10-15 minutes"
    echo
    if [ "${NONINTERACTIVE:-0}" != "1" ]; then
        interactive_read -r -p "Do you want to continue? (y/n): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_error "Installation aborted by user."
            exit 1
        fi
    else
        log_info "Non-interactive mode: proceeding."
    fi
}

prompt_remote_access() {
    log_step "Remote access configuration"
    if [ "${NONINTERACTIVE:-0}" != "1" ]; then
        echo "Select the remote access tool you want to install:"
        echo "  1) AnyDesk (Recommended)"
        echo "  2) TeamViewer"
        echo "  3) TigerVNC"
        echo "  4) Raspberry Pi Connect (Raspberry Pi OS only)"
        echo "  5) Install multiple (select after)"
        echo "  6) Skip (install manually later)"
        interactive_read -r -p "Enter your choice (1-6) [6]: " choice
    fi
    case "${choice:-6}" in
        1) REMOTE_ACCESS_TOOLS=("anydesk") ;;
        2) REMOTE_ACCESS_TOOLS=("teamviewer") ;;
        3) REMOTE_ACCESS_TOOLS=("vnc") ;;
        4) REMOTE_ACCESS_TOOLS=("rpi_connect") ;;
        5)
            echo "Select tools to install (comma-separated, e.g., 1,2):"
            echo "  1) AnyDesk"
            echo "  2) TeamViewer"
            echo "  3) TigerVNC"
            echo "  4) Raspberry Pi Connect (Raspberry Pi OS only)"
            interactive_read -r -p "Enter your choices: " multi_choice
            IFS=',' read -r -a selections <<< "${multi_choice:-}"
            REMOTE_ACCESS_TOOLS=()
            for selection in "${selections[@]}"; do
                case "$(echo "$selection" | tr -d ' ')" in
                    1) REMOTE_ACCESS_TOOLS+=("anydesk") ;;
                    2) REMOTE_ACCESS_TOOLS+=("teamviewer") ;;
                    3) REMOTE_ACCESS_TOOLS+=("vnc") ;;
                    4) REMOTE_ACCESS_TOOLS+=("rpi_connect") ;;
                esac
            done
            ;;
        6) REMOTE_ACCESS_TOOLS=() ;;
        *) REMOTE_ACCESS_TOOLS=() ;;
    esac
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ]; then
        log_info "Selected remote access tool: skip"
    else
        log_info "Selected remote access tools: ${REMOTE_ACCESS_TOOLS[*]}"
    fi
}

prompt_hotspot_config() {
    log_step "WiFi hotspot configuration"
    local default_ssid
    default_ssid="$(get_default_hotspot_ssid)"
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        HOTSPOT_SSID="${default_ssid}"
        HOTSPOT_PASSWORD="rpi-engineer-default-password"
        log_info "Non-interactive: using default SSID and password."
    else
        echo "Default SSID: ${default_ssid}"
        interactive_read -r -p "Press Enter to use default, or type custom SSID: " HOTSPOT_SSID
        if [ -z "$HOTSPOT_SSID" ]; then
            HOTSPOT_SSID="$default_ssid"
        fi
        while true; do
            interactive_read -r -s -p "Enter WiFi hotspot password (8-63 characters): " HOTSPOT_PASSWORD
            echo
            interactive_read -r -s -p "Confirm password: " password_confirm
            echo
            if [ "$HOTSPOT_PASSWORD" != "$password_confirm" ]; then
                log_warn "Passwords do not match."
                continue
            fi
            if [ "${#HOTSPOT_PASSWORD}" -ge 8 ] && [ "${#HOTSPOT_PASSWORD}" -le 63 ]; then
                break
            fi
            log_warn "Hotspot password must be 8-63 characters."
        done
    fi
}

prompt_hostname() {
    log_step "Hostname configuration"
    local current_hostname
    current_hostname="$(hostname)"
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        TARGET_HOSTNAME="$current_hostname"
    else
        echo "Current hostname: $current_hostname"
        interactive_read -r -p "Enter new hostname (or press Enter to keep current): " TARGET_HOSTNAME
        if [ -z "$TARGET_HOSTNAME" ]; then
            TARGET_HOSTNAME="$current_hostname"
        fi
    fi
    log_info "Hostname set to: $TARGET_HOSTNAME"
}

get_available_modules() {
    local modules_dir="$1"
    local mod
    AVAILABLE_MODULES=()
    if [ ! -d "$modules_dir" ]; then
        return 0
    fi
    for mod in "$modules_dir"/*/; do
        [ -d "$mod" ] || continue
        mod="$(basename "$mod")"
        if [ -f "$modules_dir/$mod/module.json" ]; then
            AVAILABLE_MODULES+=("$mod")
        fi
    done
}

get_module_display_name() {
    local modules_dir="$1"
    local mod="$2"
    local json="$modules_dir/$mod/module.json"
    if [ -f "$json" ] && command -v jq >/dev/null 2>&1; then
        jq -r '.display_name // .name // empty' "$json" 2>/dev/null || echo "$mod"
    else
        echo "$mod"
    fi
}

prompt_modules() {
    local modules_dir="$SOURCE_DIR/modules"
    get_available_modules "$modules_dir"
    if [ "${#AVAILABLE_MODULES[@]}" -eq 0 ] && [ -d "$INSTALL_DIR/modules" ]; then
        modules_dir="$INSTALL_DIR/modules"
        get_available_modules "$modules_dir"
    fi
    if [ "${#AVAILABLE_MODULES[@]}" -eq 0 ]; then
        log_info "No installable modules found; skipping module selection."
        MODULE_SELECTIONS=()
        return 0
    fi
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        log_info "Non-interactive: skipping module selection."
        MODULE_SELECTIONS=()
        return 0
    fi
    log_step "Module selection"
    echo "Select optional modules to install:"
    local i=1
    local display_name
    for mod in "${AVAILABLE_MODULES[@]}"; do
        display_name="$(get_module_display_name "$modules_dir" "$mod")"
        echo "  $i) $display_name ($mod)"
        i=$((i + 1))
    done
    interactive_read -r -p "Enter module numbers (comma-separated) or press Enter to skip: " module_choice
    MODULE_SELECTIONS=()
    if [ -n "${module_choice:-}" ]; then
        local selections
        IFS=',' read -r -a selections <<< "$module_choice"
        for selection in "${selections[@]}"; do
            selection="$(echo "$selection" | tr -d ' ')"
            if [ -n "$selection" ] && [ "$selection" -ge 1 ] 2>/dev/null && [ "$selection" -le "${#AVAILABLE_MODULES[@]}" ] 2>/dev/null; then
                MODULE_SELECTIONS+=("${AVAILABLE_MODULES[$((selection - 1))]}")
            fi
        done
    fi
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        log_info "No modules selected."
    else
        log_info "Selected modules: ${MODULE_SELECTIONS[*]}"
    fi
}

confirm_summary() {
    log_step "Configuration summary"
    echo "Installation Configuration:"
    echo
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ]; then
        echo "  Remote Access: skip"
    else
        echo "  Remote Access: ${REMOTE_ACCESS_TOOLS[*]}"
    fi
    echo "  WiFi SSID: $HOTSPOT_SSID"
    echo "  WiFi Password: ********"
    echo "  Hostname: $TARGET_HOSTNAME"
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        echo "  Modules: none"
    else
        echo "  Modules: ${MODULE_SELECTIONS[*]}"
    fi
    echo
    if [ "${NONINTERACTIVE:-0}" != "1" ]; then
        interactive_read -r -p "Is this correct? (y/n): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log_error "Installation aborted by user."
            exit 1
        fi
    fi
}

write_install_conf() {
    mkdir -p "$CONFIG_DIR"
    local password_hash
    if [ "$UPGRADE_SKIP_CONFIG" = "1" ] && [ -f "$CONFIG_DIR/install.conf" ]; then
        password_hash="$(awk -F= '/^hotspot_password_hash=/ {print $2; exit}' "$CONFIG_DIR/install.conf")"
        [ -z "$password_hash" ] && password_hash="$(openssl passwd -6 "${HOTSPOT_PASSWORD:-rpi-engineer-default-password}")"
    else
        password_hash="$(openssl passwd -6 "$HOTSPOT_PASSWORD")"
    fi
    cat > "$CONFIG_DIR/install.conf" <<EOF
[general]
version=$VERSION
install_date=$(date -Iseconds)
hostname=$TARGET_HOSTNAME

[remote_access]
tools=${REMOTE_ACCESS_TOOLS[*]:-}

[network]
hotspot_ssid=$HOTSPOT_SSID
hotspot_password_hash=$password_hash

[modules]
enabled=${MODULE_SELECTIONS[*]:-}
EOF
}

# Load install choices from a previous run (for repair/continue)
load_install_conf() {
    local conf="$CONFIG_DIR/install.conf"
    if [ ! -f "$conf" ]; then
        log_error "Cannot continue: $conf not found. Start over instead."
        exit 1
    fi
    TARGET_HOSTNAME="$(awk -F= '/^hostname=/ {print $2; exit}' "$conf")"
    HOTSPOT_SSID="$(awk -F= '/^hotspot_ssid=/ {print $2; exit}' "$conf")"
    local tools_line
    tools_line="$(awk -F= '/^tools=/ {print $2; exit}' "$conf")"
    REMOTE_ACCESS_TOOLS=()
    if [ -n "$tools_line" ]; then
        read -r -a REMOTE_ACCESS_TOOLS <<< "$tools_line"
    fi
    local enabled_line
    enabled_line="$(awk -F= '/^enabled=/ {print $2; exit}' "$conf")"
    MODULE_SELECTIONS=()
    if [ -n "$enabled_line" ]; then
        read -r -a MODULE_SELECTIONS <<< "$enabled_line"
    fi
    log_info "Loaded previous choices from $conf (hostname=$TARGET_HOSTNAME, ssid=$HOTSPOT_SSID)."
}

# Run apt-get install. When NONINTERACTIVE=1 or no TTY, use DEBIAN_FRONTEND=noninteractive.
# Otherwise allow debconf prompts so user can respond.
apt_install_interactive() {
    local package="$1" status=0
    # $package may contain multiple names (e.g. "python3 python3-pip"); word-split for apt
    if [ "${NONINTERACTIVE:-0}" = "1" ] || [ ! -e /dev/tty ]; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y $package 2>&1 | tee -a "$INSTALL_LOG" || status=$?
    else
        env -u DEBIAN_FRONTEND apt-get install -y $package < /dev/tty 2>&1 | tee -a "$INSTALL_LOG"
        status="${PIPESTATUS[0]:-0}"
    fi
    return "$status"
}

install_system_dependencies() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "deps"; then log_info "Step 'deps' already completed; skipping."; return 0; fi
    log_step "Installing system dependencies"
    echo "Ensuring dpkg/apt state is clean..."
    DEBIAN_FRONTEND=noninteractive dpkg --configure -a >> "$INSTALL_LOG" 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -f -y >> "$INSTALL_LOG" 2>&1 || true
    if ! dpkg --audit >/dev/null 2>&1; then
        log_error "dpkg database is broken (e.g. corrupted /var/lib/dpkg/status with unknown characters). Fix it before continuing:"
        echo "  1. sudo dpkg --configure -a"
        echo "  2. sudo apt-get install -f"
        echo "  3. If errors mention 'parsing' or 'near line 0', edit /var/lib/dpkg/status: backup with sudo cp /var/lib/dpkg/status /var/lib/dpkg/status.bak, then remove or fix the corrupt lines (often garbage/binary near the top)."
        exit 1
    fi
    echo "Updating package lists..."
    apt-get update 2>&1 | tee -a "$INSTALL_LOG"
    echo "Package lists updated."
    echo
    echo "Upgrading existing packages (this may take several minutes)..."
    if DEBIAN_FRONTEND=noninteractive apt-get upgrade -y 2>&1 | tee -a "$INSTALL_LOG"; then
        echo "Upgrade complete."
    else
        log_warn "Upgrade had issues (see $INSTALL_LOG); continuing with installation."
    fi
    echo
    mark_step_done "deps"
}

# Install nginx from nginx.org when distro package fails (e.g. Trixie nginx-common parse)
install_nginx_from_nginx_org() {
    local codename
    codename="$(lsb_release -cs 2>/dev/null || echo "${VERSION_CODENAME:-$OS_CODENAME}")"
    if [ -z "$codename" ]; then
        log_warn "Cannot determine distribution codename for nginx.org repo."
        return 1
    fi
    case "$OS_ID" in
        debian|raspbian|ubuntu)
            echo "Adding nginx.org repository (codename: $codename)..."
            curl -fsSL https://nginx.org/keys/nginx_signing.key | gpg --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg 2>> "$INSTALL_LOG" || return 1
            local repo_dist
            repo_dist="$([ "$OS_ID" = "ubuntu" ] && echo "ubuntu" || echo "debian")"
            echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] https://nginx.org/packages/${repo_dist} ${codename} nginx" > /etc/apt/sources.list.d/nginx.list
            printf 'Package: *\nPin: origin nginx.org\nPin: release o=nginx\nPin-Priority: 900\n' > /etc/apt/preferences.d/99nginx
            apt-get update >> "$INSTALL_LOG" 2>&1 || return 1
            DEBIAN_FRONTEND=noninteractive apt-get install -y nginx >> "$INSTALL_LOG" 2>&1
            ;;
        *)
            log_warn "nginx.org repo not configured for OS: $OS_ID"
            return 1
            ;;
    esac
}

# Verify critical dependencies for the web interface (nginx, python3)
validate_dependencies() {
    local missing=()
    command -v nginx >/dev/null 2>&1 || missing+=(nginx)
    command -v python3 >/dev/null 2>&1 || missing+=(python3)
    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing required commands: ${missing[*]}. Install them and re-run, or check $INSTALL_LOG."
        return 1
    fi
    log_info "Dependency check passed: nginx, python3 present."
    return 0
}

install_required_packages() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "packages"; then log_info "Step 'packages' already completed; skipping."; DEPS_INSTALLED="yes"; return 0; fi
    log_step "Installing required packages"
    local packages=(
        python3 python3-pip python3-venv
        network-manager dnsmasq hostapd iptables bridge-utils vlan
        cu minicom screen
        tcpdump tshark wireshark-common
        git curl wget jq bc lsof
        usbutils usb-modeswitch usb-modeswitch-data
        build-essential python3-dev
        openssl ca-certificates gnupg
    )
    for package in "${packages[@]}"; do
        if dpkg -s "$package" >/dev/null 2>&1; then
            log_info "Package already installed: $package"
            continue
        fi
        echo "Installing $package..."
        if apt_install_interactive "$package"; then
            echo "  $package installed."
        else
            log_error "Failed to install $package. Check $INSTALL_LOG for details."
            if echo "$package" | grep -q python3 && [ -f "$INSTALL_LOG" ] && grep -q "cannot get content of\|py3clean\|error processing package python3" "$INSTALL_LOG" 2>/dev/null; then
                echo ""
                echo "  This may be the known 'py3clean' issue. On the target system run:"
                echo "    sudo dpkg --configure -a"
                echo "    sudo apt-get install -f -y"
                echo "  If python3 still fails, remove the package named in the error (e.g. alacarte, hplip-data, thonny):"
                echo "    sudo apt remove --allow-remove-essential <PACKAGE>"
                echo "  then run the two commands above again and re-run this installer."
                echo "  See: web/docs/troubleshooting/install-issues.html"
            fi
            exit 1
        fi
    done
    # nginx required for web interface; try distro first, then nginx.org (avoids Trixie parse issues)
    if ! command -v nginx >/dev/null 2>&1; then
        echo "Installing nginx..."
        if apt_install_interactive "nginx"; then
            echo "  nginx installed (from distribution)."
        else
            log_warn "Distribution nginx failed (e.g. nginx-common parse issues on Trixie). Trying nginx.org repository..."
            if install_nginx_from_nginx_org; then
                echo "  nginx installed (from nginx.org)."
            else
                log_error "nginx is required for the web interface but could not be installed. Try: sudo apt install nginx, or install from https://nginx.org/en/linux_packages.html"
                exit 1
            fi
        fi
    else
        log_info "nginx already installed"
    fi
    validate_dependencies
    echo "Required packages installed."
    DEPS_INSTALLED="yes"
    mark_step_done "packages"
}

install_python_dependencies() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "python_deps"; then log_info "Step 'python_deps' already completed; skipping."; return 0; fi
    log_step "Installing Python dependencies"
    local venv_path="$INSTALL_DIR/venv"
    if [ -d "$venv_path" ]; then
        echo "Removing existing virtual environment to ensure a clean install..."
        rm -rf "$venv_path"
    fi
    echo "Creating virtual environment..."
    python3 -m venv "$venv_path" 2>&1 | tee -a "$INSTALL_LOG"
    echo "Virtual environment created."
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        echo "Installing Python packages from requirements.txt..."
        "$venv_path/bin/pip" install --upgrade pip 2>&1 | tee -a "$INSTALL_LOG"
        "$venv_path/bin/pip" install -r "$INSTALL_DIR/requirements.txt" 2>&1 | tee -a "$INSTALL_LOG"
        echo "Python packages installed."
    else
        log_warn "requirements.txt not found under $INSTALL_DIR"
    fi
    mark_step_done "python_deps"
}

create_directories() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "directories"; then log_info "Step 'directories' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Creating directories"
    echo "Creating $INSTALL_DIR, $CONFIG_DIR, $DATA_DIR, $LOG_DIR..."
    mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
    mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/services" "$INSTALL_DIR/web" "$INSTALL_DIR/modules" "$INSTALL_DIR/lib"
    mkdir -p "$CONFIG_DIR/network_profiles" "$CONFIG_DIR/module_config"
    mkdir -p "$DATA_DIR/captures" "$DATA_DIR/serial_logs" "$DATA_DIR/backups" "$DATA_DIR/database"
    echo "Directories created."
    APP_INSTALLED="yes"
    mark_step_done "directories"
}

backup_existing_install() {
    if [ "$INSTALL_MODE" != "upgrade" ]; then
        return 0
    fi
    if [ -d "$INSTALL_DIR" ]; then
        local backup_dir="/opt/rpi-engineer-backup-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backing up existing install to $backup_dir"
        cp -a "$INSTALL_DIR" "$backup_dir"
    fi
}

ensure_source_dir() {
    # When running from install dir (e.g. /opt/rpi-engineer), clone to get a fresh source
    # for deploy; otherwise we would skip deploy and leave broken/incomplete state.
    if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
        log_info "Running from install directory; cloning repository for deploy."
        local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
        echo "Cloning $REPO_URL (branch $BRANCH)..."
        if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
            log_error "git clone failed (check network and $INSTALL_LOG)."
            exit 1
        fi
        SOURCE_DIR="$clone_dir"
        echo "Repository cloned to $clone_dir"
        return 0
    fi
    # Require source to have critical files; otherwise clone so we do not deploy incomplete trees.
    if [ -d "$SOURCE_DIR/services" ] && [ -d "$SOURCE_DIR/web" ]; then
        if [ -f "$SOURCE_DIR/web/index.html" ] && [ -f "$SOURCE_DIR/services/logging_service/manager.py" ] && [ -f "$SOURCE_DIR/bin/apply-web-permissions.sh" ]; then
            return 0
        fi
        log_warn "Source directory missing critical files; cloning repository for deploy."
    else
        log_warn "Source directory not found; cloning repository."
    fi
    local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
    echo "Cloning $REPO_URL (branch $BRANCH)..."
    if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
        log_error "git clone failed (check network and $INSTALL_LOG)."
        exit 1
    fi
    SOURCE_DIR="$clone_dir"
    echo "Repository cloned to $clone_dir"
}

copy_path() {
    local src="$1"
    local dest="$2"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$src" "$dest"
    else
        rm -rf "$dest"
        cp -a "$src" "$dest"
    fi
}

deploy_files() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "deploy"; then log_info "Step 'deploy' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Deploying application files"
    ensure_source_dir
    # Upgrade/reinstall: always clone fresh so we deploy latest from remote (important when script was run via curl | bash).
    if [ "$INSTALL_MODE" = "upgrade" ] || [ "$INSTALL_MODE" = "reinstall_from_scratch" ]; then
        if command -v git >/dev/null 2>&1; then
            log_info "Cloning repository for upgrade (ensuring latest files from $BRANCH)."
            local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
            if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
                log_error "git clone failed (check network and $INSTALL_LOG)."
                exit 1
            fi
            SOURCE_DIR="$clone_dir"
        fi
    fi
    if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
        log_info "Source and install directory are the same; skipping copy."
        return 0
    fi
    backup_existing_install
    deploy_copy_from_source
    # Verify all core files (web, services, lib, bin) present; if not, repair and optionally clone/retry.
    if ! verify_and_repair_core_assets; then
        missing="core (web/services/lib/bin)"
    else
        missing=""
    fi
    if [ -n "$missing" ] && [ -d "$SOURCE_DIR" ]; then
        log_info "Re-verifying and repairing core assets from source."
        verify_and_repair_core_assets || true
        if ! verify_and_repair_core_assets; then
            missing="core (web/services/lib/bin)"
        else
            missing=""
        fi
    fi
    if [ -n "$missing" ]; then
        log_warn "Deploy incomplete after copy; missing: $missing"
        if command -v git >/dev/null 2>&1; then
            log_info "Cloning repository and redeploying from fresh source."
            local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
            if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
                log_error "git clone failed (check network and $INSTALL_LOG)."
                exit 1
            fi
            SOURCE_DIR="$clone_dir"
            if [ ! -d "$SOURCE_DIR/web" ] || [ ! -d "$SOURCE_DIR/services" ]; then
                log_error "Clone incomplete or wrong branch; missing web/ or services/."
                exit 1
            fi
            deploy_copy_from_source
            if ! verify_and_repair_core_assets; then
                log_info "Re-verifying and repairing core assets after clone."
                verify_and_repair_core_assets || true
            fi
            if ! verify_and_repair_core_assets; then
                missing="core (web/services/lib/bin)"
            else
                missing=""
            fi
        fi
    fi
    if [ -n "$missing" ]; then
        log_error "Deploy incomplete; $missing"
        log_error "Re-run the installer from a complete repo clone, or ensure the source has full web, services, lib, and bin trees."
        exit 1
    fi
    echo "Application files deployed."
    APP_INSTALLED="yes"
    mark_step_done "deploy"
}

# Core trees to verify on deploy/upgrade: every file under these is required and checked.
CORE_DIRS="web services lib bin"

# List all files under src_base (relative paths), excluding __pycache__, .pyc, .git.
# Usage: list_core_files "SOURCE_DIR/web"
list_core_files() {
    local src_base="$1"
    [ ! -d "$src_base" ] && return 0
    (cd "$src_base" && find . -type f \
        ! -path "*__pycache__*" ! -path "*/.git/*" ! -name "*.pyc" \
        | sed 's|^\./||')
}

# Verify every file under web, services, lib, bin exists at INSTALL_DIR; repair by re-copying dir then per-file.
# Returns 0 if all present, 1 if any still missing after repair.
verify_and_repair_core_assets() {
    local dir_name path missing_list="" total_missing=0
    for dir_name in $CORE_DIRS; do
        local src_base="$SOURCE_DIR/$dir_name"
        local dest_base="$INSTALL_DIR/$dir_name"
        [ ! -d "$src_base" ] && continue
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            if [ ! -e "$dest_base/$path" ]; then
                missing_list="${missing_list} ${dir_name}/${path}"
                total_missing=$((total_missing + 1))
            fi
        done < <(list_core_files "$src_base")
    done
    if [ "$total_missing" -eq 0 ]; then
        return 0
    fi
    log_warn "Missing core files after deploy ($total_missing):${missing_list}. Repairing from source."
    for dir_name in $CORE_DIRS; do
        [ -d "$SOURCE_DIR/$dir_name" ] && copy_path "$SOURCE_DIR/$dir_name" "$INSTALL_DIR/$dir_name"
    done
    total_missing=0
    missing_list=""
    for dir_name in $CORE_DIRS; do
        local src_base="$SOURCE_DIR/$dir_name"
        local dest_base="$INSTALL_DIR/$dir_name"
        [ ! -d "$src_base" ] && continue
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            if [ ! -e "$dest_base/$path" ] && [ -e "$src_base/$path" ]; then
                mkdir -p "$(dirname "$dest_base/$path")"
                cp -a "$src_base/$path" "$dest_base/$path"
            fi
            if [ ! -e "$dest_base/$path" ]; then
                missing_list="${missing_list} ${dir_name}/${path}"
                total_missing=$((total_missing + 1))
            fi
        done < <(list_core_files "$src_base")
    done
    if [ "$total_missing" -gt 0 ]; then
        log_error "Core files still missing after repair ($total_missing):${missing_list}"
        return 1
    fi
    log_info "Core assets (web/services/lib/bin) verified and repaired."
    return 0
}

# Copy from current SOURCE_DIR to INSTALL_DIR (used by deploy_files).
deploy_copy_from_source() {
    echo "Copying services..."
    copy_path "$SOURCE_DIR/services" "$INSTALL_DIR/services"
    echo "Copying web..."
    copy_path "$SOURCE_DIR/web" "$INSTALL_DIR/web"
    echo "Copying lib..."
    copy_path "$SOURCE_DIR/lib" "$INSTALL_DIR/lib"
    echo "Copying modules..."
    copy_path "$SOURCE_DIR/modules" "$INSTALL_DIR/modules"
    if [ -d "$SOURCE_DIR/bin" ]; then
        echo "Copying bin..."
        copy_path "$SOURCE_DIR/bin" "$INSTALL_DIR/bin"
    fi
    if [ -f "$SOURCE_DIR/requirements.txt" ]; then
        cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
    fi
    verify_and_repair_core_assets || true
}

setup_user_permissions() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "permissions"; then log_info "Step 'permissions' already completed; skipping."; return 0; fi
    log_step "Setting up user permissions"
    echo "Creating service user/group if needed..."
    if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        groupadd -r "$SERVICE_GROUP"
        echo "  Created group $SERVICE_GROUP"
    fi
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" -g "$SERVICE_GROUP" "$SERVICE_USER"
        echo "  Created user $SERVICE_USER"
    fi
    echo "Setting ownership and permissions..."
    chown -R "root:$SERVICE_GROUP" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"
    chown -R "root:root" "$CONFIG_DIR"
    find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
    find "$INSTALL_DIR" -type f -exec chmod 644 {} \;
    find "$DATA_DIR" -type d -exec chmod 775 {} \;
    find "$DATA_DIR" -type f -exec chmod 640 {} \;
    find "$LOG_DIR" -type d -exec chmod 775 {} \;
    find "$LOG_DIR" -type f -exec chmod 640 {} \;
    chmod 755 "$CONFIG_DIR"
    chmod 644 "$CONFIG_DIR/"* 2>/dev/null || true
    chmod 600 "$CONFIG_DIR/install.conf" "$CONFIG_DIR/remote_access.conf" 2>/dev/null || true
    if [ -d "$INSTALL_DIR/bin" ]; then
        chmod 750 "$INSTALL_DIR/bin/"* 2>/dev/null || true
    fi
    usermod -a -G dialout "$SERVICE_USER" || true
    usermod -a -G netdev "$SERVICE_USER" || true
    echo "Permissions configured."
    mark_step_done "permissions"
}

create_master_service() {
    cat > /etc/systemd/system/rpi-engineer.service <<EOF
[Unit]
Description=RPi Engineer-in-a-Box Master Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/bin/start.sh
ExecStop=$INSTALL_DIR/bin/stop.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF
}

create_service_unit() {
    local name="$1"
    local description="$2"
    local exec_start="$3"
    local run_user="$4"
    cat > "/etc/systemd/system/${name}.service" <<EOF
[Unit]
Description=$description
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$exec_start
Restart=on-failure
RestartSec=5
User=$run_user
Group=$SERVICE_GROUP
Environment=PYTHONUNBUFFERED=1
UMask=027
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF
}

configure_services() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "services"; then log_info "Step 'services' already completed; skipping."; SERVICES_CONFIGURED="yes"; return 0; fi
    log_step "Configuring systemd services"
    echo "Creating systemd service units..."
    create_master_service
    create_service_unit "rpi-engineer-api" "RPi Engineer API Gateway" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/api_gateway/main.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-network" "RPi Engineer Network Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/network_manager/manager.py" "root"
    create_service_unit "rpi-engineer-serial" "RPi Engineer Serial Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/serial_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-capture" "RPi Engineer Capture Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/capture_manager/manager.py" "root"
    create_service_unit "rpi-engineer-system" "RPi Engineer System Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/system_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-monitor" "RPi Engineer Monitor Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/monitor_service/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-update" "RPi Engineer Update Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/update_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-logging" "RPi Engineer Logging Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/logging_service/manager.py" "$SERVICE_USER"
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
        echo "Services configured and daemon reloaded."
    else
        log_warn "systemd not detected; skipping daemon-reload."
    fi
    SERVICES_CONFIGURED="yes"
    mark_step_done "services"
}

configure_nginx() {
    # Always re-apply nginx config so updates (e.g. 403 fix) take effect when install is re-run.
    log_step "Configuring nginx"
    echo "Writing nginx configuration..."
    if ! command -v nginx >/dev/null 2>&1; then
        log_warn "nginx not found; skipping nginx configuration."
        return 0
    fi
    cat > /etc/nginx/sites-available/rpi-engineer <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Explicitly allow LAN and hotspot; avoids 403 from system-wide deny rules.
    allow all;

    root /opt/rpi-engineer/web;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/rpi-engineer /etc/nginx/sites-enabled/rpi-engineer
    rm -f /etc/nginx/sites-enabled/default
    if [ -d "$INSTALL_DIR/web" ]; then
        NGINX_USER="www-data"
        if [ -f /etc/nginx/nginx.conf ] && grep -q '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf; then
            NGINX_USER=$(grep '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf | head -1 | awk '{print $2}' | tr -d ';')
        fi
        if getent passwd "$NGINX_USER" >/dev/null 2>&1; then
            chown -R "$NGINX_USER:$NGINX_USER" "$INSTALL_DIR/web"
            echo "Web root ownership set to $NGINX_USER for nginx."
        else
            chmod -R o+rX "$INSTALL_DIR/web"
            echo "Web root permissions set for nginx read access (user $NGINX_USER not found)."
        fi
        # Ensure nginx can traverse parent path (e.g. /opt, /opt/rpi-engineer).
        for d in "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR"; do
            [ -d "$d" ] && chmod o+x "$d" 2>/dev/null || true
        done
    fi
    echo "Testing nginx configuration..."
    nginx -t 2>&1 | tee -a "$INSTALL_LOG"
    if [ -d /run/systemd/system ]; then
        systemctl restart nginx
        echo "nginx restarted."
    else
        log_warn "systemd not detected; nginx config written but not restarted."
    fi
    SCRIPT_PATH="$INSTALL_DIR/bin/apply-web-permissions.sh"
    if [ -f "$SCRIPT_PATH" ]; then
        chmod 755 "$SCRIPT_PATH"
        SUDOERS_FILE="/etc/sudoers.d/rpi-engineer-apply-web-permissions"
        echo "$SERVICE_USER ALL=(root) NOPASSWD: $SCRIPT_PATH" > "$SUDOERS_FILE"
        chmod 440 "$SUDOERS_FILE"
        echo "Sudoers rule added so updates can re-apply web permissions."
    fi
    mark_step_done "nginx"
}

# Ensure wlan0 is dedicated to hotspot: unmanage in NetworkManager, deny in dhcpcd,
# and run a script at boot that brings wlan0 up with 192.168.50.1 before hostapd.
configure_hotspot_priority() {
    if [ ! -d /sys/class/net/wlan0 ]; then
        return 0
    fi
    log_info "Configuring hotspot priority over WiFi client (Ubuntu / Raspberry Pi OS)."
    if systemctl is-active NetworkManager >/dev/null 2>&1 || [ -d /etc/NetworkManager/conf.d ]; then
        mkdir -p /etc/NetworkManager/conf.d
        cat > /etc/NetworkManager/conf.d/rpi-engineer-wlan0-unmanaged.conf <<'NMEOF'
# RPi Engineer-in-a-Box: use wlan0 for hotspot only; do not manage as WiFi client
[device-wlan0-unmanaged]
match-device=interface-name:wlan0
managed=0
NMEOF
        # Do not restart NetworkManager during install; user may be on WiFi. Config applies on reboot.
        log_info "NetworkManager: wlan0 will be unmanaged after reboot."
    fi
    if command -v dhcpcd >/dev/null 2>&1 && [ -f /etc/dhcpcd.conf ]; then
        if ! grep -q '^denyinterfaces wlan0' /etc/dhcpcd.conf 2>/dev/null; then
            echo "" >> /etc/dhcpcd.conf
            echo "# RPi Engineer-in-a-Box: do not manage wlan0 (used for hotspot)" >> /etc/dhcpcd.conf
            echo "denyinterfaces wlan0" >> /etc/dhcpcd.conf
            log_info "dhcpcd: denyinterfaces wlan0 added."
        fi
    fi
    cat > "$INSTALL_DIR/bin/setup-wlan0-hotspot.sh" <<'SETUPEOF'
#!/bin/bash
# Bring wlan0 under our control for hotspot; run before hostapd.
# If hotspot.secret exists, apply SSID/password to hostapd.conf so credentials persist across reboots.
set -e
WLAN=wlan0
IP="192.168.50.1/24"
CONFIG_DIR=/etc/rpi-engineer
HOTSPOT_SECRET="$CONFIG_DIR/hotspot.secret"
[ ! -d /sys/class/net/"$WLAN" ] && exit 0
systemctl stop wpa_supplicant@"$WLAN".service 2>/dev/null || true
systemctl stop wpa_supplicant@"$WLAN" 2>/dev/null || true
ip link set "$WLAN" down 2>/dev/null || true
ip link set "$WLAN" up
if ! ip addr show "$WLAN" | grep -q "$IP"; then
    ip addr add "$IP" dev "$WLAN"
fi
# Apply persisted hotspot credentials so install/API-configured password survives reboot
if [ -f "$HOTSPOT_SECRET" ]; then
    HOTSPOT_SSID=$(sed -n '1p' "$HOTSPOT_SECRET")
    HOTSPOT_PASSWORD=$(sed -n '2p' "$HOTSPOT_SECRET")
    if [ -n "$HOTSPOT_SSID" ]; then
        mkdir -p /etc/hostapd
        {
            echo "interface=wlan0"
            echo "driver=nl80211"
            echo "ssid=$HOTSPOT_SSID"
            echo "hw_mode=g"
            echo "channel=6"
            echo "wmm_enabled=0"
            echo "macaddr_acl=0"
            echo "auth_algs=1"
            echo "ignore_broadcast_ssid=0"
            echo "wpa=2"
            printf "wpa_passphrase=%s\n" "$HOTSPOT_PASSWORD"
            echo "wpa_key_mgmt=WPA-PSK"
            echo "wpa_pairwise=TKIP"
            echo "rsn_pairwise=CCMP"
        } > /etc/hostapd/hostapd.conf
    fi
fi
exit 0
SETUPEOF
    chmod +x "$INSTALL_DIR/bin/setup-wlan0-hotspot.sh"
    cat > /etc/systemd/system/rpi-engineer-wlan0.service <<EOF
[Unit]
Description=RPi Engineer wlan0 hotspot setup (prefer hotspot over WiFi client)
Before=hostapd.service
After=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/bin/setup-wlan0-hotspot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    mkdir -p /etc/systemd/system/hostapd.service.d
    cat > /etc/systemd/system/hostapd.service.d/after-wlan0.conf <<'EOF'
[Unit]
After=rpi-engineer-wlan0.service
EOF
    systemctl daemon-reload
    # Do not run setup-wlan0-hotspot.sh here; user may be using WiFi for the install. Hotspot activates after reboot.
}

create_network_priority_script() {
    cat > "$INSTALL_DIR/bin/network-priority.sh" <<'EOF'
#!/bin/bash

test_connectivity() {
    local interface=$1
    ping -c 3 -W 5 -I "$interface" 8.8.8.8 > /dev/null 2>&1 && \
    nslookup google.com | grep -q "Address" > /dev/null 2>&1
}

for iface in /sys/class/net/usb*; do
    if [ -e "$iface" ]; then
        iface_name=$(basename "$iface")
        if test_connectivity "$iface_name"; then
            ip route replace default dev "$iface_name" metric 100
            exit 0
        fi
    fi
done

if test_connectivity eth0; then
    ip route replace default dev eth0 metric 200
    exit 0
fi

logger -t rpi-engineer "No WAN connectivity available"
exit 1
EOF
    chmod +x "$INSTALL_DIR/bin/network-priority.sh"
}

configure_hotspot() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "hotspot"; then log_info "Step 'hotspot' already completed; skipping."; HOTSPOT_CONFIGURED="yes"; return 0; fi
    log_step "Configuring WiFi hotspot"
    if [ ! -d /sys/class/net/wlan0 ]; then
        log_warn "wlan0 not found; skipping hotspot configuration."
        return 0
    fi
    if [ "$UPGRADE_SKIP_CONFIG" = "1" ]; then
        log_info "Using existing hotspot configuration (upgrade skip-config)."
        configure_hotspot_priority
        echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
        systemctl unmask hostapd >/dev/null 2>&1 || true
        # Do not start hostapd/dnsmasq during install; user may be on WiFi. They start after reboot.
        create_network_priority_script
        HOTSPOT_CONFIGURED="yes"
        return 0
    fi
    cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$HOTSPOT_SSID
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$HOTSPOT_PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    # Persist hotspot credentials so they survive reboot (applied by setup-wlan0-hotspot.sh at boot)
    mkdir -p "$CONFIG_DIR"
    printf '%s\n%s\n' "$HOTSPOT_SSID" "$HOTSPOT_PASSWORD" > "$CONFIG_DIR/hotspot.secret"
    chmod 600 "$CONFIG_DIR/hotspot.secret"
    log_info "Hotspot credentials saved to $CONFIG_DIR/hotspot.secret (used at boot)."

    cat > /etc/dnsmasq.d/rpi-engineer.conf <<EOF
interface=wlan0
dhcp-range=$DEFAULT_HOTSPOT_DHCP_START,$DEFAULT_HOTSPOT_DHCP_END,255.255.255.0,24h
domain=local
address=/rpi-engineer.local/$DEFAULT_HOTSPOT_IP
EOF

    mkdir -p /etc/network/interfaces.d
    cat > /etc/network/interfaces.d/wlan0 <<EOF
auto wlan0
iface wlan0 inet static
    address $DEFAULT_HOTSPOT_IP
    netmask 255.255.255.0
EOF

    configure_hotspot_priority
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
    systemctl unmask hostapd >/dev/null 2>&1 || true
    # Do not start hostapd/dnsmasq during install; user may be on WiFi. They start after reboot.
    create_network_priority_script
    echo "WiFi hotspot configured (SSID: $HOTSPOT_SSID)."
    HOTSPOT_CONFIGURED="yes"
    mark_step_done "hotspot"
}

configure_firewall() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "firewall"; then log_info "Step 'firewall' already completed; skipping."; return 0; fi
    log_step "Configuring firewall"
    if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
        log_warn "Container detected; skipping firewall configuration."
        return 0
    fi
    if ! command -v iptables >/dev/null 2>&1; then
        log_warn "iptables not available; skipping firewall configuration."
        return 0
    fi
    ensure_rule() {
        if ! iptables -C "$@" >/dev/null 2>&1; then
            iptables -A "$@"
        fi
    }
    ensure_nat_rule() {
        if ! iptables -t nat -C "$@" >/dev/null 2>&1; then
            iptables -t nat -A "$@"
        fi
    }
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT
    ensure_rule INPUT -i lo -j ACCEPT
    ensure_rule INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    ensure_rule INPUT -i wlan0 -p tcp -m multiport --dports 80,443 -s 192.168.50.0/24 -j ACCEPT
    ensure_rule INPUT -i wlan0 -p udp --dport 53 -j ACCEPT
    ensure_rule INPUT -i wlan0 -p udp --dport 67:68 -j ACCEPT
    if [ -n "$LAN_SUBNET" ]; then
        ensure_rule INPUT -i eth0 -p tcp -m multiport --dports 80,443 -s "$LAN_SUBNET" -j ACCEPT
    fi
    ensure_rule FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    ensure_rule FORWARD -i wlan0 -o eth0 -j ACCEPT
    ensure_rule FORWARD -i wlan0 -o usb0 -j ACCEPT
    ensure_nat_rule POSTROUTING -o eth0 -j MASQUERADE
    ensure_nat_rule POSTROUTING -o usb0 -j MASQUERADE
    echo "Firewall rules configured."
    mark_step_done "firewall"
}

install_module() {
    local module_name="$1"
    local module_dir="$INSTALL_DIR/modules/$module_name"
    local enabled_file="$CONFIG_DIR/modules_enabled.txt"
    if [ ! -d "$module_dir" ]; then
        log_warn "Module not found: $module_name"
        return 0
    fi
    if [ -f "$enabled_file" ] && grep -q "^${module_name}$" "$enabled_file"; then
        log_info "Module already enabled: $module_name"
    fi

    if [ -f "$module_dir/module.json" ]; then
        local sys_deps
        local py_deps
        sys_deps="$(jq -r '.dependencies.system[]? // empty' "$module_dir/module.json")"
        py_deps="$(jq -r '.dependencies.python[]? // empty' "$module_dir/module.json")"
        if [ -n "$sys_deps" ]; then
            while IFS= read -r dep; do
                if dpkg -s "$dep" >/dev/null 2>&1; then
                    continue
                fi
                apt_install_interactive "$dep" || { log_error "Failed to install $dep for module $module_name"; return 1; }
            done <<< "$sys_deps"
        fi
        if [ -n "$py_deps" ]; then
            while IFS= read -r dep; do
                "$INSTALL_DIR/venv/bin/pip" install "$dep" >> "$INSTALL_LOG" 2>&1
            done <<< "$py_deps"
        fi
    fi

    if [ -f "$module_dir/install.sh" ]; then
        bash "$module_dir/install.sh"
    fi

    mkdir -p "$CONFIG_DIR"
    touch "$enabled_file"
    if ! grep -q "^${module_name}$" "$enabled_file"; then
        echo "$module_name" >> "$enabled_file"
    fi
    log_info "Module installed: $module_name"
}

install_modules() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "modules"; then log_info "Step 'modules' already completed; skipping."; MODULES_INSTALLED="yes"; return 0; fi
    log_step "Installing modules"
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        log_info "No modules to install."
        return 0
    fi
    for module_name in "${MODULE_SELECTIONS[@]}"; do
        echo "Installing module: $module_name"
        install_module "$module_name"
    done
    echo "Modules installed."
    MODULES_INSTALLED="yes"
    mark_step_done "modules"
}

install_anydesk() {
    log_step "Installing AnyDesk"
    if dpkg -s anydesk >/dev/null 2>&1; then
        log_info "AnyDesk already installed."
    else
        echo "  Adding AnyDesk repository and key..."
        curl -fsSL https://keys.anydesk.com/repos/DEB-GPG-KEY | gpg --dearmor -o /usr/share/keyrings/anydesk.gpg
        echo "deb [signed-by=/usr/share/keyrings/anydesk.gpg] http://deb.anydesk.com/ all main" > /etc/apt/sources.list.d/anydesk-stable.list
        echo "  Updating package lists (may take a minute)..."
        DEBIAN_FRONTEND=noninteractive apt-get update >> "$INSTALL_LOG" 2>&1
        echo "  Installing AnyDesk package..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y anydesk >> "$INSTALL_LOG" 2>&1
    fi
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        echo "$REMOTE_ACCESS_PASSWORD" | anydesk --set-password >> "$INSTALL_LOG" 2>&1 || true
    fi
    systemctl enable anydesk >> "$INSTALL_LOG" 2>&1 || true
    systemctl start anydesk >> "$INSTALL_LOG" 2>&1 || true
    ANYDESK_ID="$(anydesk --get-id 2>/dev/null || true)"
}

install_teamviewer() {
    log_step "Installing TeamViewer"
    if dpkg -s teamviewer >/dev/null 2>&1; then
        log_info "TeamViewer already installed."
    else
        local arch
        local pkg_url
        arch="$(get_arch)"
        if [ "$arch" = "amd64" ]; then
            pkg_url="https://download.teamviewer.com/download/linux/teamviewer-host_amd64.deb"
        else
            pkg_url="https://download.teamviewer.com/download/linux/teamviewer-host_arm64.deb"
        fi
        echo "  Downloading and installing TeamViewer..."
        wget -q -O /tmp/teamviewer.deb "$pkg_url" >> "$INSTALL_LOG" 2>&1
        DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/teamviewer.deb >> "$INSTALL_LOG" 2>&1
    fi
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        teamviewer passwd "$REMOTE_ACCESS_PASSWORD" >> "$INSTALL_LOG" 2>&1 || true
    fi
    teamviewer setup >> "$INSTALL_LOG" 2>&1 || true
    systemctl enable teamviewerd >> "$INSTALL_LOG" 2>&1 || true
    systemctl start teamviewerd >> "$INSTALL_LOG" 2>&1 || true
    TEAMVIEWER_ID="$(teamviewer info 2>/dev/null | awk '/ID/ {print $4; exit}')"
}

install_vnc() {
    log_step "Installing TigerVNC"
    if dpkg -s tigervnc-standalone-server >/dev/null 2>&1; then
        log_info "TigerVNC already installed; skipping package install."
    else
        apt-get install -y tigervnc-standalone-server tigervnc-common lxde-core >> "$INSTALL_LOG" 2>&1
    fi
    mkdir -p "$INSTALL_DIR/.vnc"
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        echo "$REMOTE_ACCESS_PASSWORD" | vncpasswd -f > "$INSTALL_DIR/.vnc/passwd"
        chmod 600 "$INSTALL_DIR/.vnc/passwd"
    fi
    cat > "$INSTALL_DIR/.vnc/xstartup" <<'EOF'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
startlxde &
EOF
    chmod +x "$INSTALL_DIR/.vnc/xstartup"
    cat > /etc/systemd/system/vncserver@.service <<EOF
[Unit]
Description=TigerVNC Server
After=syslog.target network.target

[Service]
Type=forking
User=$SERVICE_USER
ExecStart=/usr/bin/vncserver :1 -geometry 1920x1080 -depth 24
ExecStop=/usr/bin/vncserver -kill :1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    systemctl start vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    VNC_CONNECTION="${DEFAULT_HOTSPOT_IP}:5901"
}

install_rpi_connect() {
    log_step "Installing Raspberry Pi Connect"
    if [ "$OS_ID" != "raspbian" ] && [ "$OS_ID" != "debian" ]; then
        log_warn "Raspberry Pi Connect is only supported on Raspberry Pi OS."
        return 0
    fi
    if dpkg -s rpi-connect >/dev/null 2>&1; then
        log_info "Raspberry Pi Connect already installed; skipping package install."
    else
        apt-get install -y rpi-connect >> "$INSTALL_LOG" 2>&1
    fi
    rpi-connect on >> "$INSTALL_LOG" 2>&1 || true
    RPI_CONNECT_URL="connect.raspberrypi.com"
}

write_remote_access_config() {
    mkdir -p "$CONFIG_DIR"
    local tools_json="[]"
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -gt 0 ]; then
        tools_json=$(printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | jq -R . | jq -s .)
    fi
    cat > "$CONFIG_DIR/remote_access.conf" <<EOF
{
  "tools_enabled": ${tools_json},
  "anydesk": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q anydesk && echo true || echo false),
    "id": "${ANYDESK_ID:-}",
    "service_status": "$(systemctl is-active anydesk 2>/dev/null || echo unknown)",
    "last_check": "$(date -Iseconds)"
  },
  "teamviewer": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q teamviewer && echo true || echo false),
    "id": "${TEAMVIEWER_ID:-}",
    "service_status": "$(systemctl is-active teamviewerd 2>/dev/null || echo unknown)",
    "last_check": "$(date -Iseconds)"
  },
  "vnc": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q vnc && echo true || echo false),
    "port": 5901,
    "display": ":1",
    "connection_string": "${VNC_CONNECTION:-}"
  },
  "rpi_connect": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q rpi_connect && echo true || echo false),
    "access_url": "${RPI_CONNECT_URL:-}",
    "signed_in": false
  }
}
EOF
}

setup_remote_access() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "remote_access"; then log_info "Step 'remote_access' already completed; skipping."; REMOTE_CONFIGURED="yes"; return 0; fi
    log_step "Setting up remote access"
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ]; then
        log_info "Remote access skipped."
        write_remote_access_config
        echo "Remote access: skipped (none selected)."
        return 0
    fi
    if [ -z "$REMOTE_ACCESS_PASSWORD" ]; then
        REMOTE_ACCESS_PASSWORD="$HOTSPOT_PASSWORD"
    fi
    for tool in "${REMOTE_ACCESS_TOOLS[@]}"; do
        echo "Installing remote access tool: $tool"
        case "$tool" in
            anydesk) install_anydesk ;;
            teamviewer) install_teamviewer ;;
            vnc) install_vnc ;;
            rpi_connect) install_rpi_connect ;;
        esac
    done
    write_remote_access_config
    echo "Remote access configured."
    REMOTE_CONFIGURED="yes"
    mark_step_done "remote_access"
}

generate_configs() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "configs"; then log_info "Step 'configs' already completed; skipping."; return 0; fi
    log_step "Generating configuration files"
    echo "Writing system.conf, remote_access.conf..."
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_DIR/system.conf" <<EOF
[general]
version=$VERSION
install_date=$(date -Iseconds)
hostname=$TARGET_HOSTNAME

[network]
hotspot_enabled=true
hotspot_ssid=$HOTSPOT_SSID
hotspot_ip=$DEFAULT_HOTSPOT_IP
priority_1=usb
priority_2=ethernet
lan_subnet=$LAN_SUBNET

[remote_access]
tools=${REMOTE_ACCESS_TOOLS[*]:-}

[web]
port=80
mode=simple

[logging]
level=INFO
retention_days=7
EOF
    echo "Configuration files written."
    mark_step_done "configs"
}

enable_services() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "enable_services"; then log_info "Step 'enable_services' already completed; skipping."; return 0; fi
    log_step "Enabling services"
    if [ ! -d /run/systemd/system ]; then
        log_warn "systemd not detected; skipping service enable/restart."
        return 0
    fi
    local services=(
        rpi-engineer
        rpi-engineer-api
        rpi-engineer-network
        rpi-engineer-serial
        rpi-engineer-capture
        rpi-engineer-system
        rpi-engineer-monitor
        rpi-engineer-update
        rpi-engineer-logging
        nginx
        rpi-engineer-wlan0
        hostapd
        dnsmasq
    )
    for service in "${services[@]}"; do
        echo "  Enabling $service..."
        systemctl enable "$service" >> "$INSTALL_LOG" 2>&1 || true
        case "$service" in
            rpi-engineer-wlan0|hostapd|dnsmasq)
                # Hotspot services: enable only; do not start during install (user may be on WiFi). They start after reboot.
                ;;
            *)
                systemctl restart "$service" >> "$INSTALL_LOG" 2>&1 || true
                ;;
        esac
    done
    echo "Services enabled (hotspot services will start after reboot)."
    mark_step_done "enable_services"
}

create_health_check_script() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "health_check"; then log_info "Step 'health_check' already completed; skipping."; return 0; fi
    cat > "$INSTALL_DIR/bin/health-check.sh" <<'EOF'
#!/bin/bash
echo "RPi Engineer-in-a-Box Health Check"
echo "===================================="

echo "Services:"
systemctl is-active rpi-engineer >/dev/null && echo "  - Main service: ok" || echo "  - Main service: fail"
systemctl is-active rpi-engineer-api >/dev/null && echo "  - API service: ok" || echo "  - API service: fail"
systemctl is-active nginx >/dev/null && echo "  - Web server: ok" || echo "  - Web server: fail"

echo "Network:"
ip addr show wlan0 | grep -q "192.168.50.1" && echo "  - WiFi hotspot: ok" || echo "  - WiFi hotspot: fail"

echo "Web Interface:"
curl -s http://localhost/api/v1/system/status >/dev/null && echo "  - API responding: ok" || echo "  - API responding: fail"
echo "===================================="
EOF
    chmod +x "$INSTALL_DIR/bin/health-check.sh"
    mark_step_done "health_check"
}

show_installation_summary() {
    log_step "Installation complete"
    echo "Installation Summary:"
    echo "  - System dependencies installed: $DEPS_INSTALLED"
    echo "  - Application files deployed: $APP_INSTALLED"
    echo "  - Services configured: $SERVICES_CONFIGURED"
    echo "  - WiFi hotspot configured: $HOTSPOT_CONFIGURED"
    echo "  - Remote access configured: $REMOTE_CONFIGURED"
    echo "  - Modules installed: $MODULES_INSTALLED"
    echo
    echo "System Information:"
    echo "  WiFi SSID: $HOTSPOT_SSID"
    echo "  WiFi Password: ********"
    echo "  Web Interface: http://${DEFAULT_HOTSPOT_IP} (after connecting to WiFi)"
    if [ -n "${ANYDESK_ID:-}" ]; then
        echo "  AnyDesk ID: $ANYDESK_ID"
    fi
    if [ -n "${TEAMVIEWER_ID:-}" ]; then
        echo "  TeamViewer ID: $TEAMVIEWER_ID"
    fi
    if [ -n "${VNC_CONNECTION:-}" ]; then
        echo "  VNC: $VNC_CONNECTION"
    fi
    if [ -n "${RPI_CONNECT_URL:-}" ]; then
        echo "  Raspberry Pi Connect: $RPI_CONNECT_URL"
    fi
    echo
    echo "Next Steps:"
    echo "  1. Reboot the system: sudo reboot (hotspot and WiFi takeover activate after reboot)"
    echo "  2. After reboot, connect to WiFi: $HOTSPOT_SSID"
    echo "  3. Open web browser to: http://${DEFAULT_HOTSPOT_IP}"
    echo
    echo "Installation log saved to: $INSTALL_LOG"
}

reboot_system() {
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        log_info "Non-interactive: skipping reboot. Run 'sudo reboot' manually if needed."
        return 0
    fi
    interactive_read -r -p "Press Enter to reboot now, or Ctrl+C to reboot manually later..."
    reboot
}

run_wizard() {
    prompt_welcome
    prompt_remote_access
    prompt_hotspot_config
    prompt_hostname
    prompt_modules
    confirm_summary
    write_install_conf
    if [ "$TARGET_HOSTNAME" != "$(hostname)" ]; then
        hostnamectl set-hostname "$TARGET_HOSTNAME"
    fi
}

main() {
    if [ "${DEBUG:-0}" = "1" ]; then
        set -x
    fi
    trap 'progress_cleanup' EXIT

    run_preflight_checks
    prompt_repair_or_start_over
    determine_install_mode
    ensure_source_dir

    if [ "$INSTALL_MODE" = "continue" ]; then
        load_install_conf
        if [ "${NONINTERACTIVE:-0}" != "1" ] && ! step_already_done "hotspot"; then
            log_step "Hotspot password (for resume)"
            echo "SSID from previous run: $HOTSPOT_SSID"
            while true; do
                interactive_read -r -s -p "Enter WiFi hotspot password (8-63 characters): " HOTSPOT_PASSWORD
                echo
                if [ "${#HOTSPOT_PASSWORD}" -ge 8 ] && [ "${#HOTSPOT_PASSWORD}" -le 63 ]; then
                    break
                fi
                log_warn "Hotspot password must be 8-63 characters."
            done
        fi
    elif [ "$INSTALL_MODE" = "upgrade" ] && [ "$UPGRADE_SKIP_CONFIG" = "1" ]; then
        load_install_conf
        if [ "${NONINTERACTIVE:-0}" != "1" ]; then
            prompt_modules
        else
            log_info "Non-interactive: keeping previously configured modules."
        fi
        write_install_conf
        if [ "$TARGET_HOSTNAME" != "$(hostname)" ]; then
            hostnamectl set-hostname "$TARGET_HOSTNAME"
        fi
    elif [ "$INSTALL_MODE" = "reconfigure" ] && [ "${NONINTERACTIVE:-0}" = "1" ]; then
        load_install_conf
        UPGRADE_SKIP_CONFIG="1"
        log_info "Reconfigure (non-interactive): re-applying config from existing install.conf."
        write_install_conf
        if [ "$TARGET_HOSTNAME" != "$(hostname)" ]; then
            hostnamectl set-hostname "$TARGET_HOSTNAME"
        fi
    elif [ "$INSTALL_MODE" = "reinstall_from_scratch" ] && [ "${NONINTERACTIVE:-0}" = "1" ]; then
        load_install_conf
        UPGRADE_SKIP_CONFIG="1"
        log_info "Reinstall from scratch (non-interactive): using existing install.conf; app directory will be replaced."
        write_install_conf
        if [ "$TARGET_HOSTNAME" != "$(hostname)" ]; then
            hostnamectl set-hostname "$TARGET_HOSTNAME"
        fi
    else
        run_wizard
    fi

    if [ "$INSTALL_MODE" = "reinstall_from_scratch" ]; then
        log_step "Reinstall from scratch: removing application directory"
        if [ -d "$INSTALL_DIR" ]; then
            log_warn "Removing $INSTALL_DIR for clean reinstall."
            rm -rf "$INSTALL_DIR"
        fi
        mkdir -p "$INSTALL_DIR"
    fi

    progress_init
    if [ "$INSTALL_MODE" != "reconfigure" ]; then
        if [ "$INSTALL_MODE" != "continue" ]; then
            : > "$INSTALL_PROGRESS_FILE"
        fi
        progress_bar 1 16 "System dependencies"
        install_system_dependencies
        progress_bar 2 16 "Required packages"
        install_required_packages
        progress_bar 3 16 "Directories"
        create_directories
        progress_bar 4 16 "Deploying files"
        deploy_files
        progress_bar 5 16 "Python dependencies"
        install_python_dependencies
        progress_bar 6 16 "User permissions"
        setup_user_permissions
        progress_bar 7 16 "Systemd services"
        configure_services
        progress_bar 8 16 "Nginx"
        configure_nginx
        progress_bar 9 16 "WiFi hotspot"
        configure_hotspot
        progress_bar 10 16 "Firewall"
        configure_firewall
        progress_bar 11 16 "Modules"
        install_modules
        progress_bar 12 16 "Remote access"
        setup_remote_access
        progress_bar 13 16 "Configuration files"
        generate_configs
        progress_bar 14 16 "Enabling services"
        enable_services
        progress_bar 15 16 "Health check"
        create_health_check_script
        progress_bar 16 16 "Complete"
    else
        progress_bar 1 6 "WiFi hotspot"
        configure_hotspot
        progress_bar 2 6 "Firewall"
        configure_firewall
        progress_bar 3 6 "Remote access"
        setup_remote_access
        progress_bar 4 6 "Configuration files"
        generate_configs
        progress_bar 5 6 "Enabling services"
        enable_services
        progress_bar 6 6 "Health check"
        create_health_check_script
    fi

    show_installation_summary
    rm -f "$INSTALL_PROGRESS_FILE"
    log_info "Install progress file removed (install complete)."
    reboot_system
}

main "$@"

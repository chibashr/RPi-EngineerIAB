#!/usr/bin/env bash
# Auto-generated from bin/install-src/*.sh. Do not edit directly.

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

# Simple scrolling progress only; no scroll region or cursor tricks.
PROGRESS_BAR_WIDTH=40
progress_init() {
    : # No-op; progress just scrolls with output
}

progress_ensure_region() {
    : # No-op; kept for call-site compatibility
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
        [ "$i" -lt "$filled" ] && bar="${bar}=" || bar="${bar}-"
    done
    local max_label_len=36
    [ "${#label}" -gt "$max_label_len" ] && label="${label:0:$((max_label_len - 3))}..."
    local line="[${bar}] ${pct}% ${label}"
    echo "$line"
    echo "[INFO] Progress: ${current}/${total} (${pct}%) ${label}" >> "$INSTALL_LOG"
}

progress_cleanup() {
    : # No-op; no scroll region to reset
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

# Quick update: git fetch + reset in install dir only. No wizard, no deps, no service reconfig.
run_quick_update() {
    log_step "Quick update (repo only)"
    if [ ! -d "$INSTALL_DIR/.git" ]; then
        log_error "Install directory is not a git repository. Use Upgrade instead."
        exit 1
    fi
    git config --system --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
    if ! git -C "$INSTALL_DIR" fetch origin "$BRANCH" >> "$INSTALL_LOG" 2>&1; then
        log_error "git fetch failed (check network and $INSTALL_LOG)."
        exit 1
    fi
    if ! git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" >> "$INSTALL_LOG" 2>&1; then
        log_error "git reset failed (check $INSTALL_LOG)."
        exit 1
    fi
    write_version_file
    log_info "Restarting services..."
    if [ -d /run/systemd/system ]; then
        systemctl restart rpi-engineer rpi-engineer-api rpi-engineer-network rpi-engineer-serial \
            rpi-engineer-capture rpi-engineer-system rpi-engineer-monitor rpi-engineer-update \
            rpi-engineer-logging nginx >> "$INSTALL_LOG" 2>&1 || true
    fi
    echo "Quick update complete. Repository updated to latest $BRANCH."
}

# Uninstall: stop services, remove configs, remove app and data.
run_uninstall() {
    log_step "Uninstalling RPi Engineer-in-a-Box"
    if [ ! -d "$INSTALL_DIR" ] && [ ! -d "$CONFIG_DIR" ]; then
        log_warn "No installation found at $INSTALL_DIR or $CONFIG_DIR."
        exit 0
    fi

    if [ "${NONINTERACTIVE:-0}" != "1" ]; then
        interactive_read -r -p "Remove data and logs too? (y/n) [n]: " remove_data
    elif [ "${RPI_ENGINEER_REMOVE_DATA:-0}" = "1" ]; then
        remove_data="y"
    else
        remove_data="n"
    fi

    # Stop and disable services
    if [ -d /run/systemd/system ]; then
        log_info "Stopping and disabling services..."
        for svc in rpi-engineer rpi-engineer-api rpi-engineer-network rpi-engineer-serial \
            rpi-engineer-capture rpi-engineer-system rpi-engineer-monitor rpi-engineer-update \
            rpi-engineer-logging rpi-engineer-wlan0; do
            systemctl stop "$svc" 2>/dev/null || true
            systemctl disable "$svc" 2>/dev/null || true
        done
        systemctl daemon-reload
    fi

    # Remove systemd unit files
    for unit in rpi-engineer rpi-engineer-api rpi-engineer-network rpi-engineer-serial \
        rpi-engineer-capture rpi-engineer-system rpi-engineer-monitor rpi-engineer-update \
        rpi-engineer-logging rpi-engineer-wlan0; do
        rm -f "/etc/systemd/system/${unit}.service"
    done
    rm -rf /etc/systemd/system/hostapd.service.d
    [ -d /run/systemd/system ] && systemctl daemon-reload

    # Restore nginx default site
    if command -v nginx >/dev/null 2>&1; then
        rm -f /etc/nginx/sites-enabled/rpi-engineer
        if [ -f /etc/nginx/sites-available/default ]; then
            ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
        fi
        nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
    fi

    # Remove sudoers rules
    rm -f /etc/sudoers.d/rpi-engineer-apply-web-permissions
    rm -f /etc/sudoers.d/rpi-engineer-apply-update
    rm -f /etc/sudoers.d/rpi-engineer-create-config-backup
    rm -f /etc/sudoers.d/rpi-engineer

    # Remove NetworkManager config
    rm -f /etc/NetworkManager/conf.d/rpi-engineer-wlan0-unmanaged.conf

    # Remove dhcpcd config (denyinterfaces wlan0)
    if [ -f /etc/dhcpcd.conf ]; then
        sed -i '/# RPi Engineer-in-a-Box/d' /etc/dhcpcd.conf 2>/dev/null || true
        sed -i '/denyinterfaces wlan0/d' /etc/dhcpcd.conf 2>/dev/null || true
    fi

    # Remove dnsmasq config
    rm -f /etc/dnsmasq.d/rpi-engineer.conf

    # Remove hostapd config (we created it)
    rm -f /etc/hostapd/hostapd.conf
    if [ -f /etc/default/hostapd ]; then
        sed -i 's|^DAEMON_CONF=.*|DAEMON_CONF=""|' /etc/default/hostapd 2>/dev/null || true
    fi

    # Remove network interfaces.d
    rm -f /etc/network/interfaces.d/wlan0

    # Remove install directory
    if [ -d "$INSTALL_DIR" ]; then
        log_info "Removing $INSTALL_DIR"
        rm -rf "$INSTALL_DIR"
    fi

    # Remove config directory
    if [ -d "$CONFIG_DIR" ]; then
        log_info "Removing $CONFIG_DIR"
        rm -rf "$CONFIG_DIR"
    fi

    # Optionally remove data and logs
    if [[ "${remove_data:-n}" =~ ^[Yy]$ ]]; then
        [ -d "$DATA_DIR" ] && rm -rf "$DATA_DIR" && log_info "Removed $DATA_DIR"
        [ -d "$LOG_DIR" ] && rm -rf "$LOG_DIR" && log_info "Removed $LOG_DIR"
    fi

    # Note: we do not remove the rpi-engineer user/group; they may be referenced elsewhere.
    echo "Uninstall complete."
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
    if [ "${NONINTERACTIVE:-0}" = "1" ] && [ "$INSTALL_MODE" = "uninstall" ]; then
        log_info "Install mode: uninstall (from environment)"
        return 0
    fi
    if [ "${NONINTERACTIVE:-0}" = "1" ] && [ "$INSTALL_MODE" = "quick_update" ]; then
        log_info "Install mode: quick update (from environment)"
        return 0
    fi
    if [ -d "$INSTALL_DIR" ] || [ -d "$CONFIG_DIR" ]; then
        log_warn "Existing installation detected."
        if [ "${NONINTERACTIVE:-0}" != "1" ]; then
            echo "Select install mode:"
            echo "  1) Upgrade (update files and services)"
            echo "  2) Quick update (update repo only, no wizard)"
            echo "  3) Reconfigure (wizard and config only)"
            echo "  4) Uninstall"
            echo "  5) Abort"
            interactive_read -r -p "Enter choice (1-5) [1]: " choice
        fi
        case "${choice:-1}" in
            1) INSTALL_MODE="upgrade" ;;
            2) INSTALL_MODE="quick_update" ;;
            3) INSTALL_MODE="reconfigure" ;;
            4) INSTALL_MODE="uninstall" ;;
            5) log_error "Installation aborted by user."; exit 1 ;;
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
                    1) UPGRADE_SKIP_CONFIG="1"; log_info "Upgrade: using existing configuration (upgrade in place)." ;;
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
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping system package upgrade (only updating rpi-engineer)."
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "deps"; then log_info "Step 'deps' already completed; skipping."; return 0; fi
    log_step "Installing system dependencies"
    DEBIAN_FRONTEND=noninteractive dpkg --configure -a >> "$INSTALL_LOG" 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -f -y >> "$INSTALL_LOG" 2>&1 || true
    if ! dpkg --audit >/dev/null 2>&1; then
        log_error "dpkg database is broken (e.g. corrupted /var/lib/dpkg/status with unknown characters). Fix it before continuing:"
        echo "  1. sudo dpkg --configure -a"
        echo "  2. sudo apt-get install -f"
        echo "  3. If errors mention 'parsing' or 'near line 0', edit /var/lib/dpkg/status: backup with sudo cp /var/lib/dpkg/status /var/lib/dpkg/status.bak, then remove or fix the corrupt lines (often garbage/binary near the top)."
        exit 1
    fi
    apt-get update 2>&1 | tee -a "$INSTALL_LOG"
    echo "Upgrading packages (may take several minutes)..."
    if DEBIAN_FRONTEND=noninteractive apt-get upgrade -y 2>&1 | tee -a "$INSTALL_LOG"; then
        :
    else
        log_warn "Upgrade had issues (see $INSTALL_LOG); continuing."
    fi
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
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping package install (only updating rpi-engineer)."
        DEPS_INSTALLED="yes"
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "packages"; then log_info "Step 'packages' already completed; skipping."; DEPS_INSTALLED="yes"; return 0; fi
    log_step "Installing required packages"
    # Allow non-superusers (wireshark group) to capture packets; must be set before wireshark-common installs
    echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections 2>/dev/null || true
    local packages=(
        python3 python3-pip python3-venv
        network-manager dnsmasq hostapd iptables bridge-utils vlan
        cu minicom screen
        tcpdump tshark wireshark-common
        libcap2-bin
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
        if apt_install_interactive "$package"; then
            :
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
    if ! command -v nginx >/dev/null 2>&1; then
        if apt_install_interactive "nginx"; then
            :
        else
            log_warn "Distribution nginx failed (e.g. Trixie parse issues). Trying nginx.org..."
            if install_nginx_from_nginx_org; then
                :
            else
                log_error "nginx is required for the web interface but could not be installed. Try: sudo apt install nginx, or install from https://nginx.org/en/linux_packages.html"
                exit 1
            fi
        fi
    else
        log_info "nginx already installed"
    fi
    validate_dependencies
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
    python3 -m venv "$venv_path" 2>&1 | tee -a "$INSTALL_LOG"
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        "$venv_path/bin/pip" install --upgrade pip 2>&1 | tee -a "$INSTALL_LOG"
        "$venv_path/bin/pip" install -r "$INSTALL_DIR/requirements.txt" 2>&1 | tee -a "$INSTALL_LOG"
        if ! "$venv_path/bin/python" -c "import uvicorn" 2>/dev/null; then
            log_error "Python dependencies failed (e.g. uvicorn not installed). Check $INSTALL_LOG."
            return 1
        fi
        # Verify uvicorn can start the API before enabling the service
        log_info "Verifying uvicorn can start API..."
        (cd "$INSTALL_DIR" && "$venv_path/bin/python" -m uvicorn services.api_gateway.main:app --host 127.0.0.1 --port 5999) >> "$INSTALL_LOG" 2>&1 &
        UVICORN_PID=$!
        sleep 3
        if curl -sf --connect-timeout 2 http://127.0.0.1:5999/api/v1/system/status >/dev/null 2>&1; then
            log_info "uvicorn health check passed."
        else
            log_warn "uvicorn health check failed (API may not respond); continuing."
        fi
        kill "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    else
        log_error "requirements.txt not found under $INSTALL_DIR; cannot install API dependencies. Re-run deploy or copy requirements.txt."
        return 1
    fi
    mark_step_done "python_deps"
}

create_directories() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "directories"; then log_info "Step 'directories' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Creating directories"
    mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
    mkdir -p "$CONFIG_DIR/network_profiles" "$CONFIG_DIR/network_configs" "$CONFIG_DIR/module_config"
    mkdir -p "$DATA_DIR/captures" "$DATA_DIR/serial_logs" "$DATA_DIR/backups" "$DATA_DIR/database" "$DATA_DIR/updates" "$DATA_DIR/staging"
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
        if [ -d "$src" ]; then
            mkdir -p "${dest%/}"
            rsync -a --delete "${src%/}/" "${dest%/}/"
        else
            rsync -a --delete "$src" "$dest"
        fi
    else
        rm -rf "$dest"
        cp -a "$src" "$dest"
    fi
}

get_source_git_hash() {
    if ! command -v git >/dev/null 2>&1; then
        return 0
    fi
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true
    fi
}

write_version_file() {
    local git_hash
    git_hash="$(get_source_git_hash | tr -d '[:space:]')"
    if [[ "$git_hash" =~ ^[0-9a-f]{40}$ ]]; then
        mkdir -p "$CONFIG_DIR"
        echo "$git_hash" > "$CONFIG_DIR/version"
        log_info "Version ref saved to $CONFIG_DIR/version"
    else
        log_warn "Version ref not written (git hash unavailable)."
    fi
}

deploy_files() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "deploy"; then log_info "Step 'deploy' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Deploying application files"
    if ! command -v git >/dev/null 2>&1; then
        log_error "git is required but not installed. Install git and re-run."
        exit 1
    fi

    if [ -d "$INSTALL_DIR/.git" ]; then
        if [ "$INSTALL_MODE" = "upgrade" ]; then
            backup_existing_install
        fi
        log_info "Existing git repository found at $INSTALL_DIR; updating."
        if git -C "$INSTALL_DIR" remote get-url origin >/dev/null 2>&1; then
            git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL" >> "$INSTALL_LOG" 2>&1 || true
        else
            git -C "$INSTALL_DIR" remote add origin "$REPO_URL" >> "$INSTALL_LOG" 2>&1 || true
        fi
        if ! git -C "$INSTALL_DIR" fetch origin "$BRANCH" >> "$INSTALL_LOG" 2>&1; then
            log_error "git fetch failed (check network and $INSTALL_LOG)."
            exit 1
        fi
        # Show diffs on branch so user can verify what is being updated
        if git -C "$INSTALL_DIR" rev-parse "origin/$BRANCH" >/dev/null 2>&1; then
            echo "--- Changes on branch $BRANCH (HEAD..origin/$BRANCH) ---" | tee -a "$INSTALL_LOG"
            git -C "$INSTALL_DIR" log --oneline HEAD.."origin/$BRANCH" 2>/dev/null | tee -a "$INSTALL_LOG" || true
            git -C "$INSTALL_DIR" diff --stat HEAD.."origin/$BRANCH" 2>/dev/null | tee -a "$INSTALL_LOG" || true
            git -C "$INSTALL_DIR" diff HEAD.."origin/$BRANCH" 2>/dev/null | tee -a "$INSTALL_LOG" || true
            echo "--- End of diff ---" | tee -a "$INSTALL_LOG"
        fi
        if ! git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" >> "$INSTALL_LOG" 2>&1; then
            log_error "git reset failed (check $INSTALL_LOG)."
            exit 1
        fi
    else
        if [ -d "$INSTALL_DIR" ] && [ "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
            log_warn "Install directory exists but is not a git repo. Backing up and replacing."
            backup_existing_install
            rm -rf "$INSTALL_DIR"
        fi
        mkdir -p "$(dirname "$INSTALL_DIR")"
        log_info "Cloning repository to $INSTALL_DIR (branch $BRANCH)."
        if ! git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >> "$INSTALL_LOG" 2>&1; then
            log_error "git clone failed (check network and $INSTALL_LOG)."
            exit 1
        fi
    fi

    for dir in web services lib bin; do
        if [ ! -d "$INSTALL_DIR/$dir" ]; then
            log_error "Deploy incomplete; missing $INSTALL_DIR/$dir"
            exit 1
        fi
    done
    echo "Application files deployed."
    write_version_file
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
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"
    chown -R "root:root" "$CONFIG_DIR"
    chmod -R u+rwX "$INSTALL_DIR"
    find "$DATA_DIR" -type d -exec chmod 775 {} \;
    find "$DATA_DIR" -type f -exec chmod 640 {} \;
    find "$LOG_DIR" -type d -exec chmod 775 {} \;
    find "$LOG_DIR" -type f -exec chmod 640 {} \;
    chmod 755 "$CONFIG_DIR"
    chmod 644 "$CONFIG_DIR/"* 2>/dev/null || true
    chmod 600 "$CONFIG_DIR/install.conf" 2>/dev/null || true
    # remote_access.conf holds only connection IDs (no passwords); API runs as $SERVICE_USER and must read it
    if [ -f "$CONFIG_DIR/remote_access.conf" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/remote_access.conf"
        chmod 640 "$CONFIG_DIR/remote_access.conf"
    fi
    # Writable config dirs: API (rpi-engineer) must write for network profiles, updates, hotspot config
    for subdir in network_profiles network_configs module_config; do
        if [ -d "$CONFIG_DIR/$subdir" ]; then
            chown -R "root:$SERVICE_GROUP" "$CONFIG_DIR/$subdir"
            find "$CONFIG_DIR/$subdir" -type d -exec chmod 775 {} \;
            find "$CONFIG_DIR/$subdir" -type f -exec chmod 664 {} \;
        fi
    done
    if [ -f "$CONFIG_DIR/version" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/version"
        chmod 664 "$CONFIG_DIR/version"
    fi
    if [ -f "$CONFIG_DIR/hotspot.secret" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/hotspot.secret"
        chmod 660 "$CONFIG_DIR/hotspot.secret"
    fi
    if [ -d "$INSTALL_DIR/bin" ]; then
        chmod 750 "$INSTALL_DIR/bin/"* 2>/dev/null || true
    fi
    # Allow git in install dir when run by root or service user (Git 2.35.2+ "dubious ownership")
    if command -v git >/dev/null 2>&1 && [ -d "$INSTALL_DIR/.git" ]; then
        git config --system --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
        # Let service user run git fetch/reset when sudo is unavailable (e.g. container)
        chmod -R g+w "$INSTALL_DIR/.git" 2>/dev/null || true
    fi
    # Make install dir group-writable so the web UI can apply updates (service user runs git in-process
    # when sudo is unavailable, or when sudoers rule is not present; group write allows both paths).
    chmod -R g+w "$INSTALL_DIR" 2>/dev/null || true
    # dialout: serial port access (ttyUSB*, ttyACM*) for serial console
    # plugdev: USB serial devices on many systems (udev assigns ttyUSB* to plugdev)
    usermod -a -G dialout "$SERVICE_USER" || true
    usermod -a -G plugdev "$SERVICE_USER" || true
    usermod -a -G netdev "$SERVICE_USER" || true
    # Packet capture: allow tcpdump to capture without root (API runs as $SERVICE_USER)
    TCPDUMP="$(command -v tcpdump 2>/dev/null)"
    if [ -n "$TCPDUMP" ] && command -v setcap >/dev/null 2>&1; then
        if setcap cap_net_raw,cap_net_admin=eip "$TCPDUMP" 2>/dev/null; then
            log_info "tcpdump capabilities set (packet capture allowed for $SERVICE_USER)."
        else
            log_warn "Could not set capabilities on tcpdump (packet capture may require root or sudo)."
        fi
    else
        [ -z "$TCPDUMP" ] && log_warn "tcpdump not found; install tcpdump for packet capture."
        command -v setcap >/dev/null 2>&1 || log_warn "setcap not found; install libcap2-bin so tcpdump can capture without root."
    fi
    # Also allow dumpcap/tshark (live view, analysis) when present
    DUMPCAP="$(command -v dumpcap 2>/dev/null)"
    if [ -n "$DUMPCAP" ]; then
        # Ensure wireshark-common allows non-superusers to capture (Debian/Ubuntu)
        if dpkg -s wireshark-common >/dev/null 2>&1; then
            echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections 2>/dev/null || true
            DEBIAN_FRONTEND=noninteractive dpkg-reconfigure wireshark-common >> "$INSTALL_LOG" 2>&1 || true
        fi
        getent group wireshark >/dev/null 2>&1 && usermod -aG wireshark "$SERVICE_USER" 2>/dev/null || true
        DUMPCAP="$(readlink -f "$DUMPCAP" 2>/dev/null || echo "$DUMPCAP")"
        if command -v setcap >/dev/null 2>&1; then
            [ -u "$DUMPCAP" ] && chmod u-s "$DUMPCAP" 2>/dev/null || true
            setcap cap_net_raw,cap_net_admin=eip "$DUMPCAP" 2>/dev/null || true
        fi
    fi
    # Persistent capture dir: /var/lib/rpi-engineer/captures (API writes pcap files here)
    mkdir -p "$DATA_DIR/captures"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR/captures" 2>/dev/null || true
    chmod -R 775 "$DATA_DIR/captures" 2>/dev/null || true
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
    local extra_env="${5:-}"
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
${extra_env}
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
    create_master_service
    local api_env="Environment=RPI_ENGINEER_ROOT=${INSTALL_DIR}
Environment=RPI_ENGINEER_DRY_RUN=0"
    create_service_unit "rpi-engineer-api" "RPi Engineer API Gateway" "$INSTALL_DIR/venv/bin/python -m uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 5000 --workers 1 --loop asyncio" "$SERVICE_USER" "$api_env"
    create_service_unit "rpi-engineer-network" "RPi Engineer Network Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/network_manager/manager.py" "root"
    create_service_unit "rpi-engineer-serial" "RPi Engineer Serial Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/serial_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-capture" "RPi Engineer Capture Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/capture_manager/manager.py" "root"
    create_service_unit "rpi-engineer-system" "RPi Engineer System Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/system_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-monitor" "RPi Engineer Monitor Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/monitor_service/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-update" "RPi Engineer Update Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/update_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-logging" "RPi Engineer Logging Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/logging_service/manager.py" "$SERVICE_USER"
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
    else
        log_warn "systemd not detected; skipping daemon-reload."
    fi
    # Allow web user (API runs as $SERVICE_USER) to run update and permission scripts with sudo (no password).
    # Required for: in-app updates (apply-update.sh), post-update permissions (apply-web-permissions.sh), config backup.
    add_sudoers_rule() {
        local script="$1" name="$2"
        [ -f "$script" ] || return 0
        chmod 755 "$script"
        mkdir -p /etc/sudoers.d
        echo "$SERVICE_USER ALL=(root) NOPASSWD: $script" > "/etc/sudoers.d/rpi-engineer-$name"
        chmod 440 "/etc/sudoers.d/rpi-engineer-$name"
    }
    add_sudoers_rule "$INSTALL_DIR/bin/apply-web-permissions.sh" "apply-web-permissions"
    add_sudoers_rule "$INSTALL_DIR/bin/apply-update.sh" "apply-update"
    add_sudoers_rule "$INSTALL_DIR/bin/create-config-backup.sh" "create-config-backup"
    # Controlled privileged operations: tcpdump, ip, ethtool, systemctl restart (no password)
    mkdir -p /etc/sudoers.d
    cat <<EOFS >/etc/sudoers.d/rpi-engineer
$SERVICE_USER ALL=(root) NOPASSWD: /usr/sbin/tcpdump
$SERVICE_USER ALL=(root) NOPASSWD: /usr/sbin/ip
$SERVICE_USER ALL=(root) NOPASSWD: /usr/sbin/ethtool
$SERVICE_USER ALL=(root) NOPASSWD: /bin/systemctl restart rpi-engineer*
EOFS
    chmod 440 /etc/sudoers.d/rpi-engineer
    log_info "Sudoers: $SERVICE_USER may run apply-update.sh, apply-web-permissions.sh, create-config-backup.sh, and privileged network commands as root (NOPASSWD)."
    if [ -x "$INSTALL_DIR/bin/verify-permissions.sh" ]; then
        log_info "Verifying permissions..."
        "$INSTALL_DIR/bin/verify-permissions.sh" >> "$INSTALL_LOG" 2>&1 || log_warn "Permission verification reported issues; see $INSTALL_LOG or run $INSTALL_DIR/bin/verify-permissions.sh"
    fi
    SERVICES_CONFIGURED="yes"
    mark_step_done "services"
}

configure_nginx() {
    # Always re-apply nginx config so updates (e.g. 403 fix) take effect when install is re-run.
    log_step "Configuring nginx"
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

    # Module web assets (JS/CSS) are served by the API gateway from modules/<id>/web/.
    location /modules/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
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
        proxy_read_timeout 120;
        proxy_send_timeout 120;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/rpi-engineer /etc/nginx/sites-enabled/rpi-engineer
    rm -f /etc/nginx/sites-enabled/default
    if [ -d "$INSTALL_DIR/web" ]; then
        # Repair nested web/web layout (e.g. from older rsync deploy); nginx expects index.html in web/.
        if [ -d "$INSTALL_DIR/web/web" ] && [ ! -f "$INSTALL_DIR/web/index.html" ]; then
            log_info "Fixing nested web directory layout."
            for f in "$INSTALL_DIR/web/web"/*; do [ -e "$f" ] && mv "$f" "$INSTALL_DIR/web/"; done
            for f in "$INSTALL_DIR/web/web"/.*; do
                [ "$f" = "$INSTALL_DIR/web/web/." ] && continue
                [ "$f" = "$INSTALL_DIR/web/web/.." ] && continue
                [ -e "$f" ] && mv "$f" "$INSTALL_DIR/web/"
            done
            rmdir "$INSTALL_DIR/web/web" 2>/dev/null || true
        fi
        NGINX_USER="www-data"
        if [ -f /etc/nginx/nginx.conf ] && grep -q '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf; then
            NGINX_USER=$(grep '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf | head -1 | awk '{print $2}' | tr -d ';')
        fi
        if getent passwd "$NGINX_USER" >/dev/null 2>&1; then
            chown -R "$NGINX_USER:$NGINX_USER" "$INSTALL_DIR/web"
        else
            chmod -R o+rX "$INSTALL_DIR/web"
        fi
        # Ensure nginx can read even if run user differs; avoid "directory index forbidden".
        chmod -R o+rX "$INSTALL_DIR/web"
        # Ensure nginx can traverse parent path (e.g. /opt, /opt/rpi-engineer).
        for d in "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR"; do
            [ -d "$d" ] && chmod o+x "$d" 2>/dev/null || true
        done
    fi
    nginx -t 2>&1 | tee -a "$INSTALL_LOG"
    if [ -d /run/systemd/system ]; then
        systemctl restart nginx
    else
        log_warn "systemd not detected; nginx config written but not restarted."
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
[keyfile]
unmanaged-devices=interface-name:wlan0
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
# Unblock WiFi if soft-blocked by rfkill (required for hostapd to start the AP)
command -v rfkill >/dev/null 2>&1 && { rfkill unblock wlan 2>/dev/null; rfkill unblock wifi 2>/dev/null; true; }
# Release wlan0 from NetworkManager so we can configure it (avoids RTNETLINK Operation not permitted)
command -v nmcli >/dev/null 2>&1 && nmcli device set "$WLAN" managed no 2>/dev/null || true
systemctl stop wpa_supplicant@"$WLAN".service 2>/dev/null || true
systemctl stop wpa_supplicant@"$WLAN" 2>/dev/null || true
# wlan0/driver may not be ready at boot; retry bringing interface up and adding IP
try=1
max_tries=6
while [ "$try" -le "$max_tries" ]; do
    ip link set "$WLAN" down 2>/dev/null || true
    ip link set "$WLAN" up 2>/dev/null || true
    ip addr add "$IP" dev "$WLAN" 2>/dev/null || true
    if ip addr show "$WLAN" 2>/dev/null | grep -q "$IP"; then
        break
    fi
    [ "$try" -eq "$max_tries" ] && { echo "rpi-engineer-wlan0: failed to bring up $WLAN after $max_tries attempts" >&2; exit 2; }
    sleep 2
    try=$((try + 1))
done
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
    # API (rpi-engineer) must write when user reconfigures hotspot from web UI
    mkdir -p "$CONFIG_DIR"
    printf '%s\n%s\n' "$HOTSPOT_SSID" "$HOTSPOT_PASSWORD" > "$CONFIG_DIR/hotspot.secret"
    chown "root:$SERVICE_GROUP" "$CONFIG_DIR/hotspot.secret"
    chmod 660 "$CONFIG_DIR/hotspot.secret"
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

# Install a single module: deps from module.json (jq), venv pip, optional install.sh.
# Failures in jq/pip/module install.sh are logged but do not abort; apt failures return 1
# so install_modules can log and continue with the next module.
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
        sys_deps="$(jq -r '.dependencies.system[]? // empty' "$module_dir/module.json" 2>/dev/null)" || true
        py_deps="$(jq -r '.dependencies.python[]? // empty' "$module_dir/module.json" 2>/dev/null)" || true
        if [ -n "$sys_deps" ]; then
            while IFS= read -r dep; do
                [ -z "$dep" ] && continue
                if dpkg -s "$dep" >/dev/null 2>&1; then
                    continue
                fi
                apt_install_interactive "$dep" || { log_error "Failed to install $dep for module $module_name"; return 1; }
            done <<< "$sys_deps"
        fi
        if [ -n "$py_deps" ] && [ -x "$INSTALL_DIR/venv/bin/pip" ]; then
            export PIP_NO_INPUT=1
            while IFS= read -r dep; do
                [ -z "$dep" ] && continue
                if ! "$INSTALL_DIR/venv/bin/pip" install --no-input "$dep" >> "$INSTALL_LOG" 2>&1; then
                    log_error "Failed to install Python dependency '$dep' for module $module_name (see $INSTALL_LOG)"
                fi
            done <<< "$py_deps"
        fi
    fi

    if [ -f "$module_dir/install.sh" ]; then
        if ! bash "$module_dir/install.sh" >> "$INSTALL_LOG" 2>&1; then
            log_error "Module $module_name install script failed; check $INSTALL_LOG"
        fi
    fi

    mkdir -p "$CONFIG_DIR"
    touch "$enabled_file"
    if ! grep -q "^${module_name}$" "$enabled_file"; then
        echo "$module_name" >> "$enabled_file"
    fi
    log_info "Module installed: $module_name"
}

install_modules() {
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping module install (only updating rpi-engineer)."
        MODULES_INSTALLED="yes"
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "modules"; then log_info "Step 'modules' already completed; skipping."; MODULES_INSTALLED="yes"; return 0; fi
    log_step "Installing modules"
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        log_info "No modules to install."
        return 0
    fi
    for module_name in "${MODULE_SELECTIONS[@]}"; do
        echo "Installing module: $module_name"
        install_module "$module_name" || log_error "Module $module_name failed to install; continuing with remaining modules."
    done
    echo "Modules installed."
    MODULES_INSTALLED="yes"
    mark_step_done "modules"
}

get_arch() {
    if command -v dpkg >/dev/null 2>&1; then
        dpkg --print-architecture
    else
        uname -m
    fi
}

# Install Xvfb + minimal WM and configure systemd so AnyDesk/TeamViewer have an X11 session when headless.
install_virtual_display() {
    log_step "Setting up virtual display for headless remote access"
    for pkg in xvfb openbox; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "  Installing $pkg..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" >> "$INSTALL_LOG" 2>&1
        fi
    done
    cat > /etc/systemd/system/xvfb.service <<'XVFBUNIT'
[Unit]
Description=X Virtual Frame Buffer for headless AnyDesk/TeamViewer
Before=anydesk.service teamviewerd.service xvfb-wm.service

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :0 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
XVFBUNIT
    cat > /etc/systemd/system/xvfb-wm.service <<'XVFBWMUNIT'
[Unit]
Description=Openbox WM on virtual display for AnyDesk/TeamViewer
After=xvfb.service
Wants=xvfb.service
Before=anydesk.service teamviewerd.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/env DISPLAY=:0 openbox --sm-disable
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
XVFBWMUNIT
    systemctl unmask xvfb.service >> "$INSTALL_LOG" 2>&1 || true
    systemctl unmask xvfb-wm.service >> "$INSTALL_LOG" 2>&1 || true
    mkdir -p /etc/systemd/system/anydesk.service.d
    cat > /etc/systemd/system/anydesk.service.d/display.conf <<'DISPLAYCONF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
DISPLAYCONF
    mkdir -p /etc/systemd/system/teamviewerd.service.d
    cat > /etc/systemd/system/teamviewerd.service.d/display.conf <<'DISPLAYCONF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
DISPLAYCONF
    systemctl daemon-reload
    systemctl enable xvfb xvfb-wm >> "$INSTALL_LOG" 2>&1 || true
    systemctl start xvfb >> "$INSTALL_LOG" 2>&1 || true
    systemctl start xvfb-wm >> "$INSTALL_LOG" 2>&1 || true
    log_info "Virtual display :0 with Openbox is ready for AnyDesk/TeamViewer."
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
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping remote access setup (only updating rpi-engineer)."
        REMOTE_CONFIGURED="yes"
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "remote_access"; then
        log_info "Step 'remote_access' already completed; ensuring virtual display if needed."
        if [ -f "$CONFIG_DIR/remote_access.conf" ] && command -v jq >/dev/null 2>&1; then
            if jq -e '(.anydesk.enabled == true) or (.teamviewer.enabled == true)' "$CONFIG_DIR/remote_access.conf" >/dev/null 2>&1; then
                install_virtual_display
            fi
        fi
        REMOTE_CONFIGURED="yes"
        return 0
    fi
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
    need_display=$(printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | grep -E '^(anydesk|teamviewer)$' | head -1)
    if [ -n "$need_display" ]; then
        install_virtual_display
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
    mark_step_done "configs"
}

enable_services() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "enable_services"; then log_info "Step 'enable_services' already completed; skipping."; return 0; fi
    log_step "Enabling services"
    if [ ! -d /run/systemd/system ]; then
        log_warn "systemd not detected; skipping service enable/restart."
        return 0
    fi
    log_info "Reloading systemd to pick up hotspot unit files."
    systemctl daemon-reload
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
        case "$service" in
            rpi-engineer-wlan0|hostapd|dnsmasq)
                if ! systemctl enable "$service" >> "$INSTALL_LOG" 2>&1; then
                    log_error "Failed to enable $service. Hotspot will not work after reboot. See $INSTALL_LOG"
                    exit 1
                fi
                # Hotspot services: enable only; do not start during install (user may be on WiFi). They start after reboot.
                ;;
            *)
                systemctl enable "$service" >> "$INSTALL_LOG" 2>&1 || true
                systemctl restart "$service" >> "$INSTALL_LOG" 2>&1 || true
                ;;
        esac
    done
    if [ "${HOTSPOT_CONFIGURED:-no}" = "yes" ]; then
        for s in rpi-engineer-wlan0 hostapd dnsmasq; do
            if ! systemctl is-enabled "$s" >/dev/null 2>&1; then
                log_error "Hotspot service $s is not enabled; hotspot will not start after reboot."
                exit 1
            fi
        done
        log_info "Hotspot services verified enabled (will start after reboot)."
    fi
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

    log_info "RPi Engineer installer (run $(date -u +%Y-%m-%dT%H:%M:%SZ) UTC)"
    run_preflight_checks
    prompt_repair_or_start_over
    determine_install_mode

    if [ "$INSTALL_MODE" = "uninstall" ]; then
        run_uninstall
        exit 0
    fi

    if [ "$INSTALL_MODE" = "quick_update" ]; then
        run_quick_update
        exit 0
    fi

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
        log_info "Upgrade: using existing configuration (no module or wizard prompts)."
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
    else
        run_wizard
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
        progress_bar 6 16 "Permissions"
        setup_user_permissions
        progress_bar 7 16 "Services"
        configure_services
        progress_bar 8 16 "nginx"
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
        if [ "$INSTALL_MODE" = "upgrade" ] && [ -x "$INSTALL_DIR/bin/apply-web-permissions.sh" ]; then
            log_step "Applying web permissions (upgrade)"
            "$INSTALL_DIR/bin/apply-web-permissions.sh" >> "$INSTALL_LOG" 2>&1 || log_warn "apply-web-permissions.sh had issues (see $INSTALL_LOG)."
        fi
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

    progress_cleanup
    echo
    show_installation_summary
    rm -f "$INSTALL_PROGRESS_FILE"
    log_info "Install progress file removed (install complete)."
    reboot_system
}

main "$@"

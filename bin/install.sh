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

REMOTE_ACCESS_TOOLS=()
REMOTE_ACCESS_PASSWORD=""
HOTSPOT_PASSWORD=""
HOTSPOT_SSID=""
TARGET_HOSTNAME=""
MODULE_SELECTIONS=()
INSTALL_MODE="fresh"

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
    if ! ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1; then
        log_error "No internet connectivity detected."
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
    echo "  Model: $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo "Unknown")"
    echo "  RAM: ${ram_mb}MB"
    echo "  Storage: ${storage_mb}MB available"
}

determine_install_mode() {
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
    else
        INSTALL_MODE="fresh"
    fi
    log_info "Install mode: $INSTALL_MODE"
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
    password_hash="$(openssl passwd -6 "$HOTSPOT_PASSWORD")"
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

# Run apt-get install. When NONINTERACTIVE=1 or no TTY, use DEBIAN_FRONTEND=noninteractive.
# Otherwise allow debconf prompts so user can respond.
apt_install_interactive() {
    local package="$1"
    # $package may contain multiple names (e.g. "python3 python3-pip"); word-split for apt
    if [ "${NONINTERACTIVE:-0}" = "1" ] || [ ! -e /dev/tty ]; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y $package >> "$INSTALL_LOG" 2>&1
    else
        env -u DEBIAN_FRONTEND apt-get install -y $package < /dev/tty 2>&1 | tee -a "$INSTALL_LOG"
    fi
    return "${PIPESTATUS[0]:-$?}"
}

install_system_dependencies() {
    log_step "Installing system dependencies"
    show_progress "Updating package lists"
    apt-get update >> "$INSTALL_LOG" 2>&1
    progress_done

    show_progress "Upgrading existing packages"
    apt-get upgrade -y >> "$INSTALL_LOG" 2>&1
    progress_done
}

install_required_packages() {
    log_step "Installing required packages"
    local packages=(
        python3 python3-pip python3-venv
        nginx
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
        show_progress "Installing $package"
        if apt_install_interactive "$package"; then
            progress_done
        else
            progress_fail
            log_error "Failed to install $package. Check $INSTALL_LOG for details."
            exit 1
        fi
    done
    DEPS_INSTALLED="yes"
}

install_python_dependencies() {
    log_step "Installing Python dependencies"
    local venv_path="$INSTALL_DIR/venv"
    if [ ! -d "$venv_path" ]; then
        show_progress "Creating virtual environment"
        python3 -m venv "$venv_path" >> "$INSTALL_LOG" 2>&1
        progress_done
    else
        log_info "Virtual environment already exists: $venv_path"
    fi
    if [ -f "$INSTALL_DIR/requirements.txt" ]; then
        show_progress "Installing Python packages"
        "$venv_path/bin/pip" install --upgrade pip >> "$INSTALL_LOG" 2>&1
        "$venv_path/bin/pip" install -r "$INSTALL_DIR/requirements.txt" >> "$INSTALL_LOG" 2>&1
        progress_done
    else
        log_warn "requirements.txt not found under $INSTALL_DIR"
    fi
}

create_directories() {
    log_step "Creating directories"
    mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
    mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/services" "$INSTALL_DIR/web" "$INSTALL_DIR/modules" "$INSTALL_DIR/lib"
    mkdir -p "$CONFIG_DIR/network_profiles" "$CONFIG_DIR/module_config"
    mkdir -p "$DATA_DIR/captures" "$DATA_DIR/serial_logs" "$DATA_DIR/backups" "$DATA_DIR/database"
    APP_INSTALLED="yes"
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
    if [ -d "$SOURCE_DIR/services" ] && [ -d "$SOURCE_DIR/web" ]; then
        return 0
    fi
    log_warn "Source directory not found; cloning repository."
    local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
    git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1
    SOURCE_DIR="$clone_dir"
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
    log_step "Deploying application files"
    ensure_source_dir
    if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
        log_info "Source and install directory are the same; skipping copy."
        return 0
    fi
    backup_existing_install
    copy_path "$SOURCE_DIR/services" "$INSTALL_DIR/services"
    copy_path "$SOURCE_DIR/web" "$INSTALL_DIR/web"
    copy_path "$SOURCE_DIR/lib" "$INSTALL_DIR/lib"
    copy_path "$SOURCE_DIR/modules" "$INSTALL_DIR/modules"
    if [ -d "$SOURCE_DIR/bin" ]; then
        copy_path "$SOURCE_DIR/bin" "$INSTALL_DIR/bin"
    fi
    if [ -f "$SOURCE_DIR/requirements.txt" ]; then
        cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
    fi
    APP_INSTALLED="yes"
}

setup_user_permissions() {
    log_step "Setting up user permissions"
    if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        groupadd -r "$SERVICE_GROUP"
    fi
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" -g "$SERVICE_GROUP" "$SERVICE_USER"
    fi
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
    log_step "Configuring systemd services"
    create_master_service
    create_service_unit "rpi-engineer-api" "RPi Engineer API Gateway" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/api_gateway/main.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-network" "RPi Engineer Network Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/network_manager/manager.py" "root"
    create_service_unit "rpi-engineer-serial" "RPi Engineer Serial Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/serial_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-capture" "RPi Engineer Capture Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/capture_manager/manager.py" "root"
    create_service_unit "rpi-engineer-system" "RPi Engineer System Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/system_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-monitor" "RPi Engineer Monitor Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/monitor_service/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-update" "RPi Engineer Update Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/update_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-logging" "RPi Engineer Logging Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/logging_service/manager.py" "$SERVICE_USER"
    systemctl daemon-reload
    SERVICES_CONFIGURED="yes"
}

configure_nginx() {
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
    nginx -t >> "$INSTALL_LOG" 2>&1
    systemctl restart nginx
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
    log_step "Configuring WiFi hotspot"
    if [ ! -d /sys/class/net/wlan0 ]; then
        log_warn "wlan0 not found; skipping hotspot configuration."
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

    cat > /etc/dnsmasq.d/rpi-engineer.conf <<EOF
interface=wlan0
dhcp-range=$DEFAULT_HOTSPOT_DHCP_START,$DEFAULT_HOTSPOT_DHCP_END,255.255.255.0,24h
domain=local
address=/rpi-engineer.local/$DEFAULT_HOTSPOT_IP
EOF

    cat > /etc/network/interfaces.d/wlan0 <<EOF
auto wlan0
iface wlan0 inet static
    address $DEFAULT_HOTSPOT_IP
    netmask 255.255.255.0
EOF

    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
    systemctl unmask hostapd >/dev/null 2>&1 || true
    systemctl restart hostapd || true
    systemctl restart dnsmasq || true
    create_network_priority_script
    HOTSPOT_CONFIGURED="yes"
}

configure_firewall() {
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
    log_step "Installing modules"
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        log_info "No modules to install."
        return 0
    fi
    for module_name in "${MODULE_SELECTIONS[@]}"; do
        install_module "$module_name"
    done
    MODULES_INSTALLED="yes"
}

install_anydesk() {
    log_step "Installing AnyDesk"
    if dpkg -s anydesk >/dev/null 2>&1; then
        log_info "AnyDesk already installed."
    else
        curl -fsSL https://keys.anydesk.com/repos/DEB-GPG-KEY | gpg --dearmor -o /usr/share/keyrings/anydesk.gpg
        echo "deb [signed-by=/usr/share/keyrings/anydesk.gpg] http://deb.anydesk.com/ all main" > /etc/apt/sources.list.d/anydesk-stable.list
        apt-get update >> "$INSTALL_LOG" 2>&1
        apt-get install -y anydesk >> "$INSTALL_LOG" 2>&1
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
        wget -O /tmp/teamviewer.deb "$pkg_url" >> "$INSTALL_LOG" 2>&1
        apt-get install -y /tmp/teamviewer.deb >> "$INSTALL_LOG" 2>&1
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
    apt-get install -y tigervnc-standalone-server tigervnc-common lxde-core >> "$INSTALL_LOG" 2>&1
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
    apt-get install -y rpi-connect >> "$INSTALL_LOG" 2>&1
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
    log_step "Setting up remote access"
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ]; then
        log_info "Remote access skipped."
        write_remote_access_config
        return 0
    fi
    if [ -z "$REMOTE_ACCESS_PASSWORD" ]; then
        REMOTE_ACCESS_PASSWORD="$HOTSPOT_PASSWORD"
    fi
    for tool in "${REMOTE_ACCESS_TOOLS[@]}"; do
        case "$tool" in
            anydesk) install_anydesk ;;
            teamviewer) install_teamviewer ;;
            vnc) install_vnc ;;
            rpi_connect) install_rpi_connect ;;
        esac
    done
    write_remote_access_config
    REMOTE_CONFIGURED="yes"
}

generate_configs() {
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
}

enable_services() {
    log_step "Enabling services"
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
        hostapd
        dnsmasq
    )
    for service in "${services[@]}"; do
        systemctl enable "$service" >> "$INSTALL_LOG" 2>&1 || true
        systemctl restart "$service" >> "$INSTALL_LOG" 2>&1 || true
    done
}

create_health_check_script() {
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
    echo "  1. Reboot the system: sudo reboot"
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

    run_preflight_checks
    determine_install_mode
    ensure_source_dir
    run_wizard

    if [ "$INSTALL_MODE" != "reconfigure" ]; then
        install_system_dependencies
        install_required_packages
        create_directories
        deploy_files
        install_python_dependencies
        setup_user_permissions
        configure_services
        configure_nginx
        configure_hotspot
        configure_firewall
        install_modules
        setup_remote_access
        generate_configs
        enable_services
        create_health_check_script
    else
        configure_hotspot
        configure_firewall
        setup_remote_access
        generate_configs
        enable_services
        create_health_check_script
    fi

    show_installation_summary
    reboot_system
}

main "$@"

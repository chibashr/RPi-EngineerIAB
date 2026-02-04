#!/usr/bin/env bash

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

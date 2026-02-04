#!/usr/bin/env bash

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
    else
        log_warn "requirements.txt not found under $INSTALL_DIR"
    fi
    mark_step_done "python_deps"
}

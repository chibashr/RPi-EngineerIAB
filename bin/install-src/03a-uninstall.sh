#!/usr/bin/env bash

# Sync files: git fetch + reset in install dir only. No wizard, no deps, no service reconfig.
run_sync_files() {
    log_step "Sync files (repo only)"
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
    if [ -d /run/systemd/system ] && [ "${#ALL_SERVICES[@]}" -gt 0 ]; then
        systemctl restart "${ALL_SERVICES[@]}" >> "$INSTALL_LOG" 2>&1 || true
    fi
    echo "Sync complete. Repository updated to latest $BRANCH."
}

run_repair() {
    local issues=()
    local svc

    # Scan phase
    [ ! -d "$INSTALL_DIR/.git" ] && issues+=( "Install directory is not a git repository" )
    [ ! -f "$INSTALL_DIR/venv/bin/python" ] && issues+=( "Python virtual environment missing" )
    [ ! -f "$CONFIG_DIR/install.conf" ] && issues+=( "install.conf missing" )
    [ ! -f "$CONFIG_DIR/system.conf" ] && issues+=( "system.conf missing" )
    for svc in "${DAEMON_SERVICES[@]}"; do
        if ! systemctl is-active "$svc" &>/dev/null; then
            issues+=( "Service not running: $svc" )
        fi
    done
    [ ! -f "$INSTALL_DIR/web/index.html" ] && issues+=( "Web assets missing (web/index.html not found)" )
    [ ! -f "$INSTALL_DIR/services/api_gateway/main.py" ] && issues+=( "API source missing" )

    # Report phase
    print_section_header "Repair Scan Results"
    if [ "${#issues[@]}" -eq 0 ]; then
        echo "No issues detected."
        return 0
    fi
    for svc in "${issues[@]}"; do
        echo "[!] $svc"
    done

    # Confirm phase
    local reply
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        reply="y"
    else
        read -r -p "Attempt to repair these issues? (y/n) [y]: " reply
        reply="${reply:-y}"
    fi
    if [[ ! "$reply" =~ ^[Yy]$ ]]; then
        exit 0
    fi

    # Repair phase
    local fixed=()

    if [[ " ${issues[*]} " == *" Install directory is not a git repository "* ]]; then
        if declare -f run_sync_files &>/dev/null; then
            ( run_sync_files ) || true
        else
            log_warn "run_sync_files not available; cannot repair git repository."
        fi
    fi
    if [[ " ${issues[*]} " == *" Python virtual environment missing "* ]]; then
        if declare -f install_python_dependencies &>/dev/null; then
            install_python_dependencies || true
        else
            log_warn "install_python_dependencies not available; cannot repair venv."
        fi
    fi
    if [[ " ${issues[*]} " == *" install.conf missing "* ]] || [[ " ${issues[*]} " == *" system.conf missing "* ]]; then
        if declare -f generate_configs &>/dev/null; then
            generate_configs || true
        else
            log_warn "generate_configs not available; cannot repair config files."
        fi
    fi
    for svc in "${DAEMON_SERVICES[@]}"; do
        if systemctl is-active "$svc" &>/dev/null; then
            continue
        fi
        if systemctl restart "$svc" 2>/dev/null; then
            fixed+=( "Service now running: $svc" )
        fi
    done
    if [[ " ${issues[*]} " == *" Web assets missing "* ]] || [[ " ${issues[*]} " == *" API source missing "* ]]; then
        if declare -f deploy_files &>/dev/null; then
            deploy_files >> "$INSTALL_LOG" 2>&1 || log_warn "deploy_files failed."
        else
            log_warn "deploy_files not available; cannot repair web/API files."
        fi
    fi

    # Re-scan and summary
    issues=()
    [ ! -d "$INSTALL_DIR/.git" ] && issues+=( "Install directory is not a git repository" )
    [ ! -f "$INSTALL_DIR/venv/bin/python" ] && issues+=( "Python virtual environment missing" )
    [ ! -f "$CONFIG_DIR/install.conf" ] && issues+=( "install.conf missing" )
    [ ! -f "$CONFIG_DIR/system.conf" ] && issues+=( "system.conf missing" )
    for svc in "${DAEMON_SERVICES[@]}"; do
        if ! systemctl is-active "$svc" &>/dev/null; then
            issues+=( "Service not running: $svc" )
        fi
    done
    [ ! -f "$INSTALL_DIR/web/index.html" ] && issues+=( "Web assets missing (web/index.html not found)" )
    [ ! -f "$INSTALL_DIR/services/api_gateway/main.py" ] && issues+=( "API source missing" )

    print_section_header "Repair Summary"
    if [ "${#fixed[@]}" -gt 0 ]; then
        echo "Fixed:"
        for svc in "${fixed[@]}"; do echo "  $svc"; done
    fi
    if [ "${#issues[@]}" -gt 0 ]; then
        echo "Still failing:"
        for svc in "${issues[@]}"; do echo "  [!] $svc"; done
    fi
    if [ "${#fixed[@]}" -gt 0 ] && [ "${#issues[@]}" -eq 0 ]; then
        echo "All detected issues were repaired."
    fi
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
    if [ -d /run/systemd/system ] && [ "${#ALL_SERVICES[@]}" -gt 0 ]; then
        log_info "Stopping and disabling services..."
        for svc in "${ALL_SERVICES[@]}"; do
            systemctl stop "$svc" 2>/dev/null || true
            systemctl disable "$svc" 2>/dev/null || true
        done
        systemctl daemon-reload
    fi

    # Remove systemd unit files
    for unit in "${ALL_SERVICES[@]}"; do
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
    rm -f /etc/sudoers.d/rpi-engineer-read-remote-config
    rm -f /etc/sudoers.d/rpi-engineer-set-remote-password
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

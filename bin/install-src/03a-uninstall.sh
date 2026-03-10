#!/usr/bin/env bash

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

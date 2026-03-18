#!/usr/bin/env bash

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

    # Admin authentication config: bcrypt-hash the admin password during install.
    # The API gateway reads it via RPI_ENGINEER_AUTH_CONF.
    local auth_conf_path="$CONFIG_DIR/auth.conf"
    local existing_password_hash=""
    if [ -f "$auth_conf_path" ]; then
        existing_password_hash="$(awk -F= '/^password_hash[[:space:]]*=/ {print $2; exit}' "$auth_conf_path" 2>/dev/null | tr -d '[:space:]' || true)"
    fi

    # If this is a fresh run (wizard set ADMIN_PASSWORD), use it.
    # If we don't have ADMIN_PASSWORD (e.g. continue/reconfigure), only write a hash if missing.
    local admin_pw="${ADMIN_PASSWORD:-}"
    if [ -z "$admin_pw" ] && [ -z "$existing_password_hash" ]; then
        admin_pw="${RPI_ENGINEER_ADMIN_PASSWORD:-rpi-engineer-default-password}"
    fi

    if [ -n "$admin_pw" ] && ( [ -z "$existing_password_hash" ] || [ "${ADMIN_PASSWORD:-}" != "" ] ); then
        log_info "Writing bcrypt admin password hash to $auth_conf_path"
        local admin_pw_hash
        admin_pw_hash="$("$INSTALL_DIR/venv/bin/python" -c "import bcrypt,sys; pw=sys.argv[1].encode('utf-8'); print(bcrypt.hashpw(pw, bcrypt.gensalt()).decode('utf-8'))" "$admin_pw")"

        # Best-effort: align the device account password with the same credential.
        # This keeps PAM-based fallback behavior consistent with the configured admin login.
        if [ -n "${ADMIN_PASSWORD:-}" ]; then
            if command -v chpasswd >/dev/null 2>&1; then
                echo "${SERVICE_USER}:${ADMIN_PASSWORD}" | chpasswd >/dev/null 2>&1 || log_warn "Failed to set system password for ${SERVICE_USER} (continuing)."
            else
                log_warn "chpasswd not available; skipping system password update."
            fi
        fi

        local existing_token_secret=""
        if [ -f "$auth_conf_path" ]; then
            existing_token_secret="$(awk -F= '/^token_secret[[:space:]]*=/ {print $2; exit}' "$auth_conf_path" 2>/dev/null | tr -d '[:space:]' || true)"
        fi

        mkdir -p "$(dirname "$auth_conf_path")"
        {
            echo "[auth]"
            [ -n "$existing_token_secret" ] && echo "token_secret=$existing_token_secret"
            echo "password_hash=$admin_pw_hash"
        } > "$auth_conf_path"

        # Keep read access for API (service user) but restrict other users.
        chown "root:$SERVICE_GROUP" "$auth_conf_path" 2>/dev/null || true
        chmod 640 "$auth_conf_path" 2>/dev/null || true
    fi

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
    # Only enable actual daemon services (services with main loops).
    # system_manager, serial_manager, capture_manager, update_manager, and monitor_service
    # are libraries used by the API gateway, not standalone daemons.
    local services=(
        rpi-engineer
        rpi-engineer-api
        rpi-engineer-network
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

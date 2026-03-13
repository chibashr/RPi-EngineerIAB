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

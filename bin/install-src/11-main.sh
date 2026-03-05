#!/usr/bin/env bash

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

    show_installation_summary
    rm -f "$INSTALL_PROGRESS_FILE"
    log_info "Install progress file removed (install complete)."
    reboot_system
}

main "$@"

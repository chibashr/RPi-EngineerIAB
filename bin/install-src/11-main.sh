#!/usr/bin/env bash

show_installation_summary() {
    print_section_header "Installation Complete"
    echo "  System dependencies installed : $DEPS_INSTALLED"
    echo "  Application files deployed    : $APP_INSTALLED"
    echo "  Services configured           : $SERVICES_CONFIGURED"
    echo "  WiFi hotspot configured       : $HOTSPOT_CONFIGURED"
    echo "  Remote access configured      : $REMOTE_CONFIGURED"
    echo "  Modules installed             : $MODULES_INSTALLED"
    echo
    echo "  WiFi SSID                     : $HOTSPOT_SSID"
    echo "  WiFi Password                 : ********"
    if [ "${REMOTE_ACCESS_PASSWORD_SOURCE:-}" = "custom" ]; then
        echo "  Remote access password        : custom (set by you)"
    else
        echo "  Remote access password        : auto-generated (saved to $CONFIG_DIR/remote_access.conf)"
    fi
    echo "  Web Interface                 : http://${DEFAULT_HOTSPOT_IP} (after connecting to WiFi)"
    [ -n "${ANYDESK_ID:-}" ] && echo "  AnyDesk ID                    : $ANYDESK_ID"
    [ -n "${TEAMVIEWER_ID:-}" ] && echo "  TeamViewer ID                 : $TEAMVIEWER_ID"
    [ -n "${VNC_CONNECTION:-}" ] && echo "  VNC                           : $VNC_CONNECTION"
    [ -n "${RPI_CONNECT_URL:-}" ] && echo "  Raspberry Pi Connect          : $RPI_CONNECT_URL"
    echo
    echo "  Next: sudo reboot, then connect to $HOTSPOT_SSID and open http://${DEFAULT_HOTSPOT_IP}"
    echo "  Installation log              : $INSTALL_LOG"
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
    if [ "${INSTALL_MODE:-}" = "reconfigure" ]; then
        prompt_reconfigure_sections
        return 0
    fi
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

prompt_missing_upgrade_config() {
    [ -z "$TARGET_HOSTNAME" ] && prompt_hostname
    [ -z "$HOTSPOT_SSID" ] && prompt_hotspot_config
    [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ] && prompt_remote_access
    [ "${#MODULE_SELECTIONS[@]}" -eq 0 ] && prompt_modules
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

    if [ "$INSTALL_MODE" = "sync" ]; then
        run_sync_files
        exit 0
    fi

    if [ "$INSTALL_MODE" = "repair" ]; then
        run_repair
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
    elif [ "$INSTALL_MODE" = "upgrade" ] && [ "${UPGRADE_SKIP_CONFIG:-0}" = "1" ]; then
        load_install_conf
        prompt_missing_upgrade_config
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
        step_counter_bar 1 16 "System dependencies"
        install_system_dependencies
        step_counter_bar 2 16 "Required packages"
        install_required_packages
        step_counter_bar 3 16 "Directories"
        create_directories
        step_counter_bar 4 16 "Deploying files"
        deploy_files
        step_counter_bar 5 16 "Python dependencies"
        install_python_dependencies
        step_counter_bar 6 16 "Permissions"
        setup_user_permissions
        step_counter_bar 7 16 "Services"
        configure_services
        step_counter_bar 8 16 "nginx"
        configure_nginx
        step_counter_bar 9 16 "WiFi hotspot"
        configure_hotspot
        step_counter_bar 10 16 "Firewall"
        configure_firewall
        step_counter_bar 11 16 "Modules"
        install_modules
        step_counter_bar 12 16 "Remote access"
        setup_remote_access
        step_counter_bar 13 16 "Configuration files"
        generate_configs
        step_counter_bar 14 16 "Enabling services"
        enable_services
        step_counter_bar 15 16 "Health check"
        create_health_check_script
        if [ "$INSTALL_MODE" = "upgrade" ] && [ -x "$INSTALL_DIR/bin/apply-web-permissions.sh" ]; then
            log_step "Applying web permissions (upgrade)"
            "$INSTALL_DIR/bin/apply-web-permissions.sh" >> "$INSTALL_LOG" 2>&1 || log_warn "apply-web-permissions.sh had issues (see $INSTALL_LOG)."
        fi
        step_counter_bar 16 16 "Complete"
    else
        local step=1
        local total=0
        reconf_includes hotspot && total=$((total + 1))
        reconf_includes firewall && total=$((total + 1))
        reconf_includes remote_access && total=$((total + 1))
        reconf_includes modules && total=$((total + 1))
        total=$((total + 3))
        reconf_includes hotspot && { step_counter_bar $step $total "WiFi hotspot"; configure_hotspot; step=$((step + 1)); }
        reconf_includes firewall && { step_counter_bar $step $total "Firewall"; configure_firewall; step=$((step + 1)); }
        reconf_includes remote_access && { step_counter_bar $step $total "Remote access"; setup_remote_access; step=$((step + 1)); }
        reconf_includes modules && { step_counter_bar $step $total "Modules"; install_modules; step=$((step + 1)); }
        step_counter_bar $step $total "Configuration files"
        generate_configs
        step=$((step + 1))
        step_counter_bar $step $total "Enabling services"
        enable_services
        step=$((step + 1))
        step_counter_bar $step $total "Health check"
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

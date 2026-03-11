#!/usr/bin/env bash

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
        interactive_read -r -p "Enter your choice (1-6) [5]: " choice
    fi
    case "${choice:-5}" in
        1) REMOTE_ACCESS_TOOLS=("anydesk") ;;
        2) REMOTE_ACCESS_TOOLS=("teamviewer") ;;
        3) REMOTE_ACCESS_TOOLS=("vnc") ;;
        4) REMOTE_ACCESS_TOOLS=("rpi_connect") ;;
        5)
            echo "Select tools to install (comma-separated, e.g., 1,2). Press Enter for all:"
            echo "  1) AnyDesk"
            echo "  2) TeamViewer"
            echo "  3) TigerVNC"
            echo "  4) Raspberry Pi Connect (Raspberry Pi OS only)"
            interactive_read -r -p "Enter your choices (press Enter for all): " multi_choice
            if [ -z "${multi_choice:-}" ]; then
                multi_choice="1,2,3,4"
            fi
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

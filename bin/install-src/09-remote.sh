#!/usr/bin/env bash

get_arch() {
    if command -v dpkg >/dev/null 2>&1; then
        dpkg --print-architecture
    else
        uname -m
    fi
}

# Install Xvfb + minimal WM and configure systemd so AnyDesk/TeamViewer have an X11 session when headless.
install_virtual_display() {
    log_step "Setting up virtual display for headless remote access"
    for pkg in xvfb openbox; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "  Installing $pkg..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" >> "$INSTALL_LOG" 2>&1
        fi
    done
    cat > /etc/systemd/system/xvfb.service <<'XVFBUNIT'
[Unit]
Description=X Virtual Frame Buffer for headless AnyDesk/TeamViewer
Before=anydesk.service teamviewerd.service xvfb-wm.service

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :0 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
XVFBUNIT
    cat > /etc/systemd/system/xvfb-wm.service <<'XVFBWMUNIT'
[Unit]
Description=Openbox WM on virtual display for AnyDesk/TeamViewer
After=xvfb.service
Wants=xvfb.service
Before=anydesk.service teamviewerd.service

[Service]
Type=simple
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/env DISPLAY=:0 openbox --sm-disable
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
XVFBWMUNIT
    systemctl unmask xvfb.service >> "$INSTALL_LOG" 2>&1 || true
    systemctl unmask xvfb-wm.service >> "$INSTALL_LOG" 2>&1 || true
    mkdir -p /etc/systemd/system/anydesk.service.d
    cat > /etc/systemd/system/anydesk.service.d/display.conf <<'DISPLAYCONF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
DISPLAYCONF
    mkdir -p /etc/systemd/system/teamviewerd.service.d
    cat > /etc/systemd/system/teamviewerd.service.d/display.conf <<'DISPLAYCONF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
DISPLAYCONF
    systemctl daemon-reload
    systemctl enable xvfb xvfb-wm >> "$INSTALL_LOG" 2>&1 || true
    systemctl start xvfb >> "$INSTALL_LOG" 2>&1 || true
    systemctl start xvfb-wm >> "$INSTALL_LOG" 2>&1 || true
    log_info "Virtual display :0 with Openbox is ready for AnyDesk/TeamViewer."
}

# Configure LightDM to use X11 with a full desktop (LXDE: taskbar, menu) so the Pi has a native GUI and AnyDesk/TeamViewer can capture display :0.
# AnyDesk 7.x on ARM64 Linux does not support Wayland; display_server_not_supported means Wayland session.
# Openbox is used only for headless (virtual display); with a physical display we use LXDE for taskbar and application menu.
configure_lightdm_for_x11() {
    [ -f /etc/lightdm/lightdm.conf ] || return 0
    log_step "Configuring LightDM for X11 desktop (AnyDesk/TeamViewer require X11; using LXDE for taskbar and menu)"
    for pkg in lightdm-gtk-greeter lxde-core; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "  Installing $pkg..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" >> "$INSTALL_LOG" 2>&1
        fi
    done
    # Prefer LXDE-pi on Raspberry Pi OS if present, else LXDE (from lxde-core)
    local x11_session="LXDE"
    [ -f /usr/share/xsessions/lxde-pi.desktop ] && x11_session="lxde-pi"
    [ -f /usr/share/xsessions/LXDE-pi.desktop ] && x11_session="LXDE-pi"
    sed -i.bak -e 's/^#* *greeter-session=.*/greeter-session=lightdm-gtk-greeter/' \
        -e "s/^#* *user-session=.*/user-session=$x11_session/" \
        -e "s/^#* *autologin-session=.*/autologin-session=$x11_session/" \
        /etc/lightdm/lightdm.conf 2>/dev/null || true
    if ! grep -q '^greeter-session=' /etc/lightdm/lightdm.conf; then
        sed -i '/^\[Seat:\*\]$/a greeter-session=lightdm-gtk-greeter' /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    if ! grep -q '^user-session=' /etc/lightdm/lightdm.conf; then
        sed -i "/^\[Seat:\*\]$/a user-session=$x11_session" /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    if ! grep -q '^autologin-session=' /etc/lightdm/lightdm.conf; then
        sed -i "/^\[Seat:\*\]$/a autologin-session=$x11_session" /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    log_info "LightDM set to X11 ($x11_session). Reboot or re-login for taskbar and menu to take effect."
}

_print_remote_tool_summary() {
    local tool="$1" id="$2" pass_source="$3"
    print_section_header "$tool Configuration Summary"
    echo "  Tool    : $tool"
    echo "  ID      : $id"
    if [ "$pass_source" = "custom" ]; then
        echo "  Password: custom (set by user)"
    else
        echo "  Password: auto-generated (see $CONFIG_DIR/remote_access.conf)"
    fi
    echo ""
}

install_anydesk() {
    log_step "Installing AnyDesk"
    if dpkg -s anydesk >/dev/null 2>&1; then
        log_info "AnyDesk already installed."
    else
        echo "  Adding AnyDesk repository and key..."
        curl -fsSL https://keys.anydesk.com/repos/DEB-GPG-KEY | gpg --dearmor -o /usr/share/keyrings/anydesk.gpg
        echo "deb [signed-by=/usr/share/keyrings/anydesk.gpg] http://deb.anydesk.com/ all main" > /etc/apt/sources.list.d/anydesk-stable.list
        echo "  Updating package lists (may take a minute)..."
        DEBIAN_FRONTEND=noninteractive apt-get update >> "$INSTALL_LOG" 2>&1
        echo "  Installing AnyDesk package..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y anydesk >> "$INSTALL_LOG" 2>&1
    fi
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        echo "$REMOTE_ACCESS_PASSWORD" | anydesk --set-password >> "$INSTALL_LOG" 2>&1 || true
    fi
    systemctl enable anydesk >> "$INSTALL_LOG" 2>&1 || true
    systemctl start anydesk >> "$INSTALL_LOG" 2>&1 || true
    ANYDESK_ID="$(anydesk --get-id 2>/dev/null || true)"
    _print_remote_tool_summary "AnyDesk" "${ANYDESK_ID:-unknown}" "$REMOTE_ACCESS_PASSWORD_SOURCE"
}

# TeamViewer headless install per https://www.teamviewer.com/en-us/global/support/knowledge-base/teamviewer-remote/download-and-installation/linux/install-teamviewer-classic-on-linux-without-graphical-user-interface/
# Uses apt install, CLI config (teamviewer passwd, teamviewer setup, teamviewer info). When TeamViewer-only, uses framebuffer (/dev/fb0); no Xvfb needed.
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
        echo "  Downloading and installing TeamViewer..."
        wget -q -O /tmp/teamviewer.deb "$pkg_url" >> "$INSTALL_LOG" 2>&1
        DEBIAN_FRONTEND=noninteractive apt-get install -y /tmp/teamviewer.deb >> "$INSTALL_LOG" 2>&1
    fi
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        teamviewer passwd "$REMOTE_ACCESS_PASSWORD" >> "$INSTALL_LOG" 2>&1 || true
    fi
    teamviewer setup >> "$INSTALL_LOG" 2>&1 || true
    systemctl enable teamviewerd >> "$INSTALL_LOG" 2>&1 || true
    systemctl start teamviewerd >> "$INSTALL_LOG" 2>&1 || true
    # Capture TeamViewer ID in a way that matches headless Linux output ("TeamViewer ID: 123456789")
    TEAMVIEWER_ID=""
    for args in info --info; do
        output="$(teamviewer "$args" 2>/dev/null || true)"
        if [ -n "$output" ]; then
            id_line="$(printf '%s\n' "$output" | sed -n 's/.*TeamViewer[[:space:]]\+ID[[:space:]]*:[[:space:]]*\([0-9]\+\).*/\1/p' | head -n1)"
            if [ -n "$id_line" ]; then
                TEAMVIEWER_ID="$id_line"
                break
            fi
        fi
    done
    _print_remote_tool_summary "TeamViewer" "${TEAMVIEWER_ID:-unknown}" "$REMOTE_ACCESS_PASSWORD_SOURCE"
}

install_vnc() {
    log_step "Installing TigerVNC"
    if [ "$INSTALL_MODE" = "continue" ] && dpkg -s tigervnc-standalone-server >/dev/null 2>&1 && [ -f "$INSTALL_DIR/.vnc/passwd" ] && [ -f /etc/systemd/system/vncserver@.service ]; then
        log_info "TigerVNC already configured; skipping (continue mode)."
        VNC_CONNECTION="${DEFAULT_HOTSPOT_IP}:5901"
        return 0
    fi
    if dpkg -s tigervnc-standalone-server >/dev/null 2>&1; then
        log_info "TigerVNC already installed; skipping package install."
    else
        if ! DEBIAN_FRONTEND=noninteractive apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" tigervnc-standalone-server tigervnc-common lxde-core >> "$INSTALL_LOG" 2>&1; then
            log_error "Failed to install TigerVNC packages; skipping VNC setup (see $INSTALL_LOG)."
            VNC_CONNECTION=""
            return 0
        fi
    fi
    if ! command -v vncserver >/dev/null 2>&1; then
        log_warn "vncserver binary not found after install; skipping VNC systemd setup."
        VNC_CONNECTION=""
        return 0
    fi
    mkdir -p "$INSTALL_DIR/.vnc"
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        if ! echo "$REMOTE_ACCESS_PASSWORD" | vncpasswd -f > "$INSTALL_DIR/.vnc/passwd" 2>> "$INSTALL_LOG"; then
            log_warn "VNC password not set or rejected (see $INSTALL_LOG); set it later with: vncpasswd"
        fi
        [ -f "$INSTALL_DIR/.vnc/passwd" ] && chmod 600 "$INSTALL_DIR/.vnc/passwd" || true
    fi
    if [ ! -f "$INSTALL_DIR/.vnc/passwd" ]; then
        log_warn "No VNC password file; TigerVNC may not start until you run: sudo -u $SERVICE_USER vncpasswd"
    fi
    cat > "$INSTALL_DIR/.vnc/xstartup" <<'EOF'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
startlxde &
EOF
    chmod +x "$INSTALL_DIR/.vnc/xstartup" || true
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
    systemctl daemon-reload >> "$INSTALL_LOG" 2>&1 || true
    systemctl enable vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    systemctl start vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    VNC_CONNECTION="${DEFAULT_HOTSPOT_IP}:5901"
    _print_remote_tool_summary "TigerVNC" "${VNC_CONNECTION:-$DEFAULT_HOTSPOT_IP:5901}" "${REMOTE_ACCESS_PASSWORD_SOURCE:-auto}"
}

install_rpi_connect() {
    log_step "Installing Raspberry Pi Connect"
    if [ "$OS_ID" != "raspbian" ] && [ "$OS_ID" != "debian" ]; then
        log_warn "Raspberry Pi Connect is only supported on Raspberry Pi OS."
        return 0
    fi
    if dpkg -s rpi-connect >/dev/null 2>&1; then
        log_info "Raspberry Pi Connect already installed; skipping package install."
    else
        apt-get install -y rpi-connect >> "$INSTALL_LOG" 2>&1
    fi
    # rpi-connect runs as a user service; enable lingering so it starts at boot without login
    local connect_user="${SUDO_USER:-}"
    [ -z "$connect_user" ] && id -u pi >/dev/null 2>&1 && connect_user="pi"
    if [ -n "$connect_user" ] && id "$connect_user" >/dev/null 2>&1; then
        if command -v loginctl >/dev/null 2>&1; then
            loginctl enable-linger "$connect_user" >> "$INSTALL_LOG" 2>&1 || true
            log_info "Enabled user lingering for $connect_user (Raspberry Pi Connect will start after reboot)."
        fi
        sudo -u "$connect_user" rpi-connect on >> "$INSTALL_LOG" 2>&1 || true
    else
        rpi-connect on >> "$INSTALL_LOG" 2>&1 || true
    fi
    RPI_CONNECT_URL="connect.raspberrypi.com"
}

write_remote_access_config() {
    mkdir -p "$CONFIG_DIR"
    local tools_json="[]"
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -gt 0 ]; then
        tools_json=$(printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | jq -R . | jq -s .)
    fi
    # Escape password for JSON: backslash and double-quote
    anydesk_pass_esc="${REMOTE_ACCESS_PASSWORD:-}"
    anydesk_pass_esc="${anydesk_pass_esc//\\/\\\\}"
    anydesk_pass_esc="${anydesk_pass_esc//\"/\\\"}"
    teamviewer_pass_esc="${REMOTE_ACCESS_PASSWORD:-}"
    teamviewer_pass_esc="${teamviewer_pass_esc//\\/\\\\}"
    teamviewer_pass_esc="${teamviewer_pass_esc//\"/\\\"}"
    cat > "$CONFIG_DIR/remote_access.conf" <<EOF
{
  "tools_enabled": ${tools_json},
  "anydesk": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q anydesk && echo true || echo false),
    "id": "${ANYDESK_ID:-}",
    "password": "$anydesk_pass_esc",
    "service_status": "$(systemctl is-active anydesk 2>/dev/null || echo unknown)",
    "last_check": "$(date -Iseconds)"
  },
  "teamviewer": {
    "enabled": $(printf '%s' "${REMOTE_ACCESS_TOOLS[*]}" | grep -q teamviewer && echo true || echo false),
    "id": "${TEAMVIEWER_ID:-}",
    "password": "$teamviewer_pass_esc",
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
    chmod 640 "$CONFIG_DIR/remote_access.conf"
    chgrp "$SERVICE_USER" "$CONFIG_DIR/remote_access.conf"
}

setup_remote_access() {
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping remote access setup (only updating rpi-engineer)."
        REMOTE_CONFIGURED="yes"
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "remote_access"; then
        log_info "Step 'remote_access' already completed; ensuring virtual display if needed (AnyDesk only; TeamViewer uses framebuffer when alone)."
        if [ -f "$CONFIG_DIR/remote_access.conf" ] && command -v jq >/dev/null 2>&1; then
            if jq -e '.anydesk.enabled == true' "$CONFIG_DIR/remote_access.conf" >/dev/null 2>&1; then
                install_virtual_display
            fi
        fi
        REMOTE_CONFIGURED="yes"
        return 0
    fi
    log_step "Setting up remote access"
    if [ "${#REMOTE_ACCESS_TOOLS[@]}" -eq 0 ]; then
        log_info "Remote access skipped."
        write_remote_access_config
        echo "Remote access: skipped (none selected)."
        return 0
    fi
    if [ -z "$REMOTE_ACCESS_PASSWORD" ] && [ "$REMOTE_ACCESS_PASSWORD_SOURCE" != "custom" ]; then
        REMOTE_ACCESS_PASSWORD="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9!@#$%^&*' | head -c 20)"
        log_info "Auto-generated remote access password."
    fi
    # AnyDesk requires Xvfb on headless; TeamViewer can use framebuffer console (no Xorg) per headless docs.
    need_xvfb=$(printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | grep -q '^anydesk$' && echo 1)
    if [ -n "$need_xvfb" ]; then
        install_virtual_display
        configure_lightdm_for_x11
    else
        if printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | grep -q '^teamviewer$'; then
            log_info "TeamViewer without AnyDesk: using framebuffer console per TeamViewer headless install docs (no Xvfb)."
            # Remove Xvfb override so teamviewerd uses framebuffer (/dev/fb0)
            rm -f /etc/systemd/system/teamviewerd.service.d/display.conf 2>/dev/null
            rmdir /etc/systemd/system/teamviewerd.service.d 2>/dev/null
            systemctl daemon-reload
        fi
    fi
    for tool in "${REMOTE_ACCESS_TOOLS[@]}"; do
        echo "Installing remote access tool: $tool"
        case "$tool" in
            anydesk) install_anydesk ;;
            teamviewer) install_teamviewer ;;
            vnc) install_vnc ;;
            rpi_connect) install_rpi_connect ;;
        esac
    done
    write_remote_access_config
    echo "Remote access configured."
    REMOTE_CONFIGURED="yes"
    mark_step_done "remote_access"
}

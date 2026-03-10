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

# Configure LightDM to use X11 (openbox) instead of Wayland so AnyDesk/TeamViewer can capture display :0.
# AnyDesk 7.x on ARM64 Linux does not support Wayland; display_server_not_supported means Wayland session.
configure_lightdm_for_x11() {
    [ -f /etc/lightdm/lightdm.conf ] || return 0
    log_step "Configuring LightDM for X11 (AnyDesk/TeamViewer require X11, not Wayland)"
    for pkg in lightdm-gtk-greeter openbox; do
        if ! dpkg -s "$pkg" >/dev/null 2>&1; then
            echo "  Installing $pkg..."
            DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" >> "$INSTALL_LOG" 2>&1
        fi
    done
    sed -i.bak -e 's/^#* *greeter-session=.*/greeter-session=lightdm-gtk-greeter/' \
        -e 's/^#* *user-session=.*/user-session=openbox/' \
        -e 's/^#* *autologin-session=.*/autologin-session=openbox/' \
        /etc/lightdm/lightdm.conf 2>/dev/null || true
    if ! grep -q '^greeter-session=' /etc/lightdm/lightdm.conf; then
        sed -i '/^\[Seat:\*\]$/a greeter-session=lightdm-gtk-greeter' /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    if ! grep -q '^user-session=' /etc/lightdm/lightdm.conf; then
        sed -i '/^\[Seat:\*\]$/a user-session=openbox' /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    if ! grep -q '^autologin-session=' /etc/lightdm/lightdm.conf; then
        sed -i '/^\[Seat:\*\]$/a autologin-session=openbox' /etc/lightdm/lightdm.conf 2>/dev/null || true
    fi
    log_info "LightDM set to X11 (openbox). Reboot or re-login for the change to take effect."
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
}

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
    TEAMVIEWER_ID="$(teamviewer info 2>/dev/null | awk '/ID/ {print $4; exit}')"
}

install_vnc() {
    log_step "Installing TigerVNC"
    if dpkg -s tigervnc-standalone-server >/dev/null 2>&1; then
        log_info "TigerVNC already installed; skipping package install."
    else
        apt-get install -y tigervnc-standalone-server tigervnc-common lxde-core >> "$INSTALL_LOG" 2>&1
    fi
    mkdir -p "$INSTALL_DIR/.vnc"
    if [ -n "$REMOTE_ACCESS_PASSWORD" ]; then
        echo "$REMOTE_ACCESS_PASSWORD" | vncpasswd -f > "$INSTALL_DIR/.vnc/passwd"
        chmod 600 "$INSTALL_DIR/.vnc/passwd"
    fi
    cat > "$INSTALL_DIR/.vnc/xstartup" <<'EOF'
#!/bin/bash
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
startlxde &
EOF
    chmod +x "$INSTALL_DIR/.vnc/xstartup"
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
    systemctl daemon-reload
    systemctl enable vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    systemctl start vncserver@1 >> "$INSTALL_LOG" 2>&1 || true
    VNC_CONNECTION="${DEFAULT_HOTSPOT_IP}:5901"
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
    rpi-connect on >> "$INSTALL_LOG" 2>&1 || true
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
        log_info "Step 'remote_access' already completed; ensuring virtual display if needed."
        if [ -f "$CONFIG_DIR/remote_access.conf" ] && command -v jq >/dev/null 2>&1; then
            if jq -e '(.anydesk.enabled == true) or (.teamviewer.enabled == true)' "$CONFIG_DIR/remote_access.conf" >/dev/null 2>&1; then
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
    if [ -z "$REMOTE_ACCESS_PASSWORD" ]; then
        REMOTE_ACCESS_PASSWORD="$HOTSPOT_PASSWORD"
    fi
    need_display=$(printf '%s\n' "${REMOTE_ACCESS_TOOLS[@]}" | grep -E '^(anydesk|teamviewer)$' | head -1)
    if [ -n "$need_display" ]; then
        install_virtual_display
        configure_lightdm_for_x11
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

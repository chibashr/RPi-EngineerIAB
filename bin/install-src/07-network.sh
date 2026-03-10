#!/usr/bin/env bash

# Ensure wlan0 is dedicated to hotspot: unmanage in NetworkManager, deny in dhcpcd,
# and run a script at boot that brings wlan0 up with 192.168.50.1 before hostapd.
configure_hotspot_priority() {
    if [ ! -d /sys/class/net/wlan0 ]; then
        return 0
    fi
    log_info "Configuring hotspot priority over WiFi client (Ubuntu / Raspberry Pi OS)."
    if systemctl is-active NetworkManager >/dev/null 2>&1 || [ -d /etc/NetworkManager/conf.d ]; then
        mkdir -p /etc/NetworkManager/conf.d
        cat > /etc/NetworkManager/conf.d/rpi-engineer-wlan0-unmanaged.conf <<'NMEOF'
# RPi Engineer-in-a-Box: use wlan0 for hotspot only; do not manage as WiFi client
[keyfile]
unmanaged-devices=interface-name:wlan0
NMEOF
        # Do not restart NetworkManager during install; user may be on WiFi. Config applies on reboot.
        log_info "NetworkManager: wlan0 will be unmanaged after reboot."
    fi
    if command -v dhcpcd >/dev/null 2>&1 && [ -f /etc/dhcpcd.conf ]; then
        if ! grep -q '^denyinterfaces wlan0' /etc/dhcpcd.conf 2>/dev/null; then
            echo "" >> /etc/dhcpcd.conf
            echo "# RPi Engineer-in-a-Box: do not manage wlan0 (used for hotspot)" >> /etc/dhcpcd.conf
            echo "denyinterfaces wlan0" >> /etc/dhcpcd.conf
            log_info "dhcpcd: denyinterfaces wlan0 added."
        fi
    fi
    cat > "$INSTALL_DIR/bin/setup-wlan0-hotspot.sh" <<'SETUPEOF'
#!/bin/bash
# Bring wlan0 under our control for hotspot; run before hostapd.
# If hotspot.secret exists, apply SSID/password to hostapd.conf so credentials persist across reboots.
set -e
WLAN=wlan0
IP="192.168.50.1/24"
CONFIG_DIR=/etc/rpi-engineer
HOTSPOT_SECRET="$CONFIG_DIR/hotspot.secret"
[ ! -d /sys/class/net/"$WLAN" ] && exit 0
# Unblock WiFi if soft-blocked by rfkill (required for hostapd to start the AP)
command -v rfkill >/dev/null 2>&1 && { rfkill unblock wlan 2>/dev/null; rfkill unblock wifi 2>/dev/null; true; }
# Release wlan0 from NetworkManager so we can configure it (avoids RTNETLINK Operation not permitted)
command -v nmcli >/dev/null 2>&1 && nmcli device set "$WLAN" managed no 2>/dev/null || true
systemctl stop wpa_supplicant@"$WLAN".service 2>/dev/null || true
systemctl stop wpa_supplicant@"$WLAN" 2>/dev/null || true
# wlan0/driver may not be ready at boot; retry bringing interface up and adding IP
try=1
max_tries=6
while [ "$try" -le "$max_tries" ]; do
    ip link set "$WLAN" down 2>/dev/null || true
    ip link set "$WLAN" up 2>/dev/null || true
    ip addr add "$IP" dev "$WLAN" 2>/dev/null || true
    if ip addr show "$WLAN" 2>/dev/null | grep -q "$IP"; then
        break
    fi
    [ "$try" -eq "$max_tries" ] && { echo "rpi-engineer-wlan0: failed to bring up $WLAN after $max_tries attempts" >&2; exit 2; }
    sleep 2
    try=$((try + 1))
done
# Apply persisted hotspot credentials so install/API-configured password survives reboot
if [ -f "$HOTSPOT_SECRET" ]; then
    HOTSPOT_SSID=$(sed -n '1p' "$HOTSPOT_SECRET")
    HOTSPOT_PASSWORD=$(sed -n '2p' "$HOTSPOT_SECRET")
    if [ -n "$HOTSPOT_SSID" ]; then
        mkdir -p /etc/hostapd
        {
            echo "interface=wlan0"
            echo "driver=nl80211"
            echo "ssid=$HOTSPOT_SSID"
            echo "hw_mode=g"
            echo "channel=6"
            echo "wmm_enabled=0"
            echo "macaddr_acl=0"
            echo "auth_algs=1"
            echo "ignore_broadcast_ssid=0"
            echo "wpa=2"
            printf "wpa_passphrase=%s\n" "$HOTSPOT_PASSWORD"
            echo "wpa_key_mgmt=WPA-PSK"
            echo "wpa_pairwise=TKIP"
            echo "rsn_pairwise=CCMP"
        } > /etc/hostapd/hostapd.conf
    fi
fi
exit 0
SETUPEOF
    chmod +x "$INSTALL_DIR/bin/setup-wlan0-hotspot.sh"
    cat > /etc/systemd/system/rpi-engineer-wlan0.service <<EOF
[Unit]
Description=RPi Engineer wlan0 hotspot setup (prefer hotspot over WiFi client)
Before=hostapd.service
After=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/bin/setup-wlan0-hotspot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    mkdir -p /etc/systemd/system/hostapd.service.d
    cat > /etc/systemd/system/hostapd.service.d/after-wlan0.conf <<'EOF'
[Unit]
After=rpi-engineer-wlan0.service
EOF
    systemctl daemon-reload
    # Do not run setup-wlan0-hotspot.sh here; user may be using WiFi for the install. Hotspot activates after reboot.
}

create_network_priority_script() {
    cat > "$INSTALL_DIR/bin/network-priority.sh" <<'EOF'
#!/bin/bash

test_connectivity() {
    local interface=$1
    ping -c 3 -W 5 -I "$interface" 8.8.8.8 > /dev/null 2>&1 && \
    nslookup google.com | grep -q "Address" > /dev/null 2>&1
}

for iface in /sys/class/net/usb*; do
    if [ -e "$iface" ]; then
        iface_name=$(basename "$iface")
        if test_connectivity "$iface_name"; then
            ip route replace default dev "$iface_name" metric 100
            exit 0
        fi
    fi
done

if test_connectivity eth0; then
    ip route replace default dev eth0 metric 200
    exit 0
fi

logger -t rpi-engineer "No WAN connectivity available"
exit 1
EOF
    chmod +x "$INSTALL_DIR/bin/network-priority.sh"
}

configure_hotspot() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "hotspot"; then log_info "Step 'hotspot' already completed; skipping."; HOTSPOT_CONFIGURED="yes"; return 0; fi
    log_step "Configuring WiFi hotspot"
    if [ ! -d /sys/class/net/wlan0 ]; then
        log_warn "wlan0 not found; skipping hotspot configuration."
        return 0
    fi
    if [ "$UPGRADE_SKIP_CONFIG" = "1" ]; then
        log_info "Using existing hotspot configuration (upgrade skip-config)."
        configure_hotspot_priority
        echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
        systemctl unmask hostapd >/dev/null 2>&1 || true
        # Do not start hostapd/dnsmasq during install; user may be on WiFi. They start after reboot.
        create_network_priority_script
        HOTSPOT_CONFIGURED="yes"
        return 0
    fi
    cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$HOTSPOT_SSID
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$HOTSPOT_PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    # Persist hotspot credentials so they survive reboot (applied by setup-wlan0-hotspot.sh at boot)
    # API (rpi-engineer) must write when user reconfigures hotspot from web UI
    mkdir -p "$CONFIG_DIR"
    printf '%s\n%s\n' "$HOTSPOT_SSID" "$HOTSPOT_PASSWORD" > "$CONFIG_DIR/hotspot.secret"
    chown "root:$SERVICE_GROUP" "$CONFIG_DIR/hotspot.secret"
    chmod 660 "$CONFIG_DIR/hotspot.secret"
    log_info "Hotspot credentials saved to $CONFIG_DIR/hotspot.secret (used at boot)."

    cat > /etc/dnsmasq.d/rpi-engineer.conf <<EOF
interface=wlan0
dhcp-range=$DEFAULT_HOTSPOT_DHCP_START,$DEFAULT_HOTSPOT_DHCP_END,255.255.255.0,24h
domain=local
address=/rpi-engineer.local/$DEFAULT_HOTSPOT_IP
EOF

    mkdir -p /etc/network/interfaces.d
    cat > /etc/network/interfaces.d/wlan0 <<EOF
auto wlan0
iface wlan0 inet static
    address $DEFAULT_HOTSPOT_IP
    netmask 255.255.255.0
EOF

    configure_hotspot_priority
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
    systemctl unmask hostapd >/dev/null 2>&1 || true
    # Do not start hostapd/dnsmasq during install; user may be on WiFi. They start after reboot.
    create_network_priority_script
    echo "WiFi hotspot configured (SSID: $HOTSPOT_SSID)."
    HOTSPOT_CONFIGURED="yes"
    mark_step_done "hotspot"
}

configure_firewall() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "firewall"; then log_info "Step 'firewall' already completed; skipping."; return 0; fi
    log_step "Configuring firewall"
    if [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
        log_warn "Container detected; skipping firewall configuration."
        return 0
    fi
    # Enable IPv4 forwarding for hotspot->WAN sharing (persists across reboot)
    if [ -d /etc/sysctl.d ]; then
        echo "net.ipv4.ip_forward=1" > /etc/sysctl.d/99-rpi-engineer.conf
        sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
    fi
    if ! command -v iptables >/dev/null 2>&1; then
        log_warn "iptables not available; skipping firewall configuration."
        return 0
    fi
    ensure_rule() {
        if ! iptables -C "$@" >/dev/null 2>&1; then
            iptables -A "$@"
        fi
    }
    ensure_nat_rule() {
        if ! iptables -t nat -C "$@" >/dev/null 2>&1; then
            iptables -t nat -A "$@"
        fi
    }
    iptables -P INPUT DROP
    iptables -P FORWARD DROP
    iptables -P OUTPUT ACCEPT
    ensure_rule INPUT -i lo -j ACCEPT
    ensure_rule INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    ensure_rule INPUT -i wlan0 -p tcp -m multiport --dports 80,443 -s 192.168.50.0/24 -j ACCEPT
    ensure_rule INPUT -i wlan0 -p udp --dport 53 -j ACCEPT
    ensure_rule INPUT -i wlan0 -p udp --dport 67:68 -j ACCEPT
    if [ -n "$LAN_SUBNET" ]; then
        ensure_rule INPUT -i eth0 -p tcp -m multiport --dports 80,443 -s "$LAN_SUBNET" -j ACCEPT
    fi
    ensure_rule FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    ensure_rule FORWARD -i wlan0 -o eth0 -j ACCEPT
    ensure_rule FORWARD -i wlan0 -o usb0 -j ACCEPT
    ensure_nat_rule POSTROUTING -o eth0 -j MASQUERADE
    ensure_nat_rule POSTROUTING -o usb0 -j MASQUERADE
    echo "Firewall rules configured."
    mark_step_done "firewall"
}

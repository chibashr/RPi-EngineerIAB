#!/usr/bin/env bash
# Create Xvfb systemd service and AnyDesk/TeamViewer drop-ins for headless use.
# Run on the device: sudo bash bin/setup-virtual-display.sh (or copy this file to the Pi and run there).

set -e
[ "$(id -u)" -eq 0 ] || { echo "Run as root (e.g. sudo $0)"; exit 1; }

apt-get install -y xvfb

cat > /etc/systemd/system/xvfb.service <<'EOF'
[Unit]
Description=X Virtual Frame Buffer for headless AnyDesk/TeamViewer
Before=anydesk.service teamviewerd.service

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :0 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /etc/systemd/system/anydesk.service.d
cat > /etc/systemd/system/anydesk.service.d/display.conf <<'EOF'
[Unit]
After=xvfb.service
Wants=xvfb.service

[Service]
Environment=DISPLAY=:0
EOF

mkdir -p /etc/systemd/system/teamviewerd.service.d
cat > /etc/systemd/system/teamviewerd.service.d/display.conf <<'EOF'
[Unit]
After=xvfb.service
Wants=xvfb.service

[Service]
Environment=DISPLAY=:0
EOF

systemctl unmask xvfb.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now xvfb
systemctl restart anydesk 2>/dev/null || true
systemctl restart teamviewerd 2>/dev/null || true
echo "Virtual display :0 is ready. AnyDesk/TeamViewer will use it after restart."

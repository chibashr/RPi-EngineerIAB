#!/usr/bin/env bash
# Create Xvfb + Openbox and AnyDesk/TeamViewer drop-ins for headless use.
# AnyDesk often needs a real X session (window manager), not just a bare Xvfb.
# Run on the device: sudo bash bin/setup-virtual-display.sh (or copy this file to the Pi and run there).

set -e
[ "$(id -u)" -eq 0 ] || { echo "Run as root (e.g. sudo $0)"; exit 1; }

apt-get install -y xvfb openbox

cat > /etc/systemd/system/xvfb.service <<'EOF'
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
EOF

cat > /etc/systemd/system/xvfb-wm.service <<'EOF'
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
EOF

mkdir -p /etc/systemd/system/anydesk.service.d
cat > /etc/systemd/system/anydesk.service.d/display.conf <<'EOF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
EOF

mkdir -p /etc/systemd/system/teamviewerd.service.d
cat > /etc/systemd/system/teamviewerd.service.d/display.conf <<'EOF'
[Unit]
After=xvfb.service xvfb-wm.service
Wants=xvfb.service xvfb-wm.service

[Service]
Environment=DISPLAY=:0
EOF

systemctl unmask xvfb.service 2>/dev/null || true
systemctl unmask xvfb-wm.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now xvfb xvfb-wm
systemctl restart anydesk 2>/dev/null || true
systemctl restart teamviewerd 2>/dev/null || true
echo "Virtual display :0 with Openbox is ready. Restart AnyDesk/TeamViewer if they were already running."
echo "If AnyDesk still shows 'display not supported', use TeamViewer or VNC for headless access."

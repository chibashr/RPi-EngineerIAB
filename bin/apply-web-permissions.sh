#!/usr/bin/env bash
# Apply nginx config, web root, and config dir permissions so the web UI is reachable
# and API can write (profiles, updates, hotspot). Run as root; can be invoked by the
# update manager via sudo after an update.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${RPI_ENGINEER_CONFIG_DIR:-/etc/rpi-engineer}"
SERVICE_GROUP="rpi-engineer"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx not found; skipping." >&2
    exit 0
fi

# Write nginx site config (allow all + correct root path).
cat > /etc/nginx/sites-available/rpi-engineer <<EOFCONFIG
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Explicitly allow LAN and hotspot; avoids 403 from system-wide deny rules.
    allow all;

    root ${INSTALL_DIR}/web;
    index index.html;

    location / {
        try_files \$uri \$uri/ =404;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOFCONFIG

ln -sf /etc/nginx/sites-available/rpi-engineer /etc/nginx/sites-enabled/rpi-engineer
rm -f /etc/nginx/sites-enabled/default

if [ -d "${INSTALL_DIR}/web" ]; then
    NGINX_USER="www-data"
    if [ -f /etc/nginx/nginx.conf ] && grep -q '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf; then
        NGINX_USER=$(grep '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf | head -1 | awk '{print $2}' | tr -d ';')
    fi
    if getent passwd "$NGINX_USER" >/dev/null 2>&1; then
        chown -R "$NGINX_USER:$NGINX_USER" "${INSTALL_DIR}/web"
    else
        chmod -R o+rX "${INSTALL_DIR}/web"
    fi
    for d in "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR"; do
        [ -d "$d" ] && chmod o+x "$d" 2>/dev/null || true
    done
fi

nginx -t 2>&1
if [ -d /run/systemd/system ]; then
    systemctl reload nginx 2>/dev/null || systemctl restart nginx
fi

# Ensure API (rpi-engineer) can write to config dirs for network profiles, updates, hotspot
if getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    for subdir in network_profiles network_configs module_config; do
        if [ -d "${CONFIG_DIR}/${subdir}" ]; then
            chown -R "root:${SERVICE_GROUP}" "${CONFIG_DIR}/${subdir}"
            find "${CONFIG_DIR}/${subdir}" -type d -exec chmod 775 {} \;
            find "${CONFIG_DIR}/${subdir}" -type f -exec chmod 664 {} \;
        fi
    done
    [ -f "${CONFIG_DIR}/version" ] && chown "root:${SERVICE_GROUP}" "${CONFIG_DIR}/version" && chmod 664 "${CONFIG_DIR}/version"
    [ -f "${CONFIG_DIR}/hotspot.secret" ] && chown "root:${SERVICE_GROUP}" "${CONFIG_DIR}/hotspot.secret" && chmod 660 "${CONFIG_DIR}/hotspot.secret"
fi

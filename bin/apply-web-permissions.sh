#!/usr/bin/env bash
# Apply nginx config, web root, config dir, and capture permissions so the web UI
# is reachable and API can write (profiles, updates, hotspot, packet capture).
# Run as root; can be invoked by the update manager via sudo after an update.
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${RPI_ENGINEER_CONFIG_DIR:-/etc/rpi-engineer}"
SERVICE_USER="rpi-engineer"
SERVICE_GROUP="rpi-engineer"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
fi

# Packet capture: allow tcpdump to capture without root (API runs as rpi-engineer)
TCPDUMP="$(command -v tcpdump 2>/dev/null)"
if [ -n "$TCPDUMP" ] && command -v setcap >/dev/null 2>&1; then
    setcap cap_net_raw,cap_net_admin=eip "$TCPDUMP" 2>/dev/null || true
fi
# Also allow dumpcap/tshark (live view, analysis)
DUMPCAP="$(command -v dumpcap 2>/dev/null)"
if [ -n "$DUMPCAP" ]; then
    # Ensure wireshark-common allows non-superusers to capture (Debian/Ubuntu)
    if dpkg -s wireshark-common >/dev/null 2>&1; then
        echo "wireshark-common wireshark-common/install-setuid boolean true" | debconf-set-selections 2>/dev/null || true
        DEBIAN_FRONTEND=noninteractive dpkg-reconfigure wireshark-common 2>/dev/null || true
    fi
    getent group wireshark >/dev/null 2>&1 && usermod -aG wireshark "$SERVICE_USER" 2>/dev/null || true
    DUMPCAP="$(readlink -f "$DUMPCAP" 2>/dev/null || echo "$DUMPCAP")"
    if command -v setcap >/dev/null 2>&1; then
        [ -u "$DUMPCAP" ] && chmod u-s "$DUMPCAP" 2>/dev/null || true
        setcap cap_net_raw,cap_net_admin=eip "$DUMPCAP" 2>/dev/null || true
    fi
fi
# Persistent capture dir: /var/lib/rpi-engineer/captures
DATA_DIR="${RPI_ENGINEER_DATA_DIR:-/var/lib/rpi-engineer}"
mkdir -p "${DATA_DIR}/captures"
getent group "$SERVICE_GROUP" >/dev/null 2>&1 && chown -R "$SERVICE_USER:$SERVICE_GROUP" "${DATA_DIR}/captures" 2>/dev/null || true
chmod -R 775 "${DATA_DIR}/captures" 2>/dev/null || true

# Ensure API (rpi-engineer) can run updates via web UI: install dir owned by service user.
# Run this even when nginx is absent so updates work.
if getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    chmod -R g+w "$INSTALL_DIR" 2>/dev/null || true
    [ -d "$INSTALL_DIR/.git" ] && chmod -R g+w "$INSTALL_DIR/.git" 2>/dev/null || true
    if command -v git >/dev/null 2>&1 && [ -d "$INSTALL_DIR/.git" ]; then
        git config --system --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
    fi
    for subdir in network_profiles network_configs module_config; do
        [ -d "${CONFIG_DIR}/${subdir}" ] && chown -R "root:${SERVICE_GROUP}" "${CONFIG_DIR}/${subdir}" && \
            find "${CONFIG_DIR}/${subdir}" -type d -exec chmod 775 {} \; 2>/dev/null || true && \
            find "${CONFIG_DIR}/${subdir}" -type f -exec chmod 664 {} \; 2>/dev/null || true
    done
    [ -f "${CONFIG_DIR}/version" ] && chown "root:${SERVICE_GROUP}" "${CONFIG_DIR}/version" && chmod 664 "${CONFIG_DIR}/version"
    [ -f "${CONFIG_DIR}/hotspot.secret" ] && chown "root:${SERVICE_GROUP}" "${CONFIG_DIR}/hotspot.secret" && chmod 660 "${CONFIG_DIR}/hotspot.secret"
fi

if ! command -v nginx >/dev/null 2>&1; then
    echo "nginx not found; skipping nginx config." >&2
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

    location /modules/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
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
        proxy_read_timeout 120;
        proxy_send_timeout 120;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
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
    chmod -R o+rX "${INSTALL_DIR}/web"
    for d in "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR"; do
        [ -d "$d" ] && chmod o+x "$d" 2>/dev/null || true
    done
fi

nginx -t 2>&1
if [ -d /run/systemd/system ]; then
    systemctl reload nginx 2>/dev/null || systemctl restart nginx
fi

# Restore web dir for nginx (permission block above set INSTALL_DIR to root:rpi-engineer)
if [ -d "${INSTALL_DIR}/web" ] && getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
    NGINX_USER="www-data"
    [ -f /etc/nginx/nginx.conf ] && grep -q '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf && \
        NGINX_USER=$(grep '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf | head -1 | awk '{print $2}' | tr -d ';')
    getent passwd "$NGINX_USER" >/dev/null 2>&1 && chown -R "$NGINX_USER:$NGINX_USER" "${INSTALL_DIR}/web"
fi

# Verify permissions; do not fail apply if verify fails (e.g. getcap not in PATH)
VERIFY_SCRIPT="${INSTALL_DIR}/bin/verify-permissions.sh"
if [ -x "$VERIFY_SCRIPT" ]; then
    if "$VERIFY_SCRIPT" 2>&1; then
        : # all checks passed
    else
        echo "verify-permissions reported issues; consider re-running this script or the installer." >&2
    fi
fi

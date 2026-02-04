#!/usr/bin/env bash

setup_user_permissions() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "permissions"; then log_info "Step 'permissions' already completed; skipping."; return 0; fi
    log_step "Setting up user permissions"
    echo "Creating service user/group if needed..."
    if ! getent group "$SERVICE_GROUP" >/dev/null 2>&1; then
        groupadd -r "$SERVICE_GROUP"
        echo "  Created group $SERVICE_GROUP"
    fi
    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        useradd -r -s /usr/sbin/nologin -d "$INSTALL_DIR" -g "$SERVICE_GROUP" "$SERVICE_USER"
        echo "  Created user $SERVICE_USER"
    fi
    echo "Setting ownership and permissions..."
    chown -R "root:$SERVICE_GROUP" "$INSTALL_DIR" "$DATA_DIR" "$LOG_DIR"
    chown -R "root:root" "$CONFIG_DIR"
    find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
    find "$INSTALL_DIR" -type f -exec chmod 644 {} \;
    find "$DATA_DIR" -type d -exec chmod 775 {} \;
    find "$DATA_DIR" -type f -exec chmod 640 {} \;
    find "$LOG_DIR" -type d -exec chmod 775 {} \;
    find "$LOG_DIR" -type f -exec chmod 640 {} \;
    chmod 755 "$CONFIG_DIR"
    chmod 644 "$CONFIG_DIR/"* 2>/dev/null || true
    chmod 600 "$CONFIG_DIR/install.conf" 2>/dev/null || true
    # remote_access.conf holds only connection IDs (no passwords); API runs as $SERVICE_USER and must read it
    if [ -f "$CONFIG_DIR/remote_access.conf" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/remote_access.conf"
        chmod 640 "$CONFIG_DIR/remote_access.conf"
    fi
    # Writable config dirs: API (rpi-engineer) must write for network profiles, updates, hotspot config
    for subdir in network_profiles network_configs module_config; do
        if [ -d "$CONFIG_DIR/$subdir" ]; then
            chown -R "root:$SERVICE_GROUP" "$CONFIG_DIR/$subdir"
            find "$CONFIG_DIR/$subdir" -type d -exec chmod 775 {} \;
            find "$CONFIG_DIR/$subdir" -type f -exec chmod 664 {} \;
        fi
    done
    if [ -f "$CONFIG_DIR/version" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/version"
        chmod 664 "$CONFIG_DIR/version"
    fi
    if [ -f "$CONFIG_DIR/hotspot.secret" ]; then
        chown "root:$SERVICE_GROUP" "$CONFIG_DIR/hotspot.secret"
        chmod 660 "$CONFIG_DIR/hotspot.secret"
    fi
    if [ -d "$INSTALL_DIR/bin" ]; then
        chmod 750 "$INSTALL_DIR/bin/"* 2>/dev/null || true
    fi
    # Allow git in install dir when run by root or service user (Git 2.35.2+ "dubious ownership")
    if command -v git >/dev/null 2>&1 && [ -d "$INSTALL_DIR/.git" ]; then
        git config --system --add safe.directory "$INSTALL_DIR" 2>/dev/null || true
        # Let service user run git fetch/reset when sudo is unavailable (e.g. container)
        chmod -R g+w "$INSTALL_DIR/.git" 2>/dev/null || true
    fi
    # Make install dir group-writable so the web UI can apply updates (service user runs git in-process
    # when sudo is unavailable, or when sudoers rule is not present; group write allows both paths).
    chmod -R g+w "$INSTALL_DIR" 2>/dev/null || true
    # dialout: serial port access (ttyUSB*, ttyACM*) for serial console
    usermod -a -G dialout "$SERVICE_USER" || true
    usermod -a -G netdev "$SERVICE_USER" || true
    mark_step_done "permissions"
}

create_master_service() {
    cat > /etc/systemd/system/rpi-engineer.service <<EOF
[Unit]
Description=RPi Engineer-in-a-Box Master Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/bin/start.sh
ExecStop=$INSTALL_DIR/bin/stop.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF
}

create_service_unit() {
    local name="$1"
    local description="$2"
    local exec_start="$3"
    local run_user="$4"
    local extra_env="${5:-}"
    cat > "/etc/systemd/system/${name}.service" <<EOF
[Unit]
Description=$description
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$exec_start
Restart=on-failure
RestartSec=5
User=$run_user
Group=$SERVICE_GROUP
Environment=PYTHONUNBUFFERED=1
${extra_env}
UMask=027
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF
}

configure_services() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "services"; then log_info "Step 'services' already completed; skipping."; SERVICES_CONFIGURED="yes"; return 0; fi
    log_step "Configuring systemd services"
    create_master_service
    local api_env="Environment=RPI_ENGINEER_ROOT=${INSTALL_DIR}
Environment=RPI_ENGINEER_DRY_RUN=0
Environment=RPI_ENGINEER_USE_GEVENT=1"
    create_service_unit "rpi-engineer-api" "RPi Engineer API Gateway" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/api_gateway/main.py" "$SERVICE_USER" "$api_env"
    create_service_unit "rpi-engineer-network" "RPi Engineer Network Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/network_manager/manager.py" "root"
    create_service_unit "rpi-engineer-serial" "RPi Engineer Serial Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/serial_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-capture" "RPi Engineer Capture Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/capture_manager/manager.py" "root"
    create_service_unit "rpi-engineer-system" "RPi Engineer System Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/system_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-monitor" "RPi Engineer Monitor Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/monitor_service/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-update" "RPi Engineer Update Manager" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/update_manager/manager.py" "$SERVICE_USER"
    create_service_unit "rpi-engineer-logging" "RPi Engineer Logging Service" "$INSTALL_DIR/venv/bin/python $INSTALL_DIR/services/logging_service/manager.py" "$SERVICE_USER"
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
    else
        log_warn "systemd not detected; skipping daemon-reload."
    fi
    SERVICES_CONFIGURED="yes"
    mark_step_done "services"
}

configure_nginx() {
    # Always re-apply nginx config so updates (e.g. 403 fix) take effect when install is re-run.
    log_step "Configuring nginx"
    if ! command -v nginx >/dev/null 2>&1; then
        log_warn "nginx not found; skipping nginx configuration."
        return 0
    fi
    cat > /etc/nginx/sites-available/rpi-engineer <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    # Explicitly allow LAN and hotspot; avoids 403 from system-wide deny rules.
    allow all;

    root /opt/rpi-engineer/web;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    # Module web assets (JS/CSS) are served by the API gateway from modules/<id>/web/.
    location /modules/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/rpi-engineer /etc/nginx/sites-enabled/rpi-engineer
    rm -f /etc/nginx/sites-enabled/default
    if [ -d "$INSTALL_DIR/web" ]; then
        NGINX_USER="www-data"
        if [ -f /etc/nginx/nginx.conf ] && grep -q '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf; then
            NGINX_USER=$(grep '^[[:space:]]*user[[:space:]]' /etc/nginx/nginx.conf | head -1 | awk '{print $2}' | tr -d ';')
        fi
        if getent passwd "$NGINX_USER" >/dev/null 2>&1; then
            chown -R "$NGINX_USER:$NGINX_USER" "$INSTALL_DIR/web"
        else
            chmod -R o+rX "$INSTALL_DIR/web"
        fi
        # Ensure nginx can traverse parent path (e.g. /opt, /opt/rpi-engineer).
        for d in "$(dirname "$INSTALL_DIR")" "$INSTALL_DIR"; do
            [ -d "$d" ] && chmod o+x "$d" 2>/dev/null || true
        done
    fi
    nginx -t 2>&1 | tee -a "$INSTALL_LOG"
    if [ -d /run/systemd/system ]; then
        systemctl restart nginx
    else
        log_warn "systemd not detected; nginx config written but not restarted."
    fi
    add_sudoers_rule() {
        local script="$1" name="$2"
        [ -f "$script" ] || return 0
        chmod 755 "$script"
        mkdir -p /etc/sudoers.d
        echo "$SERVICE_USER ALL=(root) NOPASSWD: $script" > "/etc/sudoers.d/rpi-engineer-$name"
        chmod 440 "/etc/sudoers.d/rpi-engineer-$name"
    }
    add_sudoers_rule "$INSTALL_DIR/bin/apply-web-permissions.sh" "apply-web-permissions"
    add_sudoers_rule "$INSTALL_DIR/bin/apply-update.sh" "apply-update"
    add_sudoers_rule "$INSTALL_DIR/bin/create-config-backup.sh" "create-config-backup"
    mark_step_done "nginx"
}

#!/usr/bin/env bash

# Install a single module: deps from module.json (jq), venv pip, optional install.sh.
# Failures in jq/pip/module install.sh are logged but do not abort; apt failures return 1
# so install_modules can log and continue with the next module.
install_module() {
    local module_name="$1"
    local module_dir="$INSTALL_DIR/modules/$module_name"
    local enabled_file="$CONFIG_DIR/modules_enabled.txt"
    if [ ! -d "$module_dir" ]; then
        log_warn "Module not found: $module_name"
        return 0
    fi
    if [ -f "$enabled_file" ] && grep -q "^${module_name}$" "$enabled_file"; then
        log_info "Module already enabled: $module_name"
    fi

    if [ -f "$module_dir/module.json" ]; then
        local sys_deps
        local py_deps
        sys_deps="$(jq -r '.dependencies.system[]? // empty' "$module_dir/module.json" 2>/dev/null)" || true
        py_deps="$(jq -r '.dependencies.python[]? // empty' "$module_dir/module.json" 2>/dev/null)" || true
        if [ -n "$sys_deps" ]; then
            while IFS= read -r dep; do
                [ -z "$dep" ] && continue
                if dpkg -s "$dep" >/dev/null 2>&1; then
                    continue
                fi
                apt_install_interactive "$dep" || { log_error "Failed to install $dep for module $module_name"; return 1; }
            done <<< "$sys_deps"
        fi
        if [ -n "$py_deps" ] && [ -x "$INSTALL_DIR/venv/bin/pip" ]; then
            export PIP_NO_INPUT=1
            while IFS= read -r dep; do
                [ -z "$dep" ] && continue
                if ! "$INSTALL_DIR/venv/bin/pip" install --no-input "$dep" >> "$INSTALL_LOG" 2>&1; then
                    log_error "Failed to install Python dependency '$dep' for module $module_name (see $INSTALL_LOG)"
                fi
            done <<< "$py_deps"
        fi
    fi

    if [ -f "$module_dir/install.sh" ]; then
        if ! bash "$module_dir/install.sh" >> "$INSTALL_LOG" 2>&1; then
            log_error "Module $module_name install script failed; check $INSTALL_LOG"
        fi
    fi

    mkdir -p "$CONFIG_DIR"
    touch "$enabled_file"
    if ! grep -q "^${module_name}$" "$enabled_file"; then
        echo "$module_name" >> "$enabled_file"
    fi
    log_info "Module installed: $module_name"
}

install_modules() {
    if [ "$INSTALL_MODE" = "upgrade" ]; then
        log_info "Upgrade: skipping module install (only updating rpi-engineer)."
        MODULES_INSTALLED="yes"
        return 0
    fi
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "modules"; then log_info "Step 'modules' already completed; skipping."; MODULES_INSTALLED="yes"; return 0; fi
    log_step "Installing modules"
    if [ "${#MODULE_SELECTIONS[@]}" -eq 0 ]; then
        log_info "No modules to install."
        return 0
    fi
    for module_name in "${MODULE_SELECTIONS[@]}"; do
        echo "Installing module: $module_name"
        install_module "$module_name" || log_error "Module $module_name failed to install; continuing with remaining modules."
    done
    echo "Modules installed."
    MODULES_INSTALLED="yes"
    mark_step_done "modules"
}

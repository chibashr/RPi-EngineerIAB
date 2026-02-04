#!/usr/bin/env bash

create_directories() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "directories"; then log_info "Step 'directories' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Creating directories"
    mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR"
    mkdir -p "$CONFIG_DIR/network_profiles" "$CONFIG_DIR/network_configs" "$CONFIG_DIR/module_config"
    mkdir -p "$DATA_DIR/captures" "$DATA_DIR/serial_logs" "$DATA_DIR/backups" "$DATA_DIR/database" "$DATA_DIR/updates" "$DATA_DIR/staging"
    APP_INSTALLED="yes"
    mark_step_done "directories"
}

backup_existing_install() {
    if [ "$INSTALL_MODE" != "upgrade" ]; then
        return 0
    fi
    if [ -d "$INSTALL_DIR" ]; then
        local backup_dir="/opt/rpi-engineer-backup-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backing up existing install to $backup_dir"
        cp -a "$INSTALL_DIR" "$backup_dir"
    fi
}

ensure_source_dir() {
    # When running from install dir (e.g. /opt/rpi-engineer), clone to get a fresh source
    # for deploy; otherwise we would skip deploy and leave broken/incomplete state.
    if [ "$SOURCE_DIR" = "$INSTALL_DIR" ]; then
        log_info "Running from install directory; cloning repository for deploy."
        local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
        echo "Cloning $REPO_URL (branch $BRANCH)..."
        if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
            log_error "git clone failed (check network and $INSTALL_LOG)."
            exit 1
        fi
        SOURCE_DIR="$clone_dir"
        echo "Repository cloned to $clone_dir"
        return 0
    fi
    # Require source to have critical files; otherwise clone so we do not deploy incomplete trees.
    if [ -d "$SOURCE_DIR/services" ] && [ -d "$SOURCE_DIR/web" ]; then
        if [ -f "$SOURCE_DIR/web/index.html" ] && [ -f "$SOURCE_DIR/services/logging_service/manager.py" ] && [ -f "$SOURCE_DIR/bin/apply-web-permissions.sh" ]; then
            return 0
        fi
        log_warn "Source directory missing critical files; cloning repository for deploy."
    else
        log_warn "Source directory not found; cloning repository."
    fi
    local clone_dir="/tmp/rpi-engineer-src-$(date +%s)"
    echo "Cloning $REPO_URL (branch $BRANCH)..."
    if ! git clone --branch "$BRANCH" "$REPO_URL" "$clone_dir" >> "$INSTALL_LOG" 2>&1; then
        log_error "git clone failed (check network and $INSTALL_LOG)."
        exit 1
    fi
    SOURCE_DIR="$clone_dir"
    echo "Repository cloned to $clone_dir"
}

copy_path() {
    local src="$1"
    local dest="$2"
    if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$src" "$dest"
    else
        rm -rf "$dest"
        cp -a "$src" "$dest"
    fi
}

get_source_git_hash() {
    if ! command -v git >/dev/null 2>&1; then
        return 0
    fi
    if [ -d "$INSTALL_DIR/.git" ]; then
        git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true
    fi
}

write_version_file() {
    local git_hash
    git_hash="$(get_source_git_hash | tr -d '[:space:]')"
    if [[ "$git_hash" =~ ^[0-9a-f]{40}$ ]]; then
        mkdir -p "$CONFIG_DIR"
        echo "$git_hash" > "$CONFIG_DIR/version"
        log_info "Version ref saved to $CONFIG_DIR/version"
    else
        log_warn "Version ref not written (git hash unavailable)."
    fi
}

deploy_files() {
    if [ "$INSTALL_MODE" = "continue" ] && step_already_done "deploy"; then log_info "Step 'deploy' already completed; skipping."; APP_INSTALLED="yes"; return 0; fi
    log_step "Deploying application files"
    if ! command -v git >/dev/null 2>&1; then
        log_error "git is required but not installed. Install git and re-run."
        exit 1
    fi

    if [ "$INSTALL_MODE" = "reinstall_from_scratch" ]; then
        if [ -d "$INSTALL_DIR" ]; then
            log_warn "Removing $INSTALL_DIR for clean reinstall."
            rm -rf "$INSTALL_DIR"
        fi
    fi

    if [ -d "$INSTALL_DIR/.git" ]; then
        if [ "$INSTALL_MODE" = "upgrade" ]; then
            backup_existing_install
        fi
        log_info "Existing git repository found at $INSTALL_DIR; updating."
        if git -C "$INSTALL_DIR" remote get-url origin >/dev/null 2>&1; then
            git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL" >> "$INSTALL_LOG" 2>&1 || true
        else
            git -C "$INSTALL_DIR" remote add origin "$REPO_URL" >> "$INSTALL_LOG" 2>&1 || true
        fi
        if ! git -C "$INSTALL_DIR" fetch origin "$BRANCH" >> "$INSTALL_LOG" 2>&1; then
            log_error "git fetch failed (check network and $INSTALL_LOG)."
            exit 1
        fi
        if ! git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" >> "$INSTALL_LOG" 2>&1; then
            log_error "git reset failed (check $INSTALL_LOG)."
            exit 1
        fi
    else
        if [ -d "$INSTALL_DIR" ] && [ "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
            log_warn "Install directory exists but is not a git repo. Backing up and replacing."
            backup_existing_install
            rm -rf "$INSTALL_DIR"
        fi
        mkdir -p "$(dirname "$INSTALL_DIR")"
        log_info "Cloning repository to $INSTALL_DIR (branch $BRANCH)."
        if ! git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >> "$INSTALL_LOG" 2>&1; then
            log_error "git clone failed (check network and $INSTALL_LOG)."
            exit 1
        fi
    fi

    for dir in web services lib bin; do
        if [ ! -d "$INSTALL_DIR/$dir" ]; then
            log_error "Deploy incomplete; missing $INSTALL_DIR/$dir"
            exit 1
        fi
    done
    echo "Application files deployed."
    write_version_file
    APP_INSTALLED="yes"
    mark_step_done "deploy"
}

# Core trees to verify on deploy/upgrade: every file under these is required and checked.
CORE_DIRS="web services lib bin"

# List all files under src_base (relative paths), excluding __pycache__, .pyc, .git.
# Usage: list_core_files "SOURCE_DIR/web"
list_core_files() {
    local src_base="$1"
    [ ! -d "$src_base" ] && return 0
    (cd "$src_base" && find . -type f \
        ! -path "*__pycache__*" ! -path "*/.git/*" ! -name "*.pyc" \
        | sed 's|^\./||')
}

# Verify every file under web, services, lib, bin exists at INSTALL_DIR; repair by re-copying dir then per-file.
# Returns 0 if all present, 1 if any still missing after repair.
verify_and_repair_core_assets() {
    local dir_name path missing_list="" total_missing=0
    for dir_name in $CORE_DIRS; do
        local src_base="$SOURCE_DIR/$dir_name"
        local dest_base="$INSTALL_DIR/$dir_name"
        [ ! -d "$src_base" ] && continue
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            if [ ! -e "$dest_base/$path" ]; then
                missing_list="${missing_list} ${dir_name}/${path}"
                total_missing=$((total_missing + 1))
            fi
        done < <(list_core_files "$src_base")
    done
    if [ "$total_missing" -eq 0 ]; then
        return 0
    fi
    log_warn "Missing core files after deploy ($total_missing):${missing_list}. Repairing from source."
    for dir_name in $CORE_DIRS; do
        [ -d "$SOURCE_DIR/$dir_name" ] && copy_path "$SOURCE_DIR/$dir_name" "$INSTALL_DIR/$dir_name"
    done
    total_missing=0
    missing_list=""
    for dir_name in $CORE_DIRS; do
        local src_base="$SOURCE_DIR/$dir_name"
        local dest_base="$INSTALL_DIR/$dir_name"
        [ ! -d "$src_base" ] && continue
        while IFS= read -r path; do
            [ -z "$path" ] && continue
            if [ ! -e "$dest_base/$path" ] && [ -e "$src_base/$path" ]; then
                mkdir -p "$(dirname "$dest_base/$path")"
                cp -a "$src_base/$path" "$dest_base/$path"
            fi
            if [ ! -e "$dest_base/$path" ]; then
                missing_list="${missing_list} ${dir_name}/${path}"
                total_missing=$((total_missing + 1))
            fi
        done < <(list_core_files "$src_base")
    done
    if [ "$total_missing" -gt 0 ]; then
        log_error "Core files still missing after repair ($total_missing):${missing_list}"
        return 1
    fi
    log_info "Core assets (web/services/lib/bin) verified and repaired."
    return 0
}

# Copy from current SOURCE_DIR to INSTALL_DIR (used by deploy_files).
deploy_copy_from_source() {
    echo "Copying services..."
    copy_path "$SOURCE_DIR/services" "$INSTALL_DIR/services"
    echo "Copying web..."
    copy_path "$SOURCE_DIR/web" "$INSTALL_DIR/web"
    echo "Copying lib..."
    copy_path "$SOURCE_DIR/lib" "$INSTALL_DIR/lib"
    echo "Copying modules..."
    copy_path "$SOURCE_DIR/modules" "$INSTALL_DIR/modules"
    if [ -d "$SOURCE_DIR/bin" ]; then
        echo "Copying bin..."
        copy_path "$SOURCE_DIR/bin" "$INSTALL_DIR/bin"
    fi
    if [ -f "$SOURCE_DIR/requirements.txt" ]; then
        cp "$SOURCE_DIR/requirements.txt" "$INSTALL_DIR/requirements.txt"
    fi
    verify_and_repair_core_assets || true
}

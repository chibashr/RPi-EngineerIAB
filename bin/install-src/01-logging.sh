#!/usr/bin/env bash

log_info() {
    echo "[INFO] $1" | tee -a "$INSTALL_LOG"
}

log_warn() {
    echo "[WARN] $1" | tee -a "$INSTALL_LOG"
}

log_error() {
    echo "[ERROR] $1" | tee -a "$INSTALL_LOG"
}

log_step() {
    echo "[STEP] $1" | tee -a "$INSTALL_LOG"
}

show_progress() {
    local message="$1"
    echo -n "$message... " | tee -a "$INSTALL_LOG"
}

progress_done() {
    echo "done" | tee -a "$INSTALL_LOG"
}

progress_fail() {
    echo "failed" | tee -a "$INSTALL_LOG"
}

# Repair/continue: track completed steps so an interrupted install can resume
step_already_done() {
    local step="$1"
    [ -f "$INSTALL_PROGRESS_FILE" ] && grep -q "^${step}$" "$INSTALL_PROGRESS_FILE" 2>/dev/null
}

mark_step_done() {
    local step="$1"
    echo "$step" >> "$INSTALL_PROGRESS_FILE"
}

# Simple scrolling progress only; no scroll region or cursor tricks.
PROGRESS_BAR_WIDTH=40
progress_init() {
    : # No-op; progress just scrolls with output
}

progress_ensure_region() {
    : # No-op; kept for call-site compatibility
}

progress_bar() {
    local current="$1"
    local total="$2"
    local label="${3:-}"
    local pct=0
    [ "$total" -gt 0 ] && pct=$((current * 100 / total))
    local filled=$((current * PROGRESS_BAR_WIDTH / total))
    [ "$filled" -gt "$PROGRESS_BAR_WIDTH" ] && filled=$PROGRESS_BAR_WIDTH
    local bar=""
    local i=0
    for ((i = 0; i < PROGRESS_BAR_WIDTH; i++)); do
        [ "$i" -lt "$filled" ] && bar="${bar}=" || bar="${bar}-"
    done
    local max_label_len=36
    [ "${#label}" -gt "$max_label_len" ] && label="${label:0:$((max_label_len - 3))}..."
    local line="[${bar}] ${pct}% ${label}"
    echo "$line"
    echo "[INFO] Progress: ${current}/${total} (${pct}%) ${label}" >> "$INSTALL_LOG"
}

progress_cleanup() {
    : # No-op; no scroll region to reset
}

detect_interrupted_install() {
    [ -f "$INSTALL_PROGRESS_FILE" ]
}

# Read from terminal when script is piped (e.g. curl | bash) so prompts work
# When NONINTERACTIVE=1, callers must set defaults before calling; this no-ops
interactive_read() {
    if [ "${NONINTERACTIVE:-0}" = "1" ]; then
        return 0
    fi
    if [ -t 0 ]; then
        read "$@"
    else
        [ -e /dev/tty ] && read "$@" < /dev/tty || return 0
    fi
}

debug_pause() {
    if [ "${DEBUG:-0}" = "1" ]; then
        interactive_read -r -p "Press Enter to continue..."
    fi
}

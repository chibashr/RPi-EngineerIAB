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

# Progress bar (apt-style: fixed at bottom of terminal, output scrolls above)
PROGRESS_BAR_WIDTH=40
PROGRESS_LINES=""
progress_init() {
    if [ ! -t 1 ]; then return 0; fi
    PROGRESS_LINES=$(tput lines 2>/dev/null) || true
    if [ -z "$PROGRESS_LINES" ] || [ "$PROGRESS_LINES" -le 2 ]; then return 0; fi
    # Reserve last line for progress bar; scroll region 1 to LINES-1 (1-based)
    tput csr 1 $((PROGRESS_LINES - 1)) 2>/dev/null || true
}

# Ensure scroll region is set (subprocesses like apt may reset it)
progress_ensure_region() {
    if [ ! -t 1 ] || [ -z "$PROGRESS_LINES" ] || [ "$PROGRESS_LINES" -le 2 ]; then return 0; fi
    tput csr 1 $((PROGRESS_LINES - 1)) 2>/dev/null || true
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
    if [ -t 1 ] && [ -n "$PROGRESS_LINES" ] && [ "$PROGRESS_LINES" -gt 1 ]; then
        progress_ensure_region
        # Move to last line, clear it, print bar, move cursor back into scroll area
        tput cup "$PROGRESS_LINES" 0 2>/dev/null || true
        tput el 2>/dev/null || true
        printf '\r%s' "$line"
        # Cursor at bottom of scroll area so next output appends correctly
        tput cup $((PROGRESS_LINES - 1)) 0 2>/dev/null || true
    fi
    echo "[INFO] Progress: ${current}/${total} (${pct}%) ${label}" >> "$INSTALL_LOG"
}

progress_cleanup() {
    if [ ! -t 1 ]; then return 0; fi
    # Clear the progress bar line (was in reserved last line) so it doesn't linger after summary.
    if [ -n "$PROGRESS_LINES" ] && [ "$PROGRESS_LINES" -gt 0 ]; then
        tput cup "$PROGRESS_LINES" 0 2>/dev/null || true
        tput el 2>/dev/null || true
    fi
    # Reset scroll region to full screen (ESC [ r)
    printf '\033[r' 2>/dev/null || true
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

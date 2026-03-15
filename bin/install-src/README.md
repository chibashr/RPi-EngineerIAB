# Install Script Sources

This directory contains the source fragments for `bin/install.sh`.

Workflow:

1. Edit the fragment files in this directory.
2. Run `bin/build-install.sh` (Linux/macOS) or `bin/build-install.ps1` (Windows) to regenerate `bin/install.sh`.
3. Commit both the fragments and the regenerated `bin/install.sh`.

The published `bin/install.sh` must remain a single file so the curl-pipe install
command continues to work:

`curl -fsSL https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install.sh | sudo bash`

## Install modes (when existing installation detected)

| Mode | Description |
|------|-------------|
| sync | Pull latest code from repo and restart services. No wizard, no deps. |
| upgrade | Sync files + reinstall deps + apply any missing config. |
| reconfigure | Re-run selected config sections only (hotspot/firewall/remote_access/modules). |
| repair | Scan for issues, report, confirm, then fix. |
| uninstall | Stop services, remove app, config, and optionally data/logs. |

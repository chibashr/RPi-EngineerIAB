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
| Upgrade | Update files and services; optionally re-run wizard |
| Quick update | Git fetch + reset only; no wizard, no deps |
| Reconfigure | Re-run wizard and config only |
| Uninstall | Stop services, remove app, config, and optionally data/logs |

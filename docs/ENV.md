# Environment variables

<!-- AUTO-GENERATED from codebase - do not edit the table manually. No .env.example present. -->

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `RPI_ENGINEER_ROOT` | No | Install root (default: `/opt/rpi-engineer`) | `/opt/rpi-engineer` |
| `RPI_ENGINEER_DATA_DIR` | No | Data directory (default: `/var/lib/rpi-engineer`) | `/var/lib/rpi-engineer` |
| `RPI_ENGINEER_CONFIG_DIR` | No | Config directory (default: `/etc/rpi-engineer`) | `/etc/rpi-engineer` |
| `RPI_ENGINEER_MODULES_DIR` | No | Modules directory (default: `/opt/rpi-engineer/modules`; in repo runs, falls back to `modules/`) | `/opt/rpi-engineer/modules` |
| `RPI_ENGINEER_API_BASE` | No | Base URL for API clients (default: `http://127.0.0.1:5000`) | `http://127.0.0.1:5000` |
| `RPI_ENGINEER_WS_BASE` | No | WebSocket base URL for serial/remote console UI (default: `ws://192.168.50.1`) | `ws://192.168.50.1` |
| `RPI_ENGINEER_DRY_RUN` | No | Dry-run mode for potentially destructive operations (0/1). **Default varies by service**; installer sets `RPI_ENGINEER_DRY_RUN=0` for production services. | `0` |
| `RPI_ENGINEER_VERSION` | No | App version fallback when no `config/version` or `data/version` file exists | `1.0.0` |
| `RPI_ENGINEER_ENV` | No | Environment name. `production` forces JSON log format. | `development` |
| `RPI_ENGINEER_DEBUG` | No | Debug mode toggle (0/1) | `1` |
| `RPI_ENGINEER_UPDATE_REPO` | No | Git repo for update check/apply (default: project repo) | `https://github.com/ORG/PROJECT1.git` |
| `RPI_ENGINEER_UPDATE_BRANCH` | No | Branch for update check/apply (default: `main`) | `main` |
| `RPI_ENGINEER_WAN_CHECK_INTERVAL` | No | WAN check interval in seconds (default: `60`) | `60` |
| `RPI_ENGINEER_AUTH_CONF` | No | Auth config path (default: `config/auth.conf` in repo; install may place under config dir) | `/etc/rpi-engineer/auth.conf` |
| `RPI_ENGINEER_AUDIT_LOG` | No | Audit log path (default: `data/audit.log` in repo; install may place under data dir) | `/var/lib/rpi-engineer/audit.log` |
| `RPI_ENGINEER_SERVICE_USER` | No | systemd service user used by `bin/apply-update.sh` (default: `rpi-engineer`) | `rpi-engineer` |
| `RPI_ENGINEER_SERVICE_GROUP` | No | systemd service group used by `bin/apply-update.sh` (default: `rpi-engineer`) | `rpi-engineer` |
| `RPI_ENGINEER_LAN_SUBNET` | No | Installer override for LAN subnet (used by `bin/install.sh`; unset = auto/interactive) | `192.168.50.0/24` |
| `RPI_ENGINEER_REMOVE_DATA` | No | Uninstall/remove-data toggle (0/1). When `1`, uninstall removes data/logs without prompting. | `1` |
| `RPI_ENGINEER_INSTALL_URL` | No | `bin/install-and-bootstrap.sh`: URL to `bin/install.sh` when using curl | `https://raw.githubusercontent.com/ORG/PROJECT1/main/bin/install.sh` |
| `RPI_ENGINEER_LOCAL_SRC` | No | `bin/install-and-bootstrap.sh`: local directory containing `bin/install.sh` (skips download) | `/opt/rpi-engineer-src` |
| `RPI_ENGINEER_SKIP_CLONE` | No | Installer hint to skip git clone and reuse existing `/opt/rpi-engineer` | `1` |
| `RPI_ENGINEER_REPO_ARCHIVE_URL` | No | `bin/install-and-bootstrap.sh`: tarball URL for repo source (mirror-friendly) | `https://example.com/PROJECT1/main.tar.gz` |
| `RPI_ENGINEER_REPO_ARCHIVE_TOP` | No | `bin/install-and-bootstrap.sh`: top-level dir inside repo tarball | `PROJECT1-main` |
| `RPI_ENGINEER_REPO_URL` | No | Installer mirror: git remote URL for clone/fetch | `https://git.example.com/ORG/PROJECT1.git` |
| `RPI_ENGINEER_REPO_BRANCH` | No | Installer mirror: branch to clone/reset to | `main` |
| `RPI_ENGINEER_WAN_IFACE` | No | `bin/install-and-bootstrap.sh`: interface treated as WAN (default: `eth1`) | `eth1` |
| `RPI_ENGINEER_HOTSPOT_SSID` | No | `bin/install-and-bootstrap.sh`: hotspot SSID (default: `RPi-Engineer`) | `RPi-Engineer` |
| `RPI_ENGINEER_HOTSPOT_PASSWORD` | No | `bin/install-and-bootstrap.sh`: hotspot password (default: `changeme1234`) | `changeme1234` |

<!-- END AUTO-GENERATED -->

## Logging

<!-- AUTO-GENERATED from codebase - do not edit the table manually -->

| Variable | Default | Description |
|----------|---------|-------------|
| `RPI_ENGINEER_LOG_DIR` | `/var/log/rpi-engineer` | Directory for rotating log files. Falls back to `logs/` in repo root if not writable. |
| `RPI_ENGINEER_LOG_LEVEL` | `INFO` | Log verbosity. Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `RPI_ENGINEER_LOG_FORMAT` | `plain` | Log format. Values: `plain` (human readable), `json` (structured). Overridden by `RPI_ENGINEER_ENV=production`. |
| `RPI_ENGINEER_LOG_EXPORT_DIR` | `/var/lib/rpi-engineer/exports` | Directory for log export downloads. |
| `RPI_ENGINEER_LOG_ROTATE_INTERVAL` | `3600` | Log rotation check interval (seconds). |
| `RPI_ENGINEER_LOG_MAX_SIZE_MB` | `10` | Max size per log file before rotation (MB). |
| `RPI_ENGINEER_LOG_RETAIN_DAYS` | `7` | Days to retain rotated logs. |

<!-- END AUTO-GENERATED -->

**Note**: No `.env.example` in repo. Add one to document local overrides. For install/deploy, the installer and systemd unit set the environment as needed.

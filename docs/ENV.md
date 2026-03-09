# Environment variables

<!-- AUTO-GENERATED from codebase - do not edit the table manually. No .env.example present. -->

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `RPI_ENGINEER_ROOT` | No | Install root (set by installer; default: /opt/rpi-engineer) | `/opt/rpi-engineer` |
| `RPI_ENGINEER_API_HOST` | No | API bind address (default: 0.0.0.0) | `0.0.0.0` |
| `RPI_ENGINEER_API_PORT` | No | API port (default: 5000) | `5000` |
| `RPI_ENGINEER_API_BASE` | No | API base URL for clients (default: http://127.0.0.1:5000) | `http://127.0.0.1:5000` |
| `RPI_ENGINEER_DEBUG` | No | Enable debug mode (0/1, default: 0) | `1` |
| `RPI_ENGINEER_DRY_RUN` | No | Dry-run mode for system/update commands (0/1; tests use 1) | `0` |
| `RPI_ENGINEER_VERSION` | No | App version fallback when no version file | `1.0.0` |
| `RPI_ENGINEER_ENV` | No | Environment name. Set to `production` for JSON log format. | `development` |
| `RPI_ENGINEER_DATA_DIR` | No | Data directory (default: /var/lib/rpi-engineer) | `/var/lib/rpi-engineer` |
| `RPI_ENGINEER_CONFIG_DIR` | No | Config directory (default: /etc/rpi-engineer) | `/etc/rpi-engineer` |
| `RPI_ENGINEER_MODULES_DIR` | No | Modules directory (default: /opt/rpi-engineer/modules or repo modules/) | `/opt/rpi-engineer/modules` |
| `RPI_ENGINEER_WS_BASE` | No | WebSocket base URL for serial UI (default: ws://192.168.50.1) | `ws://192.168.50.1` |
| `RPI_ENGINEER_UPDATE_REPO` | No | Git repo for updates (default: project repo) | `https://github.com/.../RPi-EngineerIAB.git` |
| `RPI_ENGINEER_UPDATE_BRANCH` | No | Branch for update check/apply (default: main) | `main` |
| `RPI_ENGINEER_WAN_CHECK_INTERVAL` | No | WAN check interval in seconds (default: 60) | `60` |

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

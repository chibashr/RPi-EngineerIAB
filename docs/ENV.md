# Environment variables

<!-- AUTO-GENERATED from codebase - do not edit the table manually. No .env.example present. -->

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `RPI_ENGINEER_ROOT` | No | Install root (set by installer; default: /opt/rpi-engineer) | `/opt/rpi-engineer` |
| `RPI_ENGINEER_API_HOST` | No | API bind address (default: 0.0.0.0) | `0.0.0.0` |
| `RPI_ENGINEER_API_PORT` | No | API port (default: 5000) | `5000` |
| `RPI_ENGINEER_DEBUG` | No | Enable debug mode (0/1, default: 0) | `1` |
| `RPI_ENGINEER_DRY_RUN` | No | Dry-run mode for updates (0/1, default: 0) | `0` |
| `RPI_ENGINEER_VERSION` | No | App version fallback when no version file | `1.0.0` |
| `RPI_ENGINEER_ENV` | No | Environment name (e.g. development). Set to `production` to enable JSON log format. | `development` |

<!-- END AUTO-GENERATED -->

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `RPI_ENGINEER_LOG_DIR` | `/var/log/rpi-engineer` | Directory for rotating log files. Falls back to `logs/` in repo root if not writable. |
| `RPI_ENGINEER_LOG_LEVEL` | `INFO` | Log verbosity. Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `RPI_ENGINEER_LOG_FORMAT` | `plain` | Log format. Values: `plain` (human readable), `json` (structured). Overridden by `RPI_ENGINEER_ENV=production`. |
| `RPI_ENGINEER_ENV` | (unset) | Set to `production` to enable JSON log format and production defaults. |

**Note**: No `.env.example` in repo. Add one to document local overrides. For install/deploy, the installer and systemd unit set the environment as needed.

# Logging Service

Provides log file listing, filtered reads, export, and a **rotation daemon**. Also supports **unified alerting**: recent WARNING and ERROR log lines are exposed as alert-shaped records and merged with monitor (health) alerts in the system status API and WebSocket stream.

## Daemon (rpi-engineer-logging)

When run as `python services/logging_service/manager.py`, the service runs a daemon that:

- Rotates log files when they exceed `RPI_ENGINEER_LOG_MAX_SIZE_MB` (default 10)
- Removes rotated files older than `RPI_ENGINEER_LOG_RETAIN_DAYS` (default 7)
- Runs rotation every `RPI_ENGINEER_LOG_ROTATE_INTERVAL` seconds (default 3600)
- Handles SIGTERM/SIGINT for clean shutdown

## API

- `get_recent_log_alerts(limit=50)` — returns `{severity, message, timestamp, source: "log"}` for recent WARNING/ERROR lines across all `.log` files. Used by `GET /api/v1/system/status` and `/ws/status`.

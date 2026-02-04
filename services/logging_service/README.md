# Logging Service

Provides log file listing, filtered reads, and export. Also supports **unified alerting**: recent WARNING and ERROR log lines are exposed as alert-shaped records and merged with monitor (health) alerts in the system status API and WebSocket stream, so the same alerts appear in the Dashboard, Logs page, and top-bar bell.

- `get_recent_log_alerts(limit=50)` — returns `{severity, message, timestamp, source: "log"}` for recent WARNING/ERROR lines across all `.log` files in the configured log dir. Used by `GET /api/v1/system/status` and `/ws/status` to build the unified alerts list.

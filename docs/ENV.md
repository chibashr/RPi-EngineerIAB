# Environment variables

<!-- AUTO-GENERATED from codebase - do not edit the table manually. No .env.example present. -->

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `RPI_ENGINEER_API_HOST` | No | API bind address (default: 0.0.0.0) | `0.0.0.0` |
| `RPI_ENGINEER_API_PORT` | No | API port (default: 5000) | `5000` |
| `RPI_ENGINEER_DEBUG` | No | Enable Flask debug (0/1, default: 0) | `1` |
| `RPI_ENGINEER_USE_GEVENT` | No | Use gevent for WSGI (0/1, default: 1) | `1` |
| `RPI_ENGINEER_VERSION` | No | App version fallback when no version file | `1.0.0` |
| `RPI_ENGINEER_ENV` | No | Environment name (e.g. development) | `development` |

<!-- END AUTO-GENERATED -->

**Note**: No `.env.example` in repo. Add one to document local overrides. For install/deploy, the installer and systemd unit set the environment as needed.

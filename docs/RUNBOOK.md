# Runbook

## Deployment

- **Install**: Run installer from repo (e.g. `curl -fsSL .../bin/install.sh | sudo bash`). See [Installation Specification](.planning/INSTALLATION-SPECIFICATION.md) and [Deployment Guide](.planning/DEPLOYMENT-GUIDE.md).
- **Upgrade**: Re-run installer (Upgrade) or use in-app update (Updates page) when available.
- **Config**: Hostname, remote access tool, WiFi hotspot password, network profiles. Backup/restore via API: GET /api/v1/backup/config, POST /api/v1/backup/restore.

## Health and monitoring

- **Health check**: `GET /health` → `{"data":{"status":"healthy"}}`. Use for load balancers or monitoring.
- **API base**: Default http://192.168.50.1 (hotspot) or http://&lt;device-ip&gt;:5000. Port configurable via `RPI_ENGINEER_API_PORT`.
- **Logs**: `journalctl -u rpi-engineer-api` (or service name as configured). Log level via env/config.

## Common issues

| Issue | Action |
|-------|--------|
| API unreachable | Check API service is running; check port and firewall; ensure venv has dependencies (`pip install -r requirements.txt`). |
| ModuleNotFoundError: flask | Install API deps: `sudo /opt/rpi-engineer/venv/bin/pip install -r /opt/rpi-engineer/requirements.txt` (adjust path to install dir). |
| Serial/capture permission | Run with appropriate user/group or sudo for device access. |
| Update check fails | Ensure deploy is a git clone and remote is reachable; version file may hold ref for comparison. |

## Rollback

- **App update**: Use in-app rollback (POST /api/v1/updates/rollback) if supported; otherwise re-run installer to previous version or restore from backup.
- **Config**: Restore from backup (POST /api/v1/backup/restore) if config was changed.

## Related

- [Deployment Guide](.planning/DEPLOYMENT-GUIDE.md) — pre-deployment checklist, site procedures, troubleshooting
- [Installation Specification](.planning/INSTALLATION-SPECIFICATION.md) — install and upgrade details

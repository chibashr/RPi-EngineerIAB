# SNMP Trap Receiver Module

Receives SNMP traps over UDP and provides live and stored views in the web UI.

## Features
- UDP trap listener (default port 1162)
- Live in-memory buffer for recent traps
- Optional persistence to SQLite with retention controls
- API endpoints for status, recent, and stored traps

## Configuration
Configuration is stored in `config.json` under the module data directory.

Default values:
- `enabled`: `true`
- `bind_address`: `0.0.0.0`
- `port`: `1162`
- `persist`: `true`
- `max_stored`: `10000`
- `max_live`: `500`

## Dependencies
- Python: `pysnmp`

## Notes
- Port 162 is privileged; if you switch to 162, ensure the service has the required permissions.

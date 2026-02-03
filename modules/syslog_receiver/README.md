# Syslog Receiver Module

Receives syslog messages over UDP and TCP and provides live and stored views in the web UI.

## Features
- UDP and TCP listeners (default port 1514)
- Live in-memory buffer for recent messages
- Optional persistence to SQLite with retention controls
- API endpoints for status, recent, and stored messages

## Configuration
Configuration is stored in `config.json` under the module data directory.

Default values:
- `enabled`: `true`
- `bind_address`: `0.0.0.0`
- `port_udp`: `1514`
- `port_tcp`: `1514`
- `persist`: `true`
- `max_stored`: `10000`
- `max_live`: `1000`

## Notes
- Port 514 is privileged; if you switch to 514, ensure the service has the required permissions.

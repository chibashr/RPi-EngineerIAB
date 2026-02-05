# RPi Engineer-in-a-Box

[![GitHub](https://img.shields.io/badge/GitHub-chibashr%2FRPi--EngineerIAB-blue)](https://github.com/chibashr/RPi-EngineerIAB)

A portable network diagnostic and remote access platform for network engineers and technicians. Transform a Raspberry Pi into a comprehensive field diagnostic tool with remote access, serial console management, packet capture, and network interface management.

## Features

- **Remote Access** – AnyDesk, TeamViewer, VNC, or Raspberry Pi Connect for remote desktop access
- **Serial Console** – Multiple USB serial sessions with full logging and file transfer
- **Packet Capture** – Live capture and analysis with BPF filters
- **Network Management** – WiFi hotspot, automatic failover, VLAN support
- **Web Interface** – Simple and Advanced modes for all skill levels

## Quick Start

### For Users

1. Install Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+) on Raspberry Pi 3B+, 4, or 5
2. Run the installer:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install.sh | sudo bash
   ```
3. Connect to WiFi hotspot `RPi-Engineer-XXXX` and open http://192.168.50.1

Re-run the installer for upgrade, quick update (repo only), reconfigure, or uninstall.

See [Installation Specification](.planning/INSTALLATION-SPECIFICATION.md) for details.

### For Implementers

1. Read [Project Overview](.planning/PROJECT-OVERVIEW.md) for goals and use cases
2. Read [System Architecture](.planning/SYSTEM-ARCHITECTURE.md) for technical design
3. Follow [Development Guide](.planning/DEVELOPMENT-GUIDE.md) for setup
4. Reference feature docs in `.planning/` during implementation

### Web Interface (Phase 3)

The web interface is served from the static `web/` directory by the API gateway.
Simple Mode is the default landing page at `/`, with Advanced Mode under
`/advanced/` as additional HTML pages. All CSS, JavaScript, and HTML are stored
on the device so the UI works **offline**; the installer and in-app updater
verify and repair required web assets so the deploy is complete.

## Documentation

| Document | Purpose |
|----------|---------|
| [Specification Suite](.planning/README.md) | Complete spec index and roadmap |
| [Project Overview](.planning/PROJECT-OVERVIEW.md) | Goals, users, use cases |
| [System Architecture](.planning/SYSTEM-ARCHITECTURE.md) | Technical design |
| [Installation](.planning/INSTALLATION-SPECIFICATION.md) | Installation procedures |
| [API Reference](.planning/API-REFERENCE.md) | REST and WebSocket APIs |
| [Deployment Guide](.planning/DEPLOYMENT-GUIDE.md) | Pre-deployment and site procedures |

## Requirements

- Raspberry Pi 3B+, 4, or 5
- Ubuntu Server 22.04+ or Raspberry Pi OS (Debian Bookworm or later)
- Recommended: USB cellular modem for mobile connectivity

## License

See LICENSE file for details.

## Author

chibashr

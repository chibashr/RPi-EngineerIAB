# Remote Access Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Supported Tools](#supported-tools)
3. [Installation and Configuration](#installation-and-configuration)
4. [Connection Management](#connection-management)
5. [Display Integration](#display-integration)
6. [Unattended Access](#unattended-access)
7. [Multi-Tool Support](#multi-tool-support)
8. [Status Monitoring](#status-monitoring)
9. [Security Considerations](#security-considerations)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Remote Access feature enables network engineers to remotely connect to the RPi Engineer-in-a-Box device from their workstations, providing full graphical desktop access for advanced configuration, troubleshooting, and device management. This is the primary use case for the system.

### Core Requirements

**Functional Requirements**:
- Support multiple remote access tools (AnyDesk, TeamViewer, VNC, Raspberry Pi Connect)
- Automatic startup on boot
- Unattended access (no user approval required)
- Display connection IDs in web interface
- Display connection IDs on physical display (if connected)
- Service health monitoring
- Connection status tracking
- Multiple tools can run simultaneously

**Non-Functional Requirements**:
- Low latency for remote desktop (<100ms on good connection)
- Reliable connection establishment
- Automatic reconnection after network interruption
- Minimal resource usage when idle
- Works over cellular connection (USB jetpack)
- No manual configuration required after setup

### Use Cases

**Primary Use Case**: Remote Engineer Access
- Engineer needs to access device at remote site
- Device powered on and connected to internet via USB jetpack
- Engineer opens AnyDesk (or TeamViewer) on workstation
- Engineer enters connection ID displayed on web interface
- Connection established automatically (unattended)
- Engineer has full desktop access to RPi
- Engineer can access web interface, serial consoles, packet captures
- Engineer performs troubleshooting and configuration
- Engineer disconnects when done

**Secondary Use Case**: Multiple Remote Access Methods
- Organization uses different remote access tools
- Device configured with both AnyDesk and TeamViewer during setup
- Both services running simultaneously
- Engineer uses whichever tool they prefer
- Connection IDs for both displayed in web interface

**Tertiary Use Case**: Physical Display Status
- Device deployed at site with HDMI display connected
- Display shows connection information (AnyDesk ID, WiFi credentials)
- Technician on-site can read information without accessing web interface
- Useful when network connectivity issues prevent web access

---

## Supported Tools

### Tool Selection

**Four primary options**:
1. **AnyDesk** (Recommended)
2. **TeamViewer**
3. **TigerVNC** (Open source alternative)
4. **Raspberry Pi Connect** (Raspberry Pi OS only; free, browser-based)

**Selection Criteria**:
- **AnyDesk**: Fast, lightweight, low latency, free for personal use
- **TeamViewer**: Well-known, enterprise features, requires license for commercial use
- **VNC**: Open source, no licensing concerns, requires VNC viewer client
- **Raspberry Pi Connect**: Official RPi solution, free, access via connect.raspberrypi.com; requires Raspberry Pi OS Bookworm+

**User Choice**:
- User selects tool(s) during installation
- Can select multiple tools (all will be installed and run)
- Default recommendation: AnyDesk

### Tool Comparison

| Feature | AnyDesk | TeamViewer | TigerVNC | Raspberry Pi Connect |
|---------|---------|------------|----------|----------------------|
| **Performance** | Excellent | Excellent | Good | Good |
| **Latency** | Very Low | Very Low | Low-Medium | Low-Medium |
| **Licensing** | Free (personal) | License required | Free (open source) | Free |
| **NAT Traversal** | Automatic | Automatic | Manual (port forwarding) | Automatic |
| **Unattended Access** | Yes | Yes | Yes (with auth) | Yes (Raspberry Pi ID) |
| **Mobile Apps** | Yes | Yes | Yes (limited) | Browser only |
| **Clipboard Sync** | Yes | Yes | Yes | Yes |
| **File Transfer** | Yes | Yes | No (native) | No (native) |
| **Setup Complexity** | Low | Low | Medium | Low |
| **Platform** | Ubuntu/RPi OS | Ubuntu/RPi OS | Ubuntu/RPi OS | Raspberry Pi OS only |

**Recommendation Logic**:
- **Enterprise**: TeamViewer (if licensed)
- **Small Business/Personal**: AnyDesk
- **Raspberry Pi OS users**: Raspberry Pi Connect (native, free)
- **Security-Conscious/No Internet**: VNC (over VPN)

---

## Installation and Configuration

### Installation Process

**During System Setup**:
1. Installation script asks: "Select remote access tool(s):"
   - [1] AnyDesk (Recommended)
   - [2] TeamViewer
   - [3] TigerVNC
   - [4] Raspberry Pi Connect (Raspberry Pi OS only)
   - [5] Multiple (select after)
   - [6] None (skip)

2. If "Multiple" selected:
   - Show checkboxes for each tool
   - User can select any combination

3. Script installs selected tool(s)
4. Script configures unattended access
5. Script retrieves and stores connection ID(s)
6. Script enables services to start on boot

### AnyDesk Installation

**Installation Steps**:
1. Add AnyDesk repository to apt sources
2. Download and install AnyDesk package (arm64)
3. Configure for unattended access:
   - Set password for unattended access
   - Disable user approval requirement
   - Set display name (e.g., "RPi-Engineer-XXXX")
4. Enable automatic startup (systemd service)
5. Retrieve AnyDesk ID
6. Store ID in configuration file
7. Test connection (optional ping to AnyDesk servers)

**Configuration Files**:
- Service: `/etc/systemd/system/anydesk.service`
- Config: `/etc/anydesk/` (managed by AnyDesk)
- ID Storage: `/etc/rpi-engineer/remote_access.conf`

**Service Configuration**:
```
[Unit]
Description=AnyDesk Remote Desktop
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/anydesk --service
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Unattended Access Setup**:
- Set password using: `echo "password" | anydesk --set-password`
- Password stored encrypted by AnyDesk
- Password complexity: 8+ characters, alphanumeric
- Password configured during installation, can be changed later

**Connection ID Retrieval**:
- Command: `anydesk --get-id`
- Returns 9-digit ID (e.g., 123456789)
- ID is persistent (doesn't change unless reinstalled)
- ID stored in config for web interface display

### TeamViewer Installation

**Installation Steps**:
1. Download TeamViewer Host package (arm64)
2. Install package with dependencies
3. Accept license agreement (automated)
4. Configure for unattended access:
   - Enable unattended access
   - Set password
   - Set device name
5. Register device with TeamViewer account (optional)
6. Enable automatic startup
7. Retrieve TeamViewer ID
8. Store ID in configuration

**Configuration Files**:
- Service: `/etc/systemd/system/teamviewerd.service`
- Config: `/opt/teamviewer/config/` (managed by TeamViewer)
- ID Storage: `/etc/rpi-engineer/remote_access.conf`

**Service Configuration**:
- TeamViewer provides its own daemon (teamviewerd)
- Enable: `systemctl enable teamviewerd`
- Start: `systemctl start teamviewerd`

**Unattended Access Setup**:
- Command: `teamviewer passwd [password]`
- Set account assignment (optional): `teamviewer setup`
- Enable unattended: Automatic with password set

**Connection ID Retrieval**:
- Command: `teamviewer info`
- Parses output for TeamViewer ID (9-10 digits)
- ID persistent unless device reassigned

### TigerVNC Installation

**Installation Steps**:
1. Install TigerVNC server package
2. Install lightweight desktop environment (LXDE or XFCE)
3. Create VNC password
4. Configure VNC server:
   - Set display resolution
   - Set port (default 5901)
   - Configure desktop environment startup
5. Create systemd service for VNC server
6. Enable automatic startup
7. Configure firewall (if enabled)

**Configuration Files**:
- Service: `/etc/systemd/system/vncserver@.service`
- Password: `/home/rpi-engineer/.vnc/passwd`
- Startup: `/home/rpi-engineer/.vnc/xstartup`
- Config: `/home/rpi-engineer/.vnc/config`

**Service Configuration**:
```
[Unit]
Description=TigerVNC Server
After=syslog.target network.target

[Service]
Type=forking
User=rpi-engineer
ExecStart=/usr/bin/vncserver :1 -geometry 1920x1080 -depth 24
ExecStop=/usr/bin/vncserver -kill :1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Password Setup**:
- Command: `vncpasswd` (interactive)
- Or: `echo "password" | vncpasswd -f > ~/.vnc/passwd`
- Password file permissions: 600 (read-write owner only)

**Connection Information**:
- Connection: `<rpi_ip_address>:5901` or `<rpi_ip_address>:1`
- Display: `:1` (first VNC display)
- No persistent ID (uses IP address)
- Must configure firewall to allow port 5901

**Desktop Environment**:
- Install LXDE (lightweight): `apt install lxde-core`
- Or XFCE: `apt install xfce4 xfce4-goodies`
- Configure `.vnc/xstartup` to launch desktop:
  ```
  #!/bin/bash
  unset SESSION_MANAGER
  unset DBUS_SESSION_BUS_ADDRESS
  startlxde &
  ```

### Raspberry Pi Connect Installation

**Requirements**: Raspberry Pi OS (Debian Bookworm or later) only. Not available on Ubuntu.

**Installation Steps**:
1. Install rpi-connect package: `apt install rpi-connect` (or `rpi-connect-lite` for shell-only on Lite)
2. Start Connect: `rpi-connect on`
3. Sign in with Raspberry Pi ID: `rpi-connect signin` (or use auth key for headless)
4. Enable user-lingering for headless: `loginctl enable-linger` (keeps Connect running when not logged in)

**Configuration**:
- No numeric connection ID; access via https://connect.raspberrypi.com
- Device appears in Connect dashboard when signed in
- Web interface displays "connect.raspberrypi.com" as access URL

**Connection Information**:
- Access URL: `connect.raspberrypi.com`
- Device identified by name in Raspberry Pi ID account
- Screen sharing requires Wayland (Desktop/Full); Lite has shell-only via rpi-connect-lite

### Configuration Storage

**Configuration File**: `/etc/rpi-engineer/remote_access.conf`

Format (JSON):
```json
{
  "tools_enabled": ["anydesk", "teamviewer"],
  "anydesk": {
    "enabled": true,
    "id": "123456789",
    "display_name": "RPi-Engineer-A1B2",
    "service_status": "running",
    "last_check": "2026-02-01T10:30:00Z"
  },
  "teamviewer": {
    "enabled": true,
    "id": "987654321",
    "device_name": "RPi-Engineer-A1B2",
    "service_status": "running",
    "last_check": "2026-02-01T10:30:00Z"
  },
  "vnc": {
    "enabled": false,
    "port": 5901,
    "display": ":1",
    "connection_string": "192.168.50.1:5901"
  },
  "rpi_connect": {
    "enabled": false,
    "access_url": "connect.raspberrypi.com",
    "signed_in": false
  }
}
```

---

## Connection Management

### Service Management

**Service Control**:
- All remote access tools managed as systemd services
- Services enabled to start on boot
- Automatic restart on failure
- Status monitoring

**Service Operations**:
- **Start**: `systemctl start anydesk` (or teamviewerd, vncserver@1)
- **Stop**: `systemctl stop anydesk`
- **Restart**: `systemctl restart anydesk`
- **Status**: `systemctl status anydesk`
- **Enable**: `systemctl enable anydesk` (start on boot)
- **Disable**: `systemctl disable anydesk` (don't start on boot)

**Health Monitoring**:
- Check service status periodically (every 60 seconds)
- If service stopped unexpectedly, restart automatically (systemd handles)
- Log status changes
- Update web interface with current status

### Connection Tracking

**Connection Events**:
- **Connected**: Remote user connected
- **Disconnected**: Remote user disconnected
- **Failed**: Connection attempt failed

**Logging**:
- All connection events logged to system log
- Log includes:
  - Timestamp
  - Tool used (AnyDesk, TeamViewer, VNC)
  - Event type (connected, disconnected)
  - Remote IP address (if available)
  - Duration (for disconnection events)

**Connection History**:
- Stored in database
- Accessible via web interface
- Columns: Timestamp, Tool, Event, Duration, Remote IP
- Useful for audit and troubleshooting

### Network Requirements

**Outbound Connectivity**:
- AnyDesk and TeamViewer require internet access
- Use relay servers for NAT traversal (no port forwarding needed)
- VNC requires port forwarding or VPN (not recommended over public internet)

**Bandwidth**:
- Minimum: 1 Mbps (acceptable for remote desktop)
- Recommended: 3+ Mbps (smooth experience)
- USB jetpack typically provides 5-50 Mbps (sufficient)

**Latency**:
- Acceptable: <200ms
- Good: <100ms
- Excellent: <50ms
- High latency = sluggish remote desktop experience

**Firewall**:
- AnyDesk: Outbound TCP 80, 443, 6568 (no inbound required)
- TeamViewer: Outbound TCP 5938 (no inbound required)
- VNC: Inbound TCP 5901 (or 5900 + display number)

---

## Display Integration

### Web Interface Display

**Connection Information Card** (Simple Mode):
- Section: "Remote Access"
- For each enabled tool:
  - Tool name (e.g., "AnyDesk")
  - Connection ID (large, readable font)
  - "Copy ID" button
  - Connection status (Connected, Disconnected, Offline)
  - Status indicator (green dot = service running, red = stopped)

**Example Display**:
```
╔═══════════════════════════════════╗
║      Remote Access                ║
╠═══════════════════════════════════╣
║  AnyDesk                          ║
║  ID: 123 456 789    [Copy]        ║
║  ● Service Running                ║
║  ○ Not Connected                  ║
╠═══════════════════════════════════╣
║  TeamViewer                       ║
║  ID: 987 654 321    [Copy]        ║
║  ● Service Running                ║
║  ● Connected                      ║
╚═══════════════════════════════════╝
```

**Advanced Mode**:
- Full page: `/advanced/remote-access.html`
- Detailed information:
  - Service status (running, stopped, failed)
  - Uptime
  - Last connection (timestamp)
  - Current connection (if any):
    - Remote IP address
    - Duration
    - "Disconnect" button (if supported)
  - Service controls (start, stop, restart)
  - Configuration options

**Connection ID Formatting**:
- AnyDesk/TeamViewer: Display with spaces for readability
  - Raw: `123456789`
  - Displayed: `123 456 789`
- VNC: Display as `<IP>:5901`
  - Example: `192.168.50.1:5901`

**Copy to Clipboard**:
- "Copy ID" button uses Clipboard API
- Copies raw ID (without spaces) for easy pasting
- Visual feedback: Button changes to "Copied!" for 2 seconds
- Fallback: Show prompt with ID for manual copy

### Physical Display Output

**Display Module** (Optional):
- If LCD/OLED display module installed
- Display shows:
  - WiFi SSID and password
  - AnyDesk ID (or TeamViewer ID)
  - Service status indicator
  - IP addresses

**Display Layout** (Example for 128x64 OLED):
```
┌──────────────────────────┐
│ RPi Engineer             │
│                          │
│ WiFi: RPi-Engineer-A1B2  │
│ Pass: ********           │
│                          │
│ AnyDesk: 123 456 789     │
│ Status: ● Running        │
│                          │
│ IP: 192.168.50.1         │
└──────────────────────────┘
```

**Display Update**:
- Refreshes every 10 seconds
- Shows current status
- Cycles through information if multiple tools enabled
- Low power consumption

**Display Module Specification**:
- Supported displays: SSD1306, SH1106, SSD1327 (I2C or SPI)
- Resolution: 128x64 or 128x32
- Connection: I2C (address 0x3C or 0x3D)
- Python library: luma.oled or Adafruit libraries
- Module configurable via web interface

---

## Unattended Access

### Configuration

**Purpose**:
- Allow remote connections without on-site approval
- Essential for unmanned sites
- Engineer can connect anytime device is powered on

**Setup Requirements**:
- Password set during installation
- Service configured to allow unattended access
- No user prompt for incoming connections

**AnyDesk Unattended Setup**:
- Set unattended password: `anydesk --set-password`
- Password stored encrypted
- Configure settings:
  - Disable permission requests
  - Enable unattended access mode
  - Set display name

**TeamViewer Unattended Setup**:
- Set password: `teamviewer passwd [password]`
- Unattended access automatically enabled with password
- Optional: Assign to TeamViewer account for management

**VNC Unattended Setup**:
- VNC always unattended (password-only authentication)
- No user approval mechanism
- Password set in `.vnc/passwd` file

### Password Management

**Password Requirements**:
- Minimum 8 characters
- Alphanumeric (letters and numbers)
- Special characters recommended
- Different from system passwords

**Password Storage**:
- AnyDesk: Encrypted by AnyDesk internally
- TeamViewer: Encrypted by TeamViewer internally
- VNC: Encrypted in `.vnc/passwd` file

**Password Changes**:
- Via web interface: System Management > Remote Access
- Change password form:
  - Current password (for verification, if possible)
  - New password
  - Confirm new password
- Apply button (restarts service with new password)

**Password Recovery**:
- If password lost:
  - Must have physical or SSH access to device
  - Reset password using command line
  - Or reconfigure service via web interface (requires admin access)

---

## Multi-Tool Support

### Running Multiple Tools

**Simultaneous Operation**:
- All selected tools run concurrently
- Each tool independent
- Each uses different ports/protocols (no conflict)
- All connection IDs displayed

**Use Case**:
- Organization uses multiple tools
- Different engineers prefer different tools
- Redundancy (if one tool fails, use another)
- Transition period (migrating from one tool to another)

**Resource Considerations**:
- Each tool consumes memory and CPU
- Idle tools have minimal resource usage (<50MB RAM each)
- Active connections consume more (during remote session)
- Raspberry Pi 4 4GB: Can run all three tools comfortably
- Raspberry Pi 3B+ 1GB: Recommend single tool

### Tool Selection

**Web Interface**:
- Show all enabled tools
- Toggle to enable/disable each tool
- Changes require service restart
- Confirmation dialog if disabling only tool

**Recommendation Display**:
- If user enables multiple tools, show note:
  - "Multiple tools enabled. This is fine, but only one is typically needed."
  - "Running multiple tools uses more resources."
- Allow user to proceed

### Failover

**Automatic Failover**:
- If one remote access tool fails, others remain available
- Web interface shows which tools are operational
- Engineer can try alternative tool if primary fails

**Manual Failover**:
- Engineer has connection IDs for all enabled tools
- If can't connect via AnyDesk, try TeamViewer
- No automatic switching (engineer chooses tool)

---

## Status Monitoring

### Service Health Checks

**Monitoring Process**:
- Backend service checks status every 60 seconds
- Query systemd for service state
- Check if process running
- Test connectivity (ping AnyDesk/TeamViewer servers if possible)
- Update status in database and web interface

**Health States**:
- **Running**: Service active and healthy
- **Stopped**: Service not running (manual stop or not enabled)
- **Failed**: Service crashed or failed to start
- **Degraded**: Service running but network connectivity issues

**Automatic Recovery**:
- systemd automatically restarts failed services
- Restart delay: 10 seconds (configurable)
- Maximum restart attempts: Unlimited (systemd default)
- If service fails repeatedly, alert shown in web interface

### Connection Status

**Current Connection**:
- AnyDesk/TeamViewer: Can query if remote session active
- VNC: Check for active connections on port 5901
- Display in web interface:
  - "Connected" (green) or "Not Connected" (gray)
  - Remote IP address (if available)
  - Connection duration (if active)

**Connection History**:
- Table of past connections
- Columns: Timestamp, Tool, Duration, Remote IP, Event (connect/disconnect)
- Sortable and filterable
- Export as CSV

### Web Interface Status Display

**Simple Mode**:
- Connection Information Card shows basic status
- Service running: Green dot
- Service stopped: Red dot
- Connected: "Connected" text with green indicator
- Not connected: "Not Connected" text with gray indicator

**Advanced Mode**:
- Detailed status page
- Each tool has section:
  - Service status badge (Running, Stopped, Failed)
  - Uptime
  - Connection ID
  - Current connection details (if any)
  - Last connection (timestamp)
  - Connection history (last 10)
- Service control buttons (Start, Stop, Restart)
- View full connection history link

---

## Security Considerations

### Access Control

**Physical Security**:
- Remote access provides full device control
- Physical access to RPi = ability to reset passwords
- Recommendation: Keep device physically secure

**Network Security**:
- AnyDesk/TeamViewer use encrypted connections (TLS)
- VNC encryption depends on configuration (recommend VNC over SSH tunnel)
- All tools should use strong passwords

**Password Security**:
- Strong passwords enforced (8+ characters, complexity)
- Passwords not displayed in web interface (only "Change Password" option)
- Passwords stored encrypted by respective tools
- Change default passwords after installation

### Audit Logging

**Connection Logging**:
- All connections logged to system log
- Includes: Timestamp, tool, event, remote IP, duration
- Logs retained per system log retention policy (default 7 days)
- Can export connection history for audit

**Log Access**:
- Logs viewable in web interface (Logs & Monitoring page)
- Filter by: Remote access tool, date range, event type
- Export logs for external audit

### Threat Mitigation

**Unauthorized Access**:
- Risk: Someone obtains connection ID and password
- Mitigation: Strong passwords, change regularly
- Detection: Monitor connection history for unexpected connections

**Service Exploitation**:
- Risk: Vulnerability in AnyDesk/TeamViewer/VNC
- Mitigation: Keep services updated, apply security patches
- System update mechanism handles tool updates

**Network Eavesdropping**:
- Risk: Connection intercepted on network
- Mitigation: AnyDesk/TeamViewer use encryption (TLS)
- VNC: Use SSH tunnel or encrypted VNC variant

### Best Practices

**Recommendations**:
- Use strong, unique passwords for remote access
- Change passwords after initial setup (from default)
- Monitor connection history regularly
- Update remote access tools via system updates
- Use AnyDesk or TeamViewer for best security (over VNC)
- If using VNC, tunnel over SSH or VPN

---

## Troubleshooting

### Common Issues

**Issue: Service Not Starting**
- **Symptoms**: Web interface shows service stopped or failed
- **Causes**:
  - Service not enabled at boot
  - Configuration error
  - Missing dependencies
  - Permission issues
- **Solutions**:
  - Check service status: `systemctl status anydesk`
  - View service logs: `journalctl -u anydesk`
  - Enable service: `systemctl enable anydesk`
  - Restart service: `systemctl restart anydesk`
  - Reinstall tool if necessary

**Issue: Cannot Connect Remotely**
- **Symptoms**: Connection times out or fails
- **Causes**:
  - No internet connectivity
  - Firewall blocking outbound connections
  - Service not running
  - Wrong connection ID
- **Solutions**:
  - Check internet connectivity (WAN status in web interface)
  - Verify service running (web interface or systemctl)
  - Verify correct connection ID (copy from web interface)
  - Check firewall rules (shouldn't be issue with default config)
  - Try alternative tool if multiple enabled

**Issue: Connection ID Not Displayed**
- **Symptoms**: Web interface shows "Unknown" or blank for connection ID
- **Causes**:
  - Service not fully initialized
  - ID not retrieved during setup
  - Configuration file corrupt
- **Solutions**:
  - Wait 30 seconds (service may be initializing)
  - Restart service (may retrieve ID on startup)
  - Manually retrieve ID:
    - AnyDesk: `anydesk --get-id`
    - TeamViewer: `teamviewer info`
  - Update configuration file manually if needed

**Issue: Unattended Access Not Working**
- **Symptoms**: Remote connection requires on-site approval
- **Causes**:
  - Unattended access not configured
  - Password not set
  - Setting reverted (tool update, config reset)
- **Solutions**:
  - Reconfigure unattended access (web interface or command line)
  - Set/reset password
  - Verify settings in tool's configuration

**Issue: Poor Remote Desktop Performance**
- **Symptoms**: Laggy, slow screen updates, disconnections
- **Causes**:
  - Slow internet connection (cellular link)
  - High latency
  - Insufficient bandwidth
  - CPU overload on RPi
- **Solutions**:
  - Check internet speed (WAN status in web interface)
  - Reduce desktop resolution (if VNC)
  - Close unnecessary applications on RPi
  - Try different remote access tool (some optimized better)
  - Accept slower performance on cellular connection

**Issue: Service Crashes Repeatedly**
- **Symptoms**: Service shows "failed" state, logs show crashes
- **Causes**:
  - Software bug
  - System resource exhaustion (memory, CPU)
  - Corrupt configuration
- **Solutions**:
  - View logs for crash details: `journalctl -u anydesk`
  - Check system resources (CPU, memory in web interface)
  - Try default configuration (backup and reset config)
  - Update service (system update)
  - Report bug to tool vendor if persistent

### Diagnostic Procedures

**Check Service Status**:
1. Open web interface
2. Navigate to System Management > Remote Access (Advanced Mode)
3. View service status for each enabled tool
4. If status not "Running", click "Start" or "Restart"

**Test Connectivity**:
1. Verify WAN connected (Network Management page)
2. Test internet connectivity (ping 8.8.8.8 from system)
3. If VNC, test port open: `nc -zv 192.168.50.1 5901` (from another device)

**Retrieve Connection Information**:
1. View web interface Connection Information Card
2. Or retrieve manually:
   - AnyDesk: `anydesk --get-id`
   - TeamViewer: `teamviewer info | grep "TeamViewer ID"`
   - VNC: Connection string is `<ip>:5901` (IP shown in web interface)

**Reset Configuration**:
1. Stop service: `systemctl stop anydesk`
2. Backup config: `cp -r /etc/anydesk /etc/anydesk.backup`
3. Remove config: `rm -rf /etc/anydesk`
4. Reinstall package: `apt reinstall anydesk`
5. Reconfigure unattended access
6. Restart service: `systemctl start anydesk`

---

## Integration with System

### API Endpoints

**Service Management**:
- `GET /api/v1/remote-access/tools` - List configured tools
- `GET /api/v1/remote-access/tools/{tool_name}` - Get tool details
- `POST /api/v1/remote-access/tools/{tool_name}/start` - Start service
- `POST /api/v1/remote-access/tools/{tool_name}/stop` - Stop service
- `POST /api/v1/remote-access/tools/{tool_name}/restart` - Restart service

**Configuration**:
- `PUT /api/v1/remote-access/tools/{tool_name}/config` - Update configuration
- `POST /api/v1/remote-access/tools/{tool_name}/password` - Change password

**Status and History**:
- `GET /api/v1/remote-access/status` - Get overall status (all tools)
- `GET /api/v1/remote-access/history` - Get connection history (all tools)
- `GET /api/v1/remote-access/tools/{tool_name}/history` - Get history for one tool

### Web Interface Pages

**Simple Mode**:
- Connection Information Card on landing page
- Shows IDs and status for all enabled tools

**Advanced Mode**:
- Remote Access page (`/advanced/remote-access.html`)
- Sections:
  - Tool Status (one card per tool)
  - Connection History (table)
  - Configuration (change passwords, enable/disable)

### Display Module Integration

**If Display Module Installed**:
- Remote access information included in display output
- Rotates between WiFi info and remote access info
- User can configure which information to display (module settings)

---

## Future Enhancements

### Advanced Features

**Connection Notifications**:
- Email notification when remote connection established
- SMS notification (if SMS module installed)
- Push notification to mobile app (future)

**Session Recording**:
- Record remote desktop sessions for audit
- Playback capability
- Storage management for recordings

**Multi-Factor Authentication**:
- Require second factor for remote access
- Time-based codes (TOTP)
- Integration with authentication services

**Access Control**:
- Whitelist specific remote IPs
- Time-based access (allow connections only during certain hours)
- User-specific accounts (multiple engineers, different access levels)

**Performance Optimization**:
- Adaptive quality based on connection speed
- Bandwidth usage monitoring and alerts
- Optimize for low-bandwidth connections

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial remote access specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- INSTALLATION-SPECIFICATION.md
- WEB-INTERFACE-SPECIFICATION.md
- SECURITY-SPECIFICATION.md

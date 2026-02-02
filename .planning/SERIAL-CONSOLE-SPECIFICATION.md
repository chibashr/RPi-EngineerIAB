# Serial Console Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Serial Device Management](#serial-device-management)
3. [Device Detection](#device-detection)
4. [Session Management](#session-management)
5. [Terminal Emulation](#terminal-emulation)
6. [Session Logging](#session-logging)
7. [File Transfer](#file-transfer)
8. [Configuration Management](#configuration-management)
9. [Multi-Session Support](#multi-session-support)
10. [Error Handling](#error-handling)

---

## Overview

### Purpose

The Serial Console feature provides comprehensive management of USB-to-serial adapters and console sessions to network devices. It enables engineers to configure routers, switches, firewalls, and other network equipment through serial connections, with full logging and file transfer capabilities.

### Core Requirements

**Functional Requirements**:
- Automatic detection of USB serial devices
- Support for multiple simultaneous console sessions
- Configurable serial port parameters (baud rate, parity, etc.)
- Full-featured terminal emulation
- Complete session logging with timestamps
- File transfer capabilities (send and receive)
- Session history and log management
- WebSocket-based real-time communication

**Non-Functional Requirements**:
- Low latency (<50ms for console input/output)
- Support for at least 8 simultaneous sessions
- Reliable data transmission (no character loss)
- Session logs retained until manually deleted
- Works with common USB-to-serial chipsets (FTDI, Prolific, CH340)

### Use Cases

**Primary Use Case**: Network Device Configuration
- Engineer connects USB-to-serial cable to network device
- Opens serial console through web interface
- Executes configuration commands
- Session automatically logged
- Engineer can review logs later or export for documentation

**Secondary Use Case**: Multi-Device Configuration
- Multiple serial cables connected to different devices
- Engineer opens multiple console sessions simultaneously
- Switches between sessions via web interface
- All sessions logged independently

**Tertiary Use Case**: Firmware Updates
- Engineer needs to upload firmware to network device
- Uses file transfer feature to send firmware file
- Monitors transfer progress
- Receives confirmation from device

### Supported Hardware

**USB-to-Serial Chipsets**:
- FTDI (FT232, FT2232, FT4232) - Preferred
- Prolific (PL2303) - Supported
- CH340/CH341 - Supported
- Silicon Labs CP210x - Supported
- Any chipset with Linux kernel driver support

**Device Path Patterns**:
- `/dev/ttyUSB[0-9]` - Most USB serial adapters
- `/dev/ttyACM[0-9]` - Some USB serial adapters
- `/dev/serial/by-id/*` - Persistent device naming
- `/dev/serial/by-path/*` - Path-based naming

---

## Serial Device Management

### Device Enumeration

**Detection Process**:
1. On system boot, scan for existing serial devices
2. Monitor for USB hotplug events (device connect/disconnect)
3. Identify device type and chipset
4. Assign friendly name based on chipset/path
5. Load default or saved configuration for device
6. Make device available in web interface

**Device Information**:
- **Device Path**: Kernel-assigned path (e.g., /dev/ttyUSB0)
- **Vendor ID**: USB vendor identifier
- **Product ID**: USB product identifier  
- **Chipset**: Detected chipset type (FTDI, Prolific, etc.)
- **Serial Number**: Device serial number (if available)
- **Friendly Name**: User-assignable name (defaults to path)
- **Connection Status**: Available, In Use, Disconnected
- **Current Configuration**: Baud rate, data bits, parity, stop bits, flow control

**Device States**:
- **Available**: Device detected and ready for use
- **In Use**: Active console session open
- **Disconnected**: Device was present but removed
- **Error**: Device present but cannot be opened (permission issue, hardware fault)

### Device Monitoring

**Hotplug Detection**:
- Monitor udev events for USB device changes
- Detect new serial device connections in real-time
- Detect device disconnections
- Update web interface automatically via WebSocket
- Handle disconnection during active session gracefully

**Health Monitoring**:
- Check device accessibility periodically
- Detect permission issues
- Identify hung or unresponsive devices
- Report errors to system logs and web interface

### Device Permissions

**Access Control**:
- Service user must be member of `dialout` group
- Device permissions: `rw-rw----` (root:dialout)
- Handle permission errors gracefully
- Provide helpful error messages if access denied

**Multi-User Considerations**:
- Only one console session per device at a time
- Attempting to open in-use device shows error
- Option to force-close existing session (with warning)

---

## Device Detection

### Automatic Discovery

**Discovery Process**:
1. On service start, enumerate all `/dev/tty*` devices
2. Query device information via ioctl calls
3. Read USB device information from sysfs
4. Match against known chipset patterns
5. Create device object with full metadata
6. Emit device discovery event

**Detection Triggers**:
- Service startup (full scan)
- USB hotplug event (single device)
- Manual refresh (user-initiated)
- Periodic scan (every 30 seconds as backup)

**Device Identification**:
- Read vendor/product IDs from USB subsystem
- Match against database of known serial chipsets
- Detect chipset driver in use
- Determine device capabilities (baud rates supported, etc.)

### Device Database

**Known Chipsets**:
```
FTDI FT232:
  - Vendor ID: 0x0403
  - Product ID: 0x6001
  - Baud rates: 300-3000000
  - Features: Full modem control, FIFO
  
Prolific PL2303:
  - Vendor ID: 0x067b
  - Product ID: 0x2303
  - Baud rates: 75-6000000
  - Notes: Some variants have driver issues
  
CH340:
  - Vendor ID: 0x1a86
  - Product ID: 0x7523
  - Baud rates: 50-2000000
  - Notes: Requires ch341 kernel module
```

**Custom Device Definitions**:
- Allow user to add custom vendor/product IDs
- Specify friendly names for specific devices
- Override default configurations
- Persist in configuration file

### Device Presentation

**Web Interface Display**:
- List all detected devices
- Group by status (Available, In Use, Disconnected)
- Show key information for each:
  - Friendly name or path
  - Chipset type
  - Current baud rate
  - Status indicator (color-coded dot)
  - "Open Console" button
  - "Configure" button

**Device Sorting**:
- Primary: By path (ttyUSB0, ttyUSB1, etc.)
- Secondary: By friendly name (alphabetical)
- User can customize sort order

**Empty State**:
- No devices detected: Show helpful message
- Suggest checking USB connections
- Link to troubleshooting documentation
- Show "Refresh" button

---

## Session Management

### Session Lifecycle

**Session Creation**:
1. User clicks "Open Console" on device
2. Backend attempts to open serial port
3. Apply configured or default port parameters
4. Allocate session ID (UUID)
5. Create session object with metadata
6. Establish WebSocket connection for data
7. Start session logging
8. Notify user of successful connection

**Session States**:
- **Connecting**: Opening device, establishing connection
- **Active**: Session open, data flowing
- **Paused**: Logging paused, connection maintained
- **Disconnecting**: Graceful shutdown in progress
- **Closed**: Session terminated
- **Error**: Connection failed or error occurred

**Session Termination**:
1. User clicks "Close" or closes web page
2. Backend closes serial port
3. Flush and close log file
4. Release device (mark as Available)
5. Clean up session resources
6. Update session record (end time, final status)

### Session Metadata

**Information Tracked**:
- **Session ID**: Unique identifier (UUID)
- **Device Path**: Which serial device (e.g., /dev/ttyUSB0)
- **Friendly Name**: User-assigned device name
- **Start Time**: ISO 8601 timestamp
- **End Time**: ISO 8601 timestamp (when closed)
- **Duration**: Calculated from start/end times
- **Port Configuration**: Baud rate, parity, etc. at session start
- **Bytes Transmitted**: Total bytes sent to device
- **Bytes Received**: Total bytes received from device
- **Log File Path**: Location of session log
- **Log File Size**: Size in bytes
- **User Notes**: Optional user-added notes

**Session Persistence**:
- Active sessions tracked in memory
- Session history saved to database
- Can retrieve past sessions for review
- Old sessions can be pruned based on age

### Multi-Session Coordination

**Simultaneous Sessions**:
- Support up to 8 simultaneous sessions (configurable)
- Each session on different serial device
- Independent WebSocket connections
- Separate logging per session
- User can switch between sessions in web interface

**Session Listing**:
- Table or card view of all active sessions
- Show: Device name, start time, duration, bytes Rx/Tx
- Actions per session:
  - Switch to (bring to foreground)
  - Pause/Resume logging
  - Close session
- "Close All Sessions" button with confirmation

**Session Switching**:
- Click on session to bring console to front
- WebSocket remains connected for all sessions
- Terminal displays only active session
- Background sessions buffer data (configurable buffer size)

---

## Terminal Emulation

### Emulator Requirements

**Terminal Type**:
- Emulate VT100/VT220/ANSI terminal
- Support common control sequences
- Handle cursor movement, colors, attributes
- Scrollback buffer (configurable size, default 10,000 lines)

**Display Features**:
- Monospace font (Consolas, Monaco, or similar)
- Configurable font size (10pt, 12pt, 14pt, 16pt)
- Color schemes (light, dark, custom)
- ANSI color support (8 or 16 colors)
- Bold, underline, reverse video attributes

**Input Handling**:
- Raw keyboard input sent to device
- Special key handling:
  - Ctrl+C: Send 0x03 (interrupt)
  - Ctrl+D: Send 0x04 (EOF)
  - Ctrl+Z: Send 0x1A (suspend)
  - Tab: Send 0x09 (tab)
  - Enter: Send CR, LF, or CRLF (configurable)
  - Arrow keys: Send ANSI escape sequences
  - Function keys: Send appropriate sequences
- Paste support (with line delay option)
- Local echo option (for debugging)

**Terminal Features**:
- Auto-scroll to bottom (toggleable)
- Scrollback navigation (mouse wheel, scrollbar)
- Text selection and copy
- Find/search in buffer
- Clear screen
- Save terminal output

### WebSocket Communication

**Data Flow**:
```
Web Browser <--(WebSocket)--> Backend Service <--(Serial)--> Network Device
```

**WebSocket Protocol**:
- URL: `ws://192.168.50.1/ws/serial/<session_id>`
- Message format: Binary or text
- Binary: Raw serial data (for file transfer)
- Text: JSON-wrapped data with metadata

**Message Types**:

Inbound (Browser → Backend):
```json
{
  "type": "data",
  "data": "show running-config\n"
}
```
```json
{
  "type": "resize",
  "rows": 24,
  "cols": 80
}
```
```json
{
  "type": "control",
  "action": "pause_logging"
}
```

Outbound (Backend → Browser):
```json
{
  "type": "data",
  "data": "Router# show running-config\nBuilding configuration..."
}
```
```json
{
  "type": "status",
  "bytes_tx": 1234,
  "bytes_rx": 5678,
  "duration": 125
}
```
```json
{
  "type": "error",
  "message": "Device disconnected"
}
```

**Flow Control**:
- Backend buffers data if WebSocket slow
- Drop oldest data if buffer full (warn user)
- Configurable buffer size (default 1MB)

### Terminal Configuration

**Settings Available**:
- **Font Family**: Monospace font selection
- **Font Size**: 10pt to 20pt
- **Line Height**: 1.0 to 2.0
- **Color Scheme**: Light, Dark, Solarized, Monokai, custom
- **Cursor Style**: Block, underline, bar
- **Cursor Blink**: On/off
- **Scrollback Size**: 1,000 to 100,000 lines
- **Line Wrap**: On/off
- **Local Echo**: On/off
- **Timestamps**: None, relative, absolute
- **Bell**: Visual, audio, none

**Per-Session Settings**:
- Each session can have own settings
- Or inherit from global defaults
- Settings saved with session (for consistency in logs)

---

## Session Logging

### Logging Architecture

**Automatic Logging**:
- All serial traffic logged automatically
- Both transmitted and received data
- Timestamps for each line or block
- No size limits (until manually deleted)
- Logs stored in `/opt/rpi-engineer/data/serial_logs/`

**Log File Naming**:
```
<device_friendly_name>_<timestamp>_<session_id>.log

Examples:
Router1_2026-02-01T14-30-00_a1b2c3d4.log
Switch-Core_2026-02-01T09-15-23_e5f6g7h8.log
```

**Log File Format**:

Plain text format:
```
===== Serial Console Log =====
Device: /dev/ttyUSB0 (Cisco Router)
Session ID: a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6
Started: 2026-02-01T14:30:00Z
Baud: 9600, Data: 8, Parity: N, Stop: 1, Flow: None
==============================

[14:30:05] > show version
[14:30:06] < Cisco IOS Software, Version 15.2(4)M1
[14:30:06] < Technical Support: http://www.cisco.com/techsupport
[14:30:06] < Copyright (c) 1986-2012 by Cisco Systems, Inc.
...

[14:35:10] > configure terminal
[14:35:11] < Enter configuration commands, one per line.  End with CNTL/Z.
[14:35:11] Router(config)#

==============================
Ended: 2026-02-01T14:45:00Z
Duration: 15 minutes
Bytes TX: 1,234
Bytes RX: 45,678
==============================
```

**Timestamp Options**:
- No timestamps (raw log)
- Relative timestamps (seconds from session start)
- Absolute timestamps (ISO 8601)
- Configurable per session

**Direction Indicators**:
- `>` prefix for transmitted data (user input)
- `<` prefix for received data (device output)
- Or no indicators (raw interleaved log)

### Log Management

**Log Storage**:
- Location: `/opt/rpi-engineer/data/serial_logs/`
- Organization: Flat directory or by date folders
- No automatic deletion (manual only)
- Storage alerts if disk space low

**Log Listing**:
- Table view in web interface
- Columns:
  - Device name
  - Session date/time
  - Duration
  - File size
  - Actions
- Sortable by any column
- Search/filter by device name, date range

**Log Actions**:
- **View**: Open in read-only terminal viewer
- **Download**: Download .log file
- **Delete**: Remove log file (with confirmation)
- **Export**: Include in bulk export
- **Add Notes**: User can add notes to log metadata

**Bulk Operations**:
- Select multiple logs (checkboxes)
- Download selected (as ZIP archive)
- Delete selected (with confirmation)
- Export all logs (ZIP)
- Delete all logs (strong confirmation required)

### Log Viewer

**Viewer Interface**:
- Modal or full-page view
- Read-only terminal display
- Full log content rendered
- Scrollable
- Searchable (find text within log)
- Timestamp display (if logged with timestamps)

**Viewer Features**:
- **Search**: Find text, highlight matches, jump to next/previous
- **Navigate**: Jump to beginning/end, scroll freely
- **Export**: Download this log
- **Copy**: Select and copy text
- **Print**: Print-friendly view
- **Close**: Return to log list

**Large Log Handling**:
- Virtual scrolling for logs >10,000 lines
- Load on demand (don't render entire log at once)
- Progress indicator for loading large logs

---

## File Transfer

### Transfer Capabilities

**Supported Protocols**:
- **Raw**: Send file as-is, no protocol (simple, unreliable)
- **XMODEM**: CRC or checksum (reliable, common)
- **YMODEM**: Batch file transfer (efficient)
- **ZMODEM**: Resume capability (robust)

**Transfer Directions**:
- **Send to Device**: Upload file from browser to network device
- **Receive from Device**: Download file from network device to browser

### Send File

**Workflow**:
1. User clicks "Send File" in console
2. File upload dialog appears
3. User selects file from local system
4. User selects transfer protocol
5. User clicks "Start Transfer"
6. File uploaded to backend (if not already cached)
7. Backend initiates transfer to serial device
8. Progress displayed in console and modal
9. Transfer completes or errors
10. Confirmation or error message shown

**Send File Dialog**:
- **File Selection**: Browse button, drag-and-drop
- **Protocol**: Dropdown (Raw, XMODEM, YMODEM, ZMODEM)
- **Options**:
  - Line delay (for raw transfer, milliseconds)
  - Echo cancel (for devices that echo back)
  - Binary mode (for non-text files)
- **Transfer Button**: "Start Transfer"
- **Cancel Button**: "Cancel"

**Transfer Progress**:
- Progress bar (percentage)
- Bytes transferred / Total size
- Transfer speed (KB/s)
- Estimated time remaining
- Current status message
- Cancel button (abort transfer)

**Raw Transfer Details**:
- Read file line by line
- Send each line to device
- Wait for line delay between lines
- No error checking
- Suitable for configuration files on Cisco devices

**XMODEM Transfer Details**:
- 128-byte or 1024-byte blocks
- CRC or checksum error checking
- Retransmit on error
- Device must be ready to receive (e.g., `copy xmodem: ...`)
- Handle SOH, EOT, ACK, NAK control characters

### Receive File

**Workflow**:
1. User initiates receive on device (e.g., `copy startup-config xmodem:`)
2. User clicks "Receive File" in console
3. Receive dialog appears
4. User selects protocol
5. User enters filename
6. User clicks "Start Receive"
7. Backend listens for incoming data
8. Progress displayed
9. File saved and offered for download
10. Confirmation shown

**Receive File Dialog**:
- **Filename**: Text input for filename
- **Protocol**: Dropdown (XMODEM, YMODEM, ZMODEM)
- **Options**:
  - Binary mode
- **Receive Button**: "Start Receive"
- **Cancel Button**: "Cancel"

**File Download**:
- After successful receive, file available in browser
- Automatic download or save dialog
- File also saved on backend (optional, for backup)

### Transfer Error Handling

**Common Errors**:
- Timeout (device not responding)
- Checksum mismatch (data corruption)
- Protocol error (unexpected response)
- User cancelled
- Device disconnected during transfer

**Error Recovery**:
- Retry automatically (configurable retry count)
- Inform user of error with details
- Option to retry manually
- Log error in session log

---

## Configuration Management

### Port Parameters

**Configurable Settings**:
- **Baud Rate**: 300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400
  - Default: 9600 (most common for network devices)
  - Cisco default: 9600
  - Some devices: 115200
  
- **Data Bits**: 5, 6, 7, 8
  - Default: 8
  - Most devices: 8
  
- **Parity**: None, Even, Odd, Mark, Space
  - Default: None
  - Most devices: None
  
- **Stop Bits**: 1, 1.5, 2
  - Default: 1
  - Most devices: 1
  
- **Flow Control**: None, XON/XOFF (software), RTS/CTS (hardware)
  - Default: None
  - Most devices: None
  - Some devices: Hardware (RTS/CTS)

**Common Presets**:
- **Cisco Default**: 9600 8N1, no flow control
- **Juniper Default**: 9600 8N1, no flow control
- **HP/Aruba**: 115200 8N1, no flow control (newer devices)
- **Custom**: User-defined settings

### Configuration Storage

**Per-Device Configuration**:
- Save configuration for specific device (by serial number or path)
- Auto-apply when device connected
- Override with manual settings if needed

**Default Configuration**:
- Global default for all unknown devices
- User-configurable
- Factory default: 9600 8N1, no flow control

**Configuration File**:
```json
{
  "defaults": {
    "baud_rate": 9600,
    "data_bits": 8,
    "parity": "none",
    "stop_bits": 1,
    "flow_control": "none"
  },
  "devices": [
    {
      "identifier": "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A12345-if00-port0",
      "friendly_name": "Router-Core-01",
      "config": {
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
        "flow_control": "none"
      }
    }
  ]
}
```

### Configuration UI

**Device Configuration Modal**:
- Accessed via "Configure" button on device card
- Shows current device information
- Configuration form:
  - Friendly name (text input)
  - Baud rate (dropdown)
  - Data bits (radio buttons or dropdown)
  - Parity (dropdown)
  - Stop bits (radio buttons or dropdown)
  - Flow control (dropdown)
- Preset selector (dropdown of common configurations)
- **Save as Default** checkbox (apply to this device always)
- **Test Connection** button (opens device briefly to test)
- **Apply** button (save settings)
- **Cancel** button (discard changes)

**Settings Validation**:
- Ensure valid combinations
- Warn if unusual settings (e.g., 7 data bits with no parity)
- Prevent invalid combinations (e.g., 1.5 stop bits with 5 data bits)

---

## Multi-Session Support

### Session Isolation

**Independent Sessions**:
- Each session has own:
  - Serial port connection
  - WebSocket connection
  - Terminal buffer
  - Logging file
  - Configuration settings
  
- Sessions do not interfere with each other
- Data from one session never sent to another
- Logs completely separate

### Resource Management

**Connection Limits**:
- Maximum simultaneous sessions: 8 (configurable)
- Prevent exceeding limit (error message)
- Warn when approaching limit

**Memory Management**:
- Each session buffer: 1MB default
- Total buffer memory: 8MB for 8 sessions
- Release memory when session closed
- Periodically trim buffers (keep last X lines)

**File Descriptor Management**:
- Each session: 1 serial port FD, 1 log file FD, 1 WebSocket FD
- Monitor FD usage
- Warn if approaching system limits

### Session Switching

**UI Design**:
- Active Sessions sidebar or tabs
- Click to switch between sessions
- Active session highlighted
- Keyboard shortcuts (Ctrl+1, Ctrl+2, etc.)
- Show session name (device friendly name)

**Switching Behavior**:
- WebSocket remains connected for all sessions
- Only active session displayed in terminal
- Background sessions continue receiving data (buffered)
- Switching is instant (no reconnection)

### Session Notifications

**Background Session Activity**:
- If data received on background session, show badge/indicator
- User can click to switch and view data
- Optional: Toast notification for significant events (device reboot, disconnection)

---

## Error Handling

### Connection Errors

**Cannot Open Device**:
- **Cause**: Permission denied, device busy, hardware fault
- **Handling**:
  - Display error message with details
  - Suggest solutions (check permissions, disconnect other session)
  - Log error for troubleshooting
  - Allow retry

**Device Disconnected During Session**:
- **Cause**: USB cable unplugged, device powered off, hardware failure
- **Handling**:
  - Detect disconnection (read/write error)
  - Close session gracefully
  - Finalize log file
  - Notify user via toast and update session status
  - Offer to reconnect when device available again

**WebSocket Disconnection**:
- **Cause**: Network issue, browser closed, backend restart
- **Handling**:
  - Attempt automatic reconnection
  - Show "Reconnecting..." message in terminal
  - Buffer data on backend during reconnection
  - Resume session when reconnected
  - If cannot reconnect after N attempts, close session

### Data Transmission Errors

**Write Failure**:
- **Cause**: Device not ready, buffer full, disconnection
- **Handling**:
  - Retry write (with timeout)
  - Log error
  - Notify user if persistent
  - Consider session broken if repeated failures

**Read Timeout**:
- **Cause**: Device not responding, slow device
- **Handling**:
  - Continue waiting (serial can be slow)
  - No error unless timeout very long (60+ seconds)
  - User can manually close if needed

**Malformed Data**:
- **Cause**: Noise on serial line, hardware issue
- **Handling**:
  - Log warning
  - Display data as received (may be garbled)
  - User can see issue and troubleshoot
  - Consider checksum/parity errors if configured

### File Transfer Errors

**Transfer Timeout**:
- **Cause**: Device not responding during protocol handshake
- **Handling**:
  - Abort transfer after timeout (30 seconds default)
  - Notify user
  - Offer to retry

**Checksum Error**:
- **Cause**: Data corruption during transfer
- **Handling**:
  - Retry block (XMODEM/YMODEM/ZMODEM)
  - If retry limit exceeded, abort transfer
  - Notify user of error

**Transfer Cancelled**:
- **Cause**: User cancelled transfer
- **Handling**:
  - Send cancel signal to device (protocol-specific)
  - Clean up partial transfer
  - Notify user of cancellation

### Recovery Procedures

**Automatic Recovery**:
- Reconnect on temporary WebSocket failure
- Retry on temporary serial port errors
- Retry file transfer blocks on checksum error

**Manual Recovery**:
- User closes and reopens session
- User disconnects and reconnects device
- User adjusts configuration and retries

**Logging**:
- All errors logged to system log
- Critical errors logged to session log
- User-visible errors shown in UI

---

## Performance Considerations

### Latency Requirements

**Target Latency**: <50ms from user keystroke to character displayed
- User types character in browser
- Character sent via WebSocket to backend (<10ms)
- Backend writes to serial port (<5ms)
- Device echoes character (<10ms, depends on device)
- Backend receives echo and sends to browser (<10ms)
- Browser displays character (<5ms)
- **Total**: ~40ms typical

**Optimization Techniques**:
- Direct WebSocket connection (no polling)
- Minimal processing in data path
- Efficient terminal rendering
- Local echo option (instant feedback, user must disable if device echoes)

### Throughput

**Serial Port Throughput**:
- Depends on baud rate
- 9600 baud ≈ 960 bytes/sec theoretical (≈800 bytes/sec practical)
- 115200 baud ≈ 11,520 bytes/sec theoretical (≈10,000 bytes/sec practical)
- Must not overwhelm WebSocket or browser

**WebSocket Throughput**:
- Much higher than serial (1+ MB/s)
- Not a bottleneck for serial console use

**Terminal Rendering**:
- Should handle 10,000+ characters/second without lag
- Use efficient rendering (virtual DOM, canvas, or optimized DOM updates)
- Batch updates if data arrives rapidly

### Resource Usage

**Memory**:
- Per-session buffer: 1MB (configurable)
- Terminal scrollback: 10,000 lines default (≈1MB per session)
- Log file buffering: 4KB - 64KB
- Total per session: ~2-3MB
- 8 sessions: ~16-24MB total (acceptable)

**CPU**:
- Serial I/O: Minimal (<1% per session)
- WebSocket I/O: Minimal (<1% per session)
- Terminal rendering: 5-10% per active session (browser-side)
- Logging: 1-2% per session

**Disk I/O**:
- Logs written continuously (buffered)
- Sync to disk periodically (every 10 seconds or on buffer full)
- Minimize write amplification

### Scalability

**Session Limits**:
- Default maximum: 8 simultaneous sessions
- Can increase if hardware permits (more RAM, CPU cores)
- Raspberry Pi 4 4GB: Comfortable with 8 sessions
- Raspberry Pi 3B+ 1GB: Limit to 4 sessions

**Long-Running Sessions**:
- Sessions may run for hours or days
- Ensure no memory leaks
- Log rotation if single log grows very large (>1GB)
- Monitor resource usage over time

---

## Security Considerations

### Access Control

**Physical Security**:
- Serial console provides full device access
- Assumes user is authorized (no authentication at app level)
- Physical access to Raspberry Pi = serial access to devices

**Session Security**:
- WebSocket not encrypted (HTTP only per requirements)
- Assume WiFi hotspot is private network
- All traffic visible on local network
- Sensitive commands visible in logs

### Data Protection

**Log Security**:
- Logs may contain passwords, keys, sensitive config
- Logs stored on device (not transmitted elsewhere)
- User responsible for protecting device
- Consider encrypting storage (future enhancement)

**Session Isolation**:
- One user at a time per requirements (no multi-user)
- Sessions isolated from each other
- No cross-session data leakage

### Best Practices

**Recommendations**:
- Change device passwords after console session
- Delete logs containing sensitive data when done
- Use secure WiFi password for hotspot
- Keep device physically secure
- Regular backups of logs (if needed for documentation)

---

## Integration with Web Interface

### API Endpoints

**Device Management**:
- `GET /api/v1/serial/devices` - List all detected devices
- `GET /api/v1/serial/devices/{id}` - Get device details
- `PUT /api/v1/serial/devices/{id}` - Update device configuration
- `POST /api/v1/serial/devices/{id}/test` - Test device connection

**Session Management**:
- `GET /api/v1/serial/sessions` - List active sessions
- `POST /api/v1/serial/sessions` - Create new session (open console)
- `GET /api/v1/serial/sessions/{id}` - Get session details
- `PUT /api/v1/serial/sessions/{id}` - Update session (pause logging, etc.)
- `DELETE /api/v1/serial/sessions/{id}` - Close session

**Log Management**:
- `GET /api/v1/serial/logs` - List all session logs
- `GET /api/v1/serial/logs/{id}` - Get log details
- `GET /api/v1/serial/logs/{id}/content` - Download log content
- `DELETE /api/v1/serial/logs/{id}` - Delete log
- `POST /api/v1/serial/logs/export` - Export selected logs

**WebSocket**:
- `WS /ws/serial/{session_id}` - WebSocket for real-time console I/O

### Web UI Integration

**Simple Mode**:
- "Serial Console" button on landing page
- Click opens device selector modal
- Select device, opens console in full-screen modal
- Simplified interface (fewer options visible)

**Advanced Mode**:
- "Serial Console" in sidebar navigation
- Dedicated page with device list
- Full feature set visible
- Multi-session support clear
- Logs and configuration accessible

**Console Modal/Page**:
- Terminal area (full-screen or large modal)
- Control buttons (Send File, Receive File, Settings, Close)
- Status bar (device, baud rate, duration, Rx/Tx bytes)
- Session tabs (if multiple sessions open)

---

## Testing and Validation

### Functional Testing

**Device Detection**:
- Test with multiple USB serial adapters
- Test hotplug (connect/disconnect during operation)
- Test with different chipsets (FTDI, Prolific, CH340)
- Verify friendly names and metadata

**Session Operations**:
- Open and close sessions
- Multiple simultaneous sessions
- Session switching
- Long-running sessions (hours)
- Session survival across WebSocket reconnection

**Terminal Emulation**:
- Test with various devices (Cisco, Juniper, HP, Linux)
- Verify ANSI color rendering
- Test special characters and sequences
- Scrollback and search functionality
- Copy/paste operations

**File Transfer**:
- Send files with different protocols
- Receive files with different protocols
- Test with various file sizes (small, medium, large)
- Test transfer interruption and resume (ZMODEM)
- Verify data integrity (checksum)

**Logging**:
- Verify all data logged correctly
- Test timestamp options
- Verify log file format
- Test log viewer with large logs
- Export and download logs

### Performance Testing

**Latency**:
- Measure keystroke to echo latency
- Should be <50ms on average
- Test with different baud rates
- Test with multiple active sessions

**Throughput**:
- Test high-speed data transfer (115200 baud)
- Verify no data loss
- Test with continuous streaming data
- Measure CPU and memory usage

**Scalability**:
- Test with maximum sessions (8)
- Measure resource usage (CPU, RAM, disk I/O)
- Test on Raspberry Pi 3B+ and 4
- Long-term stability test (24+ hours)

### Error Testing

**Connection Errors**:
- Disconnect device during session
- Remove USB cable during file transfer
- Test permission errors
- Test device busy (already open)

**Data Errors**:
- Introduce noise on serial line (if possible)
- Test parity errors
- Test frame errors
- Verify error reporting

**Recovery**:
- Test automatic reconnection
- Test manual recovery procedures
- Verify data consistency after errors

---

## Documentation Requirements

### User Documentation

**Getting Started**:
- How to connect USB-to-serial cable
- Opening first console session
- Basic terminal usage
- Closing session

**Feature Guides**:
- Configuring serial port parameters
- Using file transfer
- Managing session logs
- Working with multiple sessions

**Device-Specific Guides**:
- Connecting to Cisco devices
- Connecting to Juniper devices
- Connecting to HP/Aruba devices
- Connecting to Linux systems

**Troubleshooting**:
- Device not detected
- Cannot open device (permission errors)
- Data garbled (wrong baud rate, etc.)
- File transfer failures
- Session disconnections

### Technical Documentation

**Architecture**:
- Component overview
- Data flow diagrams
- WebSocket protocol specification
- File transfer protocol details

**API Documentation**:
- REST endpoints
- WebSocket messages
- Error codes
- Examples

**Developer Guide**:
- Adding support for new protocols
- Customizing terminal emulator
- Extending file transfer features

---

## Future Enhancements

### Potential Features

**Session Recording**:
- Record session as scriptable replay
- Timing information for accurate replay
- Useful for demonstrations and training

**Automation**:
- Send predefined command sequences
- Expect/Send scripting (like Expect tool)
- Scheduled automation tasks

**Multi-User Support**:
- Allow multiple users to view same console (read-only)
- Chat/annotation features
- Session sharing for collaboration

**Advanced Terminal Features**:
- Multiple panes (split terminal)
- Command history persistence
- Autocomplete (device-specific)
- Syntax highlighting for configs

**Cloud Integration**:
- Upload logs to cloud storage
- Remote access to serial console via cloud relay
- Centralized log management

**Enhanced Logging**:
- Structured logging (parse commands and responses)
- Searchable command history
- Configuration diff tracking

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial serial console specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- WEB-INTERFACE-SPECIFICATION.md
- API-REFERENCE.md
- DOCUMENTATION-GUIDELINES.md
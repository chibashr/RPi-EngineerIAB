# Web Interface Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Interface Overview](#interface-overview)
2. [Design Principles](#design-principles)
3. [User Modes](#user-modes)
4. [Page Specifications](#page-specifications)
5. [Component Library](#component-library)
6. [Navigation Structure](#navigation-structure)
7. [Responsive Design](#responsive-design)
8. [Real-Time Updates](#real-time-updates)
9. [Accessibility](#accessibility)
10. [Performance Requirements](#performance-requirements)

---

## Interface Overview

### Purpose

The web interface serves as the primary user interface for RPi Engineer-in-a-Box, providing both simple and advanced functionality through a dual-mode design. It must work seamlessly on mobile devices (primary use case for field technicians) and desktop computers (for engineers).

### Core Requirements

**Functional Requirements**:
- Dual mode operation (Simple/Advanced)
- Mobile-first responsive design
- No authentication required
- Dark mode support
- Real-time status updates
- Embedded documentation access
- Works without internet connectivity

**Non-Functional Requirements**:
- Page load time: <3 seconds on RPi 4
- API response rendering: <100ms
- Mobile touch-friendly controls (minimum 44x44px tap targets)
- Works on Chrome, Firefox, Safari (iOS/Android/Desktop)
- Graceful degradation on older browsers
- Minimal JavaScript dependencies
- Progressive enhancement approach

### User Access Pattern

```
User Connects to WiFi Hotspot (RPi-Engineer-XXXX)
              ↓
    Opens Browser to http://192.168.50.1
              ↓
         Landing Page Loads
              ↓
    ┌─────────────────────┐
    │   Simple Mode       │ ← Default on every boot
    │   (Essential Tasks) │
    └─────────────────────┘
              ↓
    [Switch to Advanced] button
              ↓
    ┌─────────────────────┐
    │   Advanced Mode     │ ← Persists until switched back
    │   (Full Control)    │
    └─────────────────────┘
```

---

## Design Principles

### 1. Simplicity First

**Principle**: Make common tasks immediately accessible with minimal clicks

**Implementation**:
- Simple mode shows only essential actions
- No deep menu hierarchies
- Large, clear action buttons
- Obvious success/failure feedback

### 2. Progressive Disclosure

**Principle**: Show advanced features only when needed

**Implementation**:
- Simple mode hides complexity
- Advanced mode reveals full capabilities
- Expandable sections for detailed information
- Help text available but not intrusive

### 3. Mobile-First

**Principle**: Design for mobile devices, enhance for desktop

**Implementation**:
- Touch-friendly controls
- Vertical scrolling preferred
- Single-column layouts on mobile
- Thumb-friendly button placement

### 4. Immediate Feedback

**Principle**: User actions should have instant visual feedback

**Implementation**:
- Loading spinners for operations >500ms
- Success/error notifications
- Real-time status updates
- Progress indicators for long operations

### 5. Offline-Capable

**Principle**: All functionality works without internet

**Implementation**:
- All assets served locally
- No external CDN dependencies
- Embedded documentation
- Local data storage

### 6. Consistent Patterns

**Principle**: Similar actions should look and behave similarly

**Implementation**:
- Consistent button styles
- Standard icon usage
- Predictable navigation
- Uniform color coding

---

## User Modes

### Simple Mode

**Purpose**: Provide immediate access to most common tasks for field technicians and end users

**Entry Point**: Default mode on every boot/page load

**Target Users**: 
- Field technicians performing basic tasks
- End users capturing packets
- Anyone needing quick access

**Key Features**:
- Large action buttons for common tasks
- Status at a glance
- Connection information prominently displayed
- Minimal configuration options
- Clear visual hierarchy

**Layout Philosophy**:
- Vertical card-based layout
- One primary action per card
- Status indicators visible
- No scrolling required for primary actions (on mobile)

#### Simple Mode Page Structure

**Top Section - Header**:
- Project logo/title
- Mode indicator badge
- Mode switch button

**Status Overview Card**:
- Visual health indicator (green checkmark, yellow warning, or red error)
- Key metrics displayed with icons:
  - CPU usage percentage
  - Memory usage percentage  
  - System temperature
  - Storage available
- Network connectivity status with colored indicator
- Click to expand for detailed breakdown

**Connection Information Card**:
- WiFi credentials section:
  - SSID displayed prominently  
  - Password with show/hide toggle
  - Copy to clipboard button
- Remote access section:
  - Service name (AnyDesk/TeamViewer/VNC)
  - Connection ID prominently displayed
  - Copy ID button
  - Connection status (Connected/Disconnected)
- Collapsible to save screen space

**Quick Action Buttons** (Primary Actions):
- Capture Packets button:
  - Large button with packet icon
  - Launches simple capture interface
  - Disabled if no interfaces available
- Serial Console button:
  - Large button with terminal icon
  - Shows detected devices count
  - Launches device selector
- Documentation button:
  - Large button with book icon
  - Opens embedded documentation

**Mode Switch Section**:
- "Need more control?" prompt text
- "Switch to Advanced Mode" button
- Brief explanation of what advanced mode offers

### Advanced Mode

**Purpose**: Provide full control and visibility for network engineers and administrators

**Entry Point**: Via "Switch to Advanced Mode" button in Simple Mode

**Persistence**: Enabled state persists until user switches back (survives page refresh, but resets to Simple on reboot)

**Target Users**:
- Network engineers configuring the system
- Administrators managing multiple captures
- Users needing detailed configuration

**Key Features**:
- Complete system dashboard
- Full network configuration
- Service management
- Advanced capture settings
- System settings and updates
- Module management

**Layout Philosophy**:
- Dashboard-style with sidebar navigation
- Multi-panel information display
- Dense information for power users
- Desktop-optimized with mobile responsive fallback

#### Advanced Mode Structure

**Sidebar Navigation** (Collapsible):
- Dashboard (home icon)
- Network Management (network icon)
- Serial Console (terminal icon)
- Packet Capture (activity icon)
- System Management (settings icon)
- Updates & Maintenance (download icon)
- Modules (puzzle piece icon)
- Logs & Monitoring (file-text icon)
- Documentation (book icon)
- Divider line
- Switch to Simple Mode (toggle icon)
- Collapse sidebar button

**Main Content Area**:
- Page title and breadcrumbs
- Action toolbar (page-specific actions)
- Content panels and sections
- Footer with status information

---

## Page Specifications

### Simple Mode Landing Page

**URL**: `/` or `/index.html`

**Purpose**: Provide immediate access to essential tasks and status

**Visual Layout**:
- Clean, uncluttered design
- Generous white space (or dark space in dark mode)
- Card-based sections with clear separation
- Vertical scrolling on mobile, potential two-column on desktop

**Header Section**:
- Logo: "RPi Engineer-in-a-Box" with icon
- Mode indicator: Small badge showing "Simple Mode"
- Mode switch: Button in top-right

**System Status Card**:
- Overall health indicator:
  - Large icon: Checkmark (green), Warning (yellow), Error (red)
  - Text status: "All Systems Operational" or specific issue
- Quick metrics grid (2x2 on mobile, 4x1 on desktop):
  - CPU: Icon + percentage + small bar
  - Memory: Icon + percentage + small bar
  - Temperature: Icon + value in °C + status color
  - Storage: Icon + available space + small bar
- Network status:
  - "WAN Connected via [interface]" (green) or "No WAN Connection" (red)
  - Click to see more details
- Expandable section:
  - Shows all interfaces briefly
  - Service status summary
  - Recent alerts (if any)

**Connection Info Card**:
- Title: "Connection Information"
- WiFi section:
  - Label: "Connect to WiFi"
  - SSID: Large text, easily readable
  - Password: Hidden by default with show/hide eye icon
  - Copy WiFi Details button (copies both SSID and password)
- Remote Access section:
  - Label: "Remote Access"
  - Service: "AnyDesk" or "TeamViewer" or "VNC"
  - ID: Large text, easily readable  
  - Status indicator: Dot (green=connected, gray=disconnected)
  - Copy ID button
- Privacy toggle: Hide/show this card entirely

**Quick Actions**:
- Each action as large card with:
  - Icon (large, colorful)
  - Action name (large text)
  - Brief description (small text)
  - Disabled state clearly indicated
  
- Capture Packets:
  - Icon: Radio waves or network activity
  - Opens capture quick-start dialog
  - Shows number of available interfaces
  
- Serial Console:
  - Icon: Terminal window
  - Opens device list
  - Shows count of detected devices
  
- View Logs:
  - Icon: Document or list
  - Opens recent logs viewer
  - Shows unread alert count badge
  
- Documentation:
  - Icon: Book or help
  - Opens embedded docs
  - Links to quick guides

**Mode Switch Section**:
- Centered text: "Need advanced features?"
- Button: "Switch to Advanced Mode"
- On click: Show confirmation explaining mode switch

**Footer**:
- Version number (small text)
- Last update check timestamp
- Link to advanced mode (duplicate of button)

### Advanced Mode Dashboard

**URL**: `/dashboard.html` or `/advanced/`

**Purpose**: Comprehensive system overview for engineers

**Layout**:
- Left sidebar: Navigation menu
- Main content area: Dashboard widgets
- Top bar: Page title, breadcrumbs, user controls

**Sidebar** (200px wide, collapsible to icons-only):
- Logo at top
- Navigation items:
  - Each with icon + label
  - Active page highlighted
  - Hover effect
  - Expandable sections (if sub-pages exist)
- Mode switch at bottom
- Collapse toggle button

**Dashboard Content**:

Top Row - System Metrics (Cards):
- CPU Usage:
  - Large percentage number
  - Line chart (last 60 seconds)
  - Color changes based on threshold
  - Click for detailed view
  
- Memory Usage:
  - Used / Total display
  - Percentage
  - Progress bar
  - Breakdown (click for details)
  
- Temperature:
  - Current temperature
  - Trend indicator (up/down arrow)
  - Warning if threshold exceeded
  - History graph on click
  
- Storage:
  - Root partition usage
  - Data partition usage
  - Progress bars for each
  - Cleanup button if low

Network Status Panel:
- Table view:
  - Columns: Interface, Status, IP Address, Type, Speed
  - Color-coded status dots
  - Quick action buttons per row
- Summary stats:
  - Active interfaces count
  - Current WAN interface
  - Total traffic (Rx/Tx today)
- Quick actions toolbar:
  - Refresh
  - Configure
  - Add interface/VLAN

Service Status Panel:
- List or table view:
  - Service name
  - Status with color indicator
  - Uptime
  - Action buttons (Stop/Start/Restart)
- Filter options:
  - All services
  - Running only
  - Stopped/Failed only
  - Core services only
- Quick actions:
  - Restart all
  - View all logs

Active Captures Panel:
- If captures running:
  - List with: Name, Interface, Duration, Size, Packet count
  - Real-time updates
  - Stop/View/Download buttons
- If no captures:
  - Empty state with "Start Capture" button
- Recent captures:
  - Last 3 completed captures
  - Download/Delete buttons

Recent Alerts Panel:
- Last 5 system alerts/events
- Each showing:
  - Timestamp
  - Severity icon/color
  - Brief message
  - Click for full details
- "View All Logs" link

Quick Actions Toolbar:
- Prominent buttons for common tasks:
  - Start Packet Capture
  - Open Serial Console
  - Check for Updates
  - View Full Logs

### Network Management Page

**URL**: `/advanced/network.html`

**Purpose**: Complete network configuration and management

**Tab Structure**:
- Interfaces
- VLANs  
- Routing
- Profiles
- Hotspot Settings

**Interfaces Tab**:

Interface Cards (one per interface):
- Header section:
  - Interface name (friendly)
  - Kernel name in parenthesis (eth0, wlan0, etc.)
  - Enable/Disable toggle
  - Status indicator dot
  
- Information section:
  - Connection status (Up/Down, Connected/Disconnected)
  - Configuration mode (DHCP/Static)
  - IP address / subnet mask
  - Gateway (if configured)
  - DNS servers
  - MAC address
  - Link speed (if applicable)
  - Current traffic stats (Rx/Tx)
  
- Action buttons:
  - Configure (opens configuration modal)
  - View Details (expands full information)
  - Test Connectivity (runs ping test)

Configuration Modal (for editing interface):
- Interface name field (friendly name)
- Enable/Disable toggle
- Configuration mode selector:
  - DHCP (automatic)
  - Static (manual configuration)
- If Static selected:
  - IP Address field with validation
  - Subnet mask field (or CIDR)
  - Gateway field (optional)
  - DNS servers field (comma-separated, optional)
- Advanced settings (expandable):
  - MTU (Maximum Transmission Unit)
  - Metric (routing priority number)
  - MAC address override
  - Custom DHCP client options
- Save as Profile checkbox
- Action buttons:
  - Apply Changes (with confirmation)
  - Test Configuration (validates before applying)
  - Cancel

**VLANs Tab**:

VLAN List (if any configured):
- Table format:
  - VLAN ID
  - Parent Interface
  - IP Configuration
  - Status
  - Actions (Edit, Delete)
- Empty state if no VLANs

Add VLAN button (prominent)

Add/Edit VLAN Modal:
- Parent interface dropdown
- VLAN ID field (1-4094 validation)
- Tagged/Untagged toggle
- IP configuration section (same as interface)
- Actions: Create/Update, Cancel

**Routing Tab**:

Current Routes Section:
- Active routing table display:
  - Destination (network or default)
  - Gateway
  - Interface  
  - Metric
  - Status (active/inactive)
- System routes (not editable, grayed out)
- Custom routes (editable/deletable)

Default Gateway Section:
- Current default gateway display
- Interface used
- Automatic/Manual toggle
- If manual: Gateway address field

Add Route Section:
- Destination network field
- Subnet mask or CIDR
- Gateway field
- Interface selector
- Metric field
- Add Route button

Interface Priority Section:
- Visual list of interfaces
- Drag handles for reordering
- Priority numbers displayed
- Automatic failover based on this order
- Test Failover button

**Profiles Tab**:

Saved Profiles List:
- Card view of saved profiles:
  - Profile name
  - Description  
  - Date saved
  - Interfaces included
  - Actions: Load, Edit, Delete
- Empty state if no profiles

Save Current Configuration Section:
- Profile name field
- Description field (optional)
- Select interfaces to include (checkboxes)
- Save Profile button

Load Profile:
- Select profile from list
- Preview changes modal:
  - Shows what will change
  - Interfaces affected
  - Current vs. new configuration
- Confirmation required
- Apply/Cancel buttons

**Hotspot Tab**:

WiFi Access Point Settings:
- Enable/Disable toggle (always on per requirements)
- SSID field (editable)
- Password field (show/hide toggle)
- Security mode selector (WPA2/WPA3)
- Channel selector (1-11, or Auto)
- Bandwidth selector (20MHz/40MHz)
- Country code (for regulatory compliance)

DHCP Server Settings:
- IP address range:
  - Start address
  - End address
  - Subnet validation
- Lease time (hours)
- DNS server addresses (comma-separated)
- Gateway address

Connected Clients:
- Real-time list of connected devices:
  - MAC address
  - Assigned IP
  - Hostname (if available)
  - Connection time
  - Signal strength
  - Action: Disconnect (kick)
- Auto-refresh toggle

Apply Changes button (with confirmation)

**Factory Reset Section** (bottom of page):
- Prominent warning styling
- Description of what will be reset
- Checkbox: "Preserve hotspot configuration" (checked by default)
- Factory Reset button (requires confirmation)
- Multiple confirmation steps for safety

### Serial Console Page

**URL**: `/advanced/serial.html`

**Purpose**: Manage serial console connections to network devices

**Page Layout**:
- Detected Devices section
- Active Sessions section  
- Session Logs section

**Detected Devices Section**:

Device Cards (one per detected serial adapter):
- Device identification:
  - Device path (/dev/ttyUSB0, /dev/ttyACM0, etc.)
  - Chipset information (FTDI, Prolific, etc.)
  - Connection status indicator
- Quick info:
  - Currently configured baud rate
  - Session status (In use / Available)
- Action buttons:
  - Open Console (primary action, large button)
  - Configure Settings (opens settings modal)

No Devices Detected state:
- Helpful message
- Icon illustration
- Instructions for connecting USB serial adapters
- Auto-refresh note

Device Settings Modal:
- Serial port parameters:
  - Baud rate dropdown (9600, 19200, 38400, 57600, 115200)
  - Data bits radio buttons (7, 8)
  - Parity dropdown (None, Even, Odd, Mark, Space)
  - Stop bits radio buttons (1, 1.5, 2)
  - Flow control dropdown (None, XON/XOFF, RTS/CTS)
- Save as default checkbox (persists settings for this device)
- Test connection button
- Apply/Cancel buttons

**Serial Console Modal** (opens when "Open Console" clicked):

Full-screen or large modal layout:

Header bar:
- Device identifier (path + friendly name if set)
- Connection settings badge (e.g., "115200 8N1")
- Connection status indicator (Connected/Disconnected)
- Settings dropdown menu
- Close button

Terminal area:
- Black background (or theme appropriate)
- Monospace font
- Full terminal emulator behavior:
  - ANSI color support
  - Scrollback buffer (configurable size)
  - Text selection and copy
  - Paste support
  - Proper line wrapping

Controls bar (above terminal):
- Connection toggle (Connect/Disconnect)
- Clear screen button
- Send file button
- Receive file button  
- Settings menu:
  - Local echo toggle
  - Line wrap toggle
  - Timestamps toggle
  - Font size selector
  - Color scheme selector

Input area (below terminal):
- Command input field
- Send button
- Or press Enter to send
- Input history (up/down arrows)

Footer bar:
- Session duration timer
- Bytes received counter
- Bytes transmitted counter
- Logging status indicator (Recording/Paused)
- Logging controls (Pause/Resume, Save Log)

Send File Dialog:
- File selection
- Transfer protocol (Raw, XMODEM, YMODEM, ZMODEM)
- Progress bar during transfer
- Cancel button

Receive File Dialog:
- Filename
- Transfer protocol
- Progress bar
- Save location options

**Active Sessions Section**:

Sessions list:
- Table or card view:
  - Device name/path
  - Start time
  - Duration (updating)
  - Data transmitted/received
  - Actions:
    - Switch to session (if multiple open)
    - Close session
- Close All Sessions button (if multiple)
- Empty state if no active sessions

**Session Logs Section**:

Log files list:
- Table view:
  - Device name
  - Session date/time
  - Duration
  - File size
  - Actions:
    - View log (opens viewer modal)
    - Download log
    - Delete log
- Filters:
  - Date range
  - Device
  - Search within logs
- Bulk actions:
  - Select multiple
  - Download selected (as ZIP)
  - Delete selected
- Export All Logs button
- Delete All Logs button (with strong confirmation)

Log Viewer Modal:
- Read-only terminal display
- Full log contents
- Navigation:
  - Scroll or page through
  - Jump to beginning/end
  - Search function (highlights matches)
- Timestamp display (if logged with timestamps)
- Download button
- Close button

### Packet Capture Page

**URL**: `/advanced/capture.html`

**Purpose**: Configure, run, and analyze packet captures

**Page Structure**:
- New Capture button (prominent, top-right)
- Active Captures section
- Completed Captures section (with filters)

**New Capture Button**:
- Opens capture configuration modal
- Large, primary-styled button
- Shows keyboard shortcut (e.g., Ctrl+N)

**Active Captures Section**:

If no active captures:
- Empty state with illustration
- "Start New Capture" button
- Recent captures suggestion

If captures active:
- Real-time updating cards (one per active capture):
  - Capture name (or auto-generated ID)
  - Interface being captured
  - Status (Running/Paused)
  - Statistics (updating every second):
    - Duration
    - Packet count
    - File size
    - Current capture rate (packets/sec, Mbps)
  - Progress bar (if time or size limited)
  - Action buttons:
    - View Live (opens live viewer)
    - Pause/Resume
    - Stop
    - Download

**New Capture Modal**:

Basic Configuration:
- Capture name field (optional, auto-generated if empty)
- Interface selector (dropdown of all available interfaces)
- Duration/Size limits section:
  - Unlimited (default)
  - Time limit: Hours/Minutes/Seconds fields
  - Packet count limit: Number field
  - File size limit: Size in MB field

Filtering section (expandable):
- Filter mode selector:
  - No filter (capture all)
  - BPF filter (text entry)
  - Simple filter (GUI builder)
  
- If BPF filter selected:
  - Text area for filter expression
  - Syntax highlighting (if possible)
  - Validate button (checks filter syntax)
  - Examples link (opens help)
  
- If Simple filter selected:
  - Protocol dropdown (TCP, UDP, ICMP, ARP, etc.)
  - Direction selector (Any, Inbound, Outbound)
  - Source IP field (with subnet support)
  - Destination IP field
  - Source port field
  - Destination port field
  - Add condition button (for multiple filters)
  - Preview BPF button (shows generated filter)

Advanced Options (expandable):
- Promiscuous mode toggle (enabled by default)
- Snapshot length (bytes per packet, 0 = full packet)
- Buffer size (MB for capture buffer)
- Ring buffer toggle (circular capture, keeps last X MB)
- File rotation:
  - Enable toggle
  - Size per file
  - Number of files to keep

Action buttons:
- Start Capture (begins capture, stays on page)
- Start & View Live (begins and opens live viewer)
- Cancel

**Live Capture Viewer** (Modal or full page):

Layout with three panes:

Top pane - Packet list (table):
- Columns:
  - Number (packet number in capture)
  - Time (timestamp, relative or absolute)
  - Source (IP or MAC)
  - Destination  
  - Protocol
  - Length
  - Info (protocol-specific summary)
- Sortable columns
- Selectable rows
- Auto-scroll toggle (follow live packets)
- Freeze display toggle (stop updating while viewing)

Middle pane - Packet details (tree view):
- Selected packet expanded into protocol layers:
  - Frame (link layer info)
  - Ethernet/WiFi (Layer 2)
  - IP (Layer 3)
  - TCP/UDP/ICMP (Layer 4)
  - Application data (Layer 7)
- Each layer expandable to show fields
- Values shown with descriptions

Bottom pane - Hex dump:
- Raw packet data in hex and ASCII
- Synchronized highlighting with packet details
- Offset column
- Bytes grouped for readability

Controls:
- Filter bar (display filter, doesn't affect capture):
  - Filter expression field
  - Apply button
  - Clear button
  - Quick filter buttons (TCP, UDP, ICMP, HTTP, DNS)
- View options:
  - Time format (relative, absolute, delta)
  - Name resolution (on/off for IPs, ports)
  - Colorize packets (protocol-based coloring)
- Capture controls:
  - Pause/Resume capture
  - Stop capture
  - Save capture
  - Close viewer

Statistics panel (sidebar or modal):
- Protocol distribution (pie chart)
- Conversations (list of IP pairs with packet/byte counts)
- Endpoints (top talkers)
- Bandwidth over time (line chart)
- Protocol hierarchy (tree)
- Export statistics button

**Completed Captures Section**:

Filter bar:
- Search by name (text field)
- Filter by interface (dropdown)
- Date range picker (from/to dates)
- Apply filters button
- Clear filters button

Captures list:
- Table or card view:
  - Capture name
  - Interface
  - Date/time captured
  - Duration
  - Packet count
  - File size
  - Actions:
    - Analyze (opens analyzer modal)
    - Download
    - Delete
- Sortable by any column
- Pagination (if many captures)

Bulk actions:
- Select multiple checkboxes
- Download selected (as ZIP)
- Delete selected (with confirmation)

Capture Analyzer Modal:

Similar to live viewer but for completed captures:
- Packet list (full capture, not live)
- Packet details and hex dump
- Statistics tabs:
  - Summary
  - Conversations  
  - Endpoints
  - Protocol hierarchy
  - Protocol-specific tabs (HTTP, DNS, etc.) if applicable
- Advanced analysis options:
  - Follow TCP stream
  - Expert info (warnings, errors, notes)
  - Time sequence graphs
- Export options:
  - Export as CSV
  - Export statistics
  - Download PCAP
  - Download filtered view

### System Management Page

**URL**: `/advanced/system.html`

**Purpose**: Manage services, power, and system settings

**Tab Structure**:
- Services
- Power Management
- Settings
- System Information

**Services Tab**:

Services list:
- Table format:
  - Service name
  - Description (on hover or expandable)
  - Status indicator:
    - Running (green dot)
    - Stopped (gray dot)  
    - Failed (red dot)
    - Starting/Stopping (animated)
  - Uptime (if running)
  - Auto-start toggle (enabled/disabled at boot)
  - Actions:
    - Start (if stopped)
    - Stop (if running)
    - Restart
    - View Logs
    - Enable/Disable auto-start

Filter options:
- All services
- Running only
- Stopped only
- Failed only
- Core services only
- Module services only

Bulk actions:
- Restart all button (with confirmation)
- Start all stopped
- Stop all running (with confirmation)

Service details modal (when clicking service name):
- Full service name and description
- Current status and uptime
- Process ID (if running)
- Memory usage
- CPU usage
- Dependencies (services it depends on / depends on it)
- Recent log entries (last 50 lines)
- Full logs link
- Control buttons (Start/Stop/Restart/Enable/Disable)

**Power Management Tab**:

Power options (warning-styled section):
- Shutdown:
  - Large red button
  - Confirmation dialog
  - Countdown timer (10 seconds, cancellable)
  - "Shutting down..." status message
  
- Restart:
  - Orange button
  - Confirmation dialog
  - Countdown timer (10 seconds, cancellable)
  - "Restarting..." status message

Low power mode:
- Toggle switch
- When enabled:
  - Reduces CPU frequency
  - Dims display (if present)
  - Disables non-essential services
  - Status: "Low Power Mode Active" banner
- When disabled:
  - Returns to normal operation

Power status information:
- Power source:
  - USB power detected
  - Battery power (if battery module installed)
- Battery information (if applicable):
  - Battery percentage
  - Charging status
  - Estimated runtime
  - Health status
- Power consumption:
  - Current draw estimation
  - Average over last hour

Scheduled power actions (future feature):
- Schedule shutdown
- Schedule restart
- Power on schedule (if hardware supports)

**Settings Tab**:

General settings section:
- Hostname:
  - Current hostname displayed
  - Edit button (opens inline editor)
  - Apply changes button
  - Requires restart warning
  
- Timezone:
  - Current timezone
  - Dropdown selector (searchable list of timezones)
  - Auto-detect button (uses browser timezone)
  - Apply button
  
- Time synchronization:
  - NTP enabled toggle
  - NTP server address (editable)
  - Current time display
  - Sync now button

Web interface settings section:
- Default mode:
  - Radio buttons: Simple / Advanced
  - Determines landing page mode
  
- Mode persistence:
  - Toggle: Remember mode selection across page reloads
  - Note: Always returns to Simple after reboot
  
- Theme:
  - Light mode
  - Dark mode  
  - Auto (follows system preference)
  - Color scheme preview
  
- Language/Locale:
  - Language selector (if multi-language supported)
  - Date format
  - Time format (12/24 hour)
  - Number format

Notification settings section:
- Alert thresholds:
  - CPU usage: Slider or number input (percentage)
  - Memory usage: Slider or number input (percentage)
  - Temperature: Input field (degrees C)
  - Disk usage: Slider or number input (percentage)
  
- Notification display:
  - Duration (seconds or until dismissed)
  - Position (top-right, bottom-right, etc.)
  - Sound enabled toggle
  
- Email notifications (if configured):
  - Email address
  - Alert types to email

Advanced settings section:
- API settings:
  - Rate limiting toggle and threshold
  - WebSocket keep-alive interval
  - Request timeout
  
- Logging:
  - Default log level (Debug, Info, Warning, Error, Critical)
  - Log retention days
  - Log file size limits
  
- Storage:
  - Automatic cleanup toggle
  - Cleanup thresholds
  - Data to keep (captures, logs, backups)

Save all settings button
Reset to defaults button (with confirmation)

**System Information Tab**:

Hardware section:
- Raspberry Pi model
- CPU: Model, cores, architecture, current frequency
- RAM: Total, available, usage percentage
- Storage:
  - Root partition: Size, used, available
  - Data partition: Size, used, available
  - SD card health (if available)

Software section:
- Operating system: Name and version
- Kernel version
- RPi Engineer version
- Installation date
- Last update date
- Python version

Network section:
- Summary of all interfaces
- Active WAN interface
- Hotspot status
- Connected clients count

USB devices section:
- List of connected USB devices:
  - Device name
  - Vendor/Product ID
  - Type (serial, network, storage, etc.)
  - Driver in use

Serial devices section:
- List of detected serial devices
- Path, chipset, status

System health section:
- CPU temperature (current)
- Temperature history graph
- Throttling status (if ever throttled)
- Undervoltage status (if ever undervoltage)

Export system info button (saves as JSON or text file)

### Updates & Maintenance Page

**URL**: `/advanced/updates.html`

**Purpose**: System updates, backups, and maintenance

**Tab Structure**:
- Software Updates
- Configuration Backup
- Data Management

**Software Updates Tab**:

Current version section:
- Installed version (large, prominent)
- Installation date
- Last update check timestamp
- Update channel (stable, beta, dev)

Update check section:
- "Check for Updates" button (primary action)
- Checking status (spinner when active)
- Last check result:
  - Up to date message (with green checkmark)
  - Update available message (with badge/count)
  - Check failed message (with retry button)

Available updates section (if updates found):
- New version number (prominent)
- Release date
- Size to download
- Changelog tabs:
  - What's New (new features)
  - Improvements (enhancements)
  - Bug Fixes (fixes)
  - Breaking Changes (warnings, if any)
- Full changelog link

Update actions:
- "Install Update" button (primary, large)
- "View Full Changelog" link
- "Remind Me Later" button

Update process modal:
- Cannot be dismissed during update
- Progress steps displayed:
  - Preparing (checking prerequisites)
  - Backing up configuration (auto)
  - Downloading update files
  - Validating downloaded files
  - Applying update
  - Restarting services
  - Verifying installation
  - Complete
- Progress bar (overall)
- Current step highlighted
- Status messages
- Estimated time remaining
- Completion message with "View Changes" button

Update history section:
- Table of previous updates:
  - Version (from → to)
  - Date applied
  - Status (Success, Failed, Rolled back)
  - Actions:
    - View changelog
    - Rollback (if recent, within rollback window)

Rollback option:
- Available only for most recent update
- Available for limited time (e.g., 7 days)
- "Rollback to Previous Version" button
- Confirmation required
- Shows what will be rolled back

Update settings:
- Automatic update checks toggle
- Check frequency (daily, weekly)
- Notification preferences
- Update channel selection

**Configuration Backup Tab**:

Quick backup section:
- "Create Backup Now" button (large, primary)
- Backup description field (optional)
- Quick backup creates config-only backup

Backup options:
- Backup type selector:
  - Configuration only (recommended, smaller)
  - Configuration + user data (larger)
- What to include (if user data selected):
  - Packet capture files (checkbox)
  - Serial console logs (checkbox)
  - System logs (checkbox)
  - Module data (checkbox)
- Compression level (None, Fast, Best)

Create backup button
Estimated backup size displayed

Backup list:
- Table of existing backups:
  - Backup name (auto-generated or user-provided)
  - Type (Config / Full)
  - Date created
  - Size
  - Description (if provided)
  - Actions:
    - Download
    - Restore (opens restore modal)
    - Delete

Restore backup modal:
- Upload backup file section:
  - File selector
  - Or select from list of existing backups
  
- Backup information display:
  - Created date
  - RPi Engineer version
  - Backup type
  - Size
  - Contents list
  
- Restore options:
  - Restore all (default)
  - Selective restore (choose components):
    - Network configuration
    - Service settings
    - Hotspot configuration
    - Module configuration
    - User data (if included)
  
- Warnings:
  - Services will restart
  - Active sessions will be closed
  - Changes cannot be undone
  
- Restore button (requires confirmation)
- Cancel button

Restore process:
- Progress modal (cannot dismiss)
- Steps:
  - Validating backup file
  - Stopping services
  - Restoring files
  - Updating configuration
  - Restarting services
  - Verifying restoration
- Progress bar
- Status messages
- Completion notification

Automatic backup settings:
- Enable automatic backups toggle
- Backup schedule:
  - Daily (time picker)
  - Weekly (day + time)
  - Before updates (checkbox, always on)
- Retention policy:
  - Keep last X backups (number input)
  - Delete backups older than X days
  - Maximum storage for backups (MB)

**Data Management Tab**:

Storage overview:
- Visual storage breakdown:
  - System: X GB
  - Captures: X GB
  - Logs: X GB
  - Backups: X GB
  - Free space: X GB
- Pie chart or stacked bar
- Warnings if low space

Packet captures management:
- Total captures: count
- Total size: GB/MB
- Actions:
  - View all captures (link to Captures page)
  - Delete old captures:
    - Older than (date picker)
    - Delete button (with confirmation)
  - Delete all captures (strong confirmation required)
  - Export all captures (as ZIP)

Serial logs management:
- Total log files: count
- Total size: GB/MB
- Actions:
  - View all logs (link to Serial page)
  - Delete old logs (date picker + confirm)
  - Delete all logs (strong confirmation)
  - Export all logs (as ZIP)

System logs management:
- Total size: GB/MB
- Current log level
- Actions:
  - View logs (link to Logs page)
  - Delete old logs (keeps configured retention)
  - Clear all logs (strong confirmation)
  - Export system logs

Cleanup wizard:
- Automated cleanup tool
- Options:
  - Delete captures older than X days
  - Delete logs older than X days
  - Delete old backups (keeping Y most recent)
  - Compress old captures
- Preview how much space will be freed
- Run cleanup button

Factory reset section:
- Highly visible, warning-styled
- "Factory Reset System" button (red/danger)
- Multiple confirmations required:
  - First: "Are you sure?"
  - Second: Type "RESET" to confirm
- Options:
  - Preserve hotspot configuration (checked by default)
  - Preserve backups (checked by default)
- What will be reset:
  - All network configurations
  - All service settings
  - All module configurations
  - All user data (captures, logs)
  - Update history
- What will remain:
  - Base system installation
  - Hotspot config (if checked)
  - Backups (if checked)
- Cannot be undone warning
- System will reboot after reset

### Modules Page

**URL**: `/advanced/modules.html`

**Purpose**: Install, configure, and manage system modules

**Tab Structure**:
- Installed Modules
- Available Modules

**Installed Modules Tab**:

If no modules installed:
- Empty state message
- Illustration
- "Browse Available Modules" button

If modules installed:
- Module cards (grid layout on desktop, list on mobile):
  - Module icon/logo
  - Module name
  - Version number
  - Brief description
  - Status badge:
    - Enabled (green)
    - Disabled (gray)
    - Error (red)
  - Action buttons:
    - Configure (if module has settings)
    - Enable/Disable toggle
    - View Documentation
    - Uninstall

Module details (click on card or name):
- Full module information modal:
  - Name and description
  - Current version
  - Author/Maintainer
  - Installation date
  - Dependencies (list)
  - Provides (services, features)
  - Documentation (if available)
  - Actions: Configure, Enable/Disable, Uninstall

Configure module modal:
- Module-specific configuration form
- Fields generated from module schema
- Field types:
  - Text inputs
  - Dropdowns
  - Toggles
  - Number inputs
  - File uploads
- Validation messages
- Help text per field
- Apply/Save button
- Cancel button
- Reset to defaults button

Uninstall module:
- Confirmation dialog
- Warnings:
  - Dependencies check (if other modules depend on this)
  - Data loss warning (if module has data)
  - Services will restart
- Option to keep module data
- Uninstall button
- Cancel button

Uninstall process:
- Progress modal
- Steps:
  - Stopping module service
  - Removing module files
  - Updating configuration
  - Restarting services
- Completion notification

**Available Modules Tab**:

Module catalog:
- Search/filter bar:
  - Search by name or description
  - Category filter (Networking, Monitoring, Display, etc.)
  - Sort by (Name, Popularity, Date added)

Module cards (grid layout):
- Module icon
- Module name
- Brief description (truncated)
- Category badge
- Version available
- Size
- "Install" button (or "Installed" badge if already installed)

Module details modal (click on card):
- Full description
- Screenshots (if available)
- Version
- Size
- Requirements:
  - System requirements
  - Dependencies (other modules)
  - Minimum RPi Engineer version
- Installation notes
- Changelog
- Actions:
  - Install button (primary)
  - View Documentation
  - Close

Install module:
- Dependency check first:
  - Lists dependencies to install
  - Option to install all or cancel
- Installation progress modal:
  - Downloading module
  - Checking dependencies
  - Installing dependencies
  - Installing module
  - Configuring module
  - Enabling module
  - Progress bar
  - Status messages
- Configuration step (if module needs initial config):
  - Configuration form
  - Can skip and configure later
- Completion message:
  - Module installed successfully
  - Go to module (link)
  - Close button

Upload custom module:
- "Upload Custom Module" button
- File upload area (drag and drop or click)
- File requirements:
  - .zip or .tar.gz format
  - Contains module.json
- Upload and validate
- If valid:
  - Show module info
  - Install button
- If invalid:
  - Error message
  - Details about what's missing

Module management settings:
- Auto-update modules toggle
- Update check frequency
- Module repository URL (for custom repos)

### Logs & Monitoring Page

**URL**: `/advanced/logs.html`

**Purpose**: View system logs, metrics, and alerts

**Tab Structure**:
- System Logs
- Performance Metrics
- Alerts History

**System Logs Tab**:

Filter panel (collapsible):
- Log level multi-select:
  - All levels (default)
  - Debug
  - Info
  - Warning
  - Error
  - Critical
- Service filter (dropdown):
  - All services
  - Individual services listed
- Time range:
  - Last hour
  - Last 24 hours
  - Last 7 days
  - Custom range (date pickers)
- Search field:
  - Full-text search in log messages
  - Placeholder: "Search logs..."
- Apply filters button
- Clear all filters button

Log display area:
- Table format:
  - Timestamp (with timezone)
  - Level (color-coded badge):
    - Debug (gray)
    - Info (blue)
    - Warning (yellow)
    - Error (orange)
    - Critical (red)
  - Service (source of log)
  - Message (truncated, click to expand)
- Expandable rows:
  - Full message
  - Stack trace (if error)
  - Additional context
- Real-time updates:
  - Auto-scroll toggle
  - Pause updates button
  - Manual refresh button
- Pagination:
  - Rows per page selector
  - Page navigation
- Empty state if no logs match filters

Log entry details modal:
- Full log entry information:
  - Timestamp (precise)
  - Log level
  - Service/component
  - Full message
  - Stack trace (if applicable)
  - Context variables
  - Related logs (same request/session)
- Copy message button
- Close button

Export logs section:
- Export options:
  - Format: CSV, JSON, Plain text
  - Include filters applied
  - All logs or current page only
- Export button
- Download starts automatically

Log settings:
- Live updates toggle
- Update interval (seconds)
- Lines per page
- Timestamp format
- Wrap long lines toggle

**Performance Metrics Tab**:

Time range selector (top):
- Predefined ranges:
  - Last hour
  - Last 6 hours
  - Last 24 hours
  - Last 7 days
  - Last 30 days
  - Custom range
- Refresh interval selector:
  - 5 seconds
  - 10 seconds
  - 30 seconds
  - 1 minute
  - Manual only
- Auto-refresh toggle

Metrics dashboard:

CPU Usage chart:
- Line chart
- Shows percentage over time
- Multiple cores (if shown separately)
- Color-coded zones (normal, warning, critical)
- Current value displayed
- Statistics (avg, min, max)

Memory Usage chart:
- Stacked area chart showing:
  - Used memory
  - Buffers/Cache
  - Free memory
- Or line chart of used percentage
- Current value
- Statistics

Temperature chart:
- Line chart
- Temperature in Celsius
- Warning threshold line
- Critical threshold line
- Current value
- Min/max markers

Disk Usage:
- Multiple charts or single chart with series:
  - Root partition
  - Data partition
- Percentage used over time
- Current usage
- Growth trend

Network Traffic:
- Stacked area chart:
  - Received (Rx)
  - Transmitted (Tx)
- Per-interface toggle
- Units: Mbps or MB/s
- Total bandwidth used (today/selected period)

Disk I/O:
- Line chart
- Read and write operations
- IOPS or MB/s
- Current values

Service Status Over Time:
- Stacked timeline showing service uptime/downtime
- Color-coded per service
- Click to see details

Chart interactions:
- Hover for precise values
- Zoom in/out (pinch or buttons)
- Pan left/right through time
- Export chart as PNG
- Full-screen view

Statistics panel:
- Tabular statistics for selected time range:
  - Metric name
  - Current value
  - Average
  - Minimum (timestamp)
  - Maximum (timestamp)
  - 95th percentile
  - 99th percentile

Export metrics:
- Export as CSV
- Export as JSON
- Include charts as images (PDF)

**Alerts History Tab**:

Alerts list:
- Table or card view:
  - Timestamp
  - Severity (Critical, Warning, Info):
    - Critical: Red icon
    - Warning: Yellow icon
    - Info: Blue icon
  - Alert type (category)
  - Message
  - Status:
    - Active (ongoing)
    - Acknowledged
    - Resolved
  - Actions:
    - View details
    - Acknowledge
    - Dismiss

Filters:
- Severity multi-select
- Status (Active, Acknowledged, Resolved, All)
- Alert type (category dropdown)
- Date range
- Apply / Clear buttons

Alert details modal:
- Full alert information:
  - Alert ID
  - Timestamp (when triggered)
  - Severity and type
  - Full message
  - Affected component
  - Current value vs threshold
  - Recommendations / next steps
  - Alert history (if recurring)
- Actions:
  - Acknowledge (marks as seen)
  - Resolve (marks as fixed)
  - Snooze (temporary suppress)
  - View related logs
  - View related metrics

Acknowledged/Resolved alerts:
- Lighter styling
- Show who acknowledged/resolved (if multi-user in future)
- Timestamp of acknowledgement/resolution

Alert configuration:
- "Configure Alerts" button
- Links to System Management > Settings > Notifications
- Quick access to threshold settings

Alert summary:
- Statistics:
  - Total alerts (selected period)
  - Critical count
  - Warning count
  - Active alerts count
  - Most common alert type
- Chart: Alerts over time (bar chart by day or hour)

Export alerts:
- Export as CSV
- Export as JSON
- Include only selected filters

### Documentation Page

**URL**: `/docs/` or `/advanced/docs.html`

**Purpose**: Provide comprehensive embedded documentation

**Layout**:
- Left sidebar: Table of contents
- Main area: Rendered documentation
- Right sidebar: Quick navigation within page (anchors)

**Table of Contents** (left sidebar, tree structure):

Getting Started:
- Welcome
- Quick Start Guide
- First Time Setup
- Connecting to the Device
- Understanding the Interface

User Guides:
- Simple Mode Guide
- Advanced Mode Guide
- Switching Between Modes

Network Configuration:
- Interface Management
- Static vs DHCP Configuration
- VLAN Setup
- Routing and Failover
- WiFi Hotspot Configuration
- Saving Network Profiles
- Factory Reset Network

Serial Console:
- Connecting to Devices
- Opening a Console Session
- Configuring Serial Settings
- Using the Terminal
- File Transfer
- Session Logging
- Common Device Types:
  - Cisco Devices
  - Juniper Devices
  - HP/Aruba Devices
  - Other Vendors

Packet Capture:
- Starting a Basic Capture
- Configuring Capture Filters
- Live Packet Viewing
- Analyzing Captures
- Understanding Statistics
- Common Filter Examples
- Troubleshooting with Captures

System Management:
- Managing Services
- Power Options
- System Settings
- User Preferences
- Monitoring System Health

Updates and Maintenance:
- Checking for Updates
- Applying Updates
- Rolling Back Updates
- Creating Backups
- Restoring from Backup
- Data Management
- Factory Reset

Modules:
- What Are Modules
- Installing Modules
- Configuring Modules
- Available Modules:
  - Display Driver
  - (Other modules)
- Creating Custom Modules (developer)

Troubleshooting:
- Common Issues:
  - Cannot Connect to WiFi
  - Web Interface Not Loading
  - Remote Access Not Working
  - Serial Device Not Detected
  - Capture Not Starting
  - Network Configuration Issues
- Diagnostic Steps
- Viewing Logs
- Getting Help

Technical Reference:
- API Documentation (link to API-REFERENCE.md)
- Network Architecture
- Module Development
- File Locations

FAQ:
- Frequently Asked Questions (categorized)

**Documentation content area**:

Rendered documentation:
- Clean, readable typography
- Syntax highlighting for commands
- Copyable code blocks (copy button)
- Images and diagrams
- Tables formatted nicely
- Breadcrumb navigation
- Previous/Next navigation at bottom

**Right sidebar** (on desktop):
- "On this page" heading
- List of headings as jump links
- Active section highlighted
- Scrolls with page

Documentation features:
- Full-text search (searches all docs)
- Print-friendly version
- Dark mode support
- Font size controls
- Export as PDF (future)

Search results page:
- Search query displayed
- Results grouped by document
- Match highlighting
- Relevance sorting
- Filter by category

---

## Component Library

### Buttons

**Primary Button**:
- Visual: Solid background, high contrast
- Size: Minimum 44x44px touch target
- States: Default, Hover, Active, Disabled, Loading
- Use: Main call-to-action per section

**Secondary Button**:
- Visual: Outlined or lower contrast
- Size: Same as primary
- States: Same as primary
- Use: Alternative actions

**Danger/Warning Button**:
- Visual: Red/orange colors
- Size: Same as primary
- Requires: Confirmation before action
- Use: Destructive operations

**Icon Button**:
- Visual: Icon only, circular or square
- Size: 32x32px minimum
- Tooltip: Always present on hover
- Use: Space-constrained areas

**Link Button**:
- Visual: Styled as hyperlink
- Underline: On hover only
- Use: Tertiary actions, "Learn more" links

### Form Controls

**Text Input**:
- Label: Always present, clear
- Placeholder: Optional, example format
- Validation: Inline, as user types or on blur
- Error state: Red border, error message below
- Success state: Green border (optional)
- Disabled state: Grayed out, not editable

**Dropdown/Select**:
- Label: Always present
- Searchable: For lists >10 items
- Selected value: Clearly shown
- Disabled items: Grayed out
- Groups: Supported for organization

**Toggle Switch**:
- Label: Describes the state
- States: On (enabled) / Off (disabled)
- Immediate effect OR requires Apply button (specify)
- Disabled state: Grayed, not clickable

**Checkbox**:
- Label: To the right of checkbox
- Indeterminate state: Supported for parent/child
- Group: Multiple related checkboxes
- Disabled state: Grayed

**Radio Button**:
- Label: To the right of button
- Group: Mutually exclusive options
- Layout: Vertical preferred
- Disabled state: Grayed

**Date/Time Picker**:
- Calendar view: Month grid
- Time selector: Hours and minutes
- Timezone: Display current timezone
- "Now" button: Sets to current time
- Clear button: Clears selection

**File Upload**:
- Drag and drop area
- Or click to browse
- File type restrictions noted
- Max size displayed
- Preview (for images)
- Upload progress bar

### Cards and Containers

**Status Card**:
- Border: Color-coded (green=good, yellow=warning, red=error)
- Icon: Status indicator
- Content: Key information
- Action: Click to expand for details
- Expandable: Additional info hidden by default

**Action Card** (Simple Mode):
- Large icon: Centered or left
- Title: Large, clear text
- Description: Brief, 1-2 lines
- Button: Primary action at bottom
- Hover: Slight elevation/shadow
- Disabled: Grayed out, reason shown

**Information Card**:
- Header: Title and optional icon
- Content: Organized information
- Footer: Optional actions or metadata
- Collapsible: Optional for space saving

**Module Card**:
- Icon/Logo: Top or left
- Name and version: Prominent
- Description: Brief summary
- Status badge: Enabled/Disabled
- Actions: Configure, Enable/Disable, More
- Hover: Highlight for interaction

### Tables

**Data Table**:
- Header row: Column names, sortable
- Body rows: Data, hover highlight
- Actions column: Right-aligned, icon buttons
- Row selection: Checkbox in first column
- Empty state: Helpful message, call-to-action
- Loading state: Skeleton or spinner
- Pagination: At bottom if >25 rows
- Responsive: Mobile converts to cards

**Sortable Columns**:
- Click header to sort
- Visual indicator: Arrow up/down
- Default sort: Specified per table
- Multi-column sort: Optional, advanced

**Filterable Tables**:
- Filter controls: Above table
- Applied filters: Shown as badges, removable
- Clear all: Button to reset filters

### Modals and Dialogs

**Standard Modal**:
- Overlay: Semi-transparent dark background
- Container: Centered, white (or themed)
- Header: Title, close button (X)
- Body: Scrollable if tall
- Footer: Action buttons (right-aligned)
- Sizes: Small (400px), Medium (600px), Large (800px)
- Keyboard: Esc closes, Tab cycles focus
- Accessibility: Focus trap, ARIA attributes

**Full-Screen Modal**:
- For complex interfaces (console, capture viewer)
- Header: Title, close button
- Body: Full viewport minus header
- Footer: Optional, for actions
- Close: Button and Esc key

**Confirmation Dialog**:
- Question or warning text
- Two buttons: Confirm, Cancel
- Dangerous actions: Require typing confirmation
- Default focus: Cancel (safer)
- Keyboard: Enter confirms, Esc cancels

**Drawer/Slide-out**:
- Slides from side (left, right, top, bottom)
- Overlay: Optional
- Use: Contextual info, settings
- Close: X button, click overlay, Esc

### Notifications and Alerts

**Toast Notification**:
- Position: Top-right or bottom-right
- Types: Success, Info, Warning, Error
- Icon: Matches type
- Message: Brief, clear
- Auto-dismiss: Configurable (3-10 seconds)
- Manual dismiss: X button
- Action button: Optional (e.g., "Undo", "View")
- Stack: Multiple toasts stack

**Alert Banner**:
- Position: Top of page or section
- Types: Success, Info, Warning, Error
- Color-coded: Background and border
- Icon: Matches type
- Message: Can be longer than toast
- Dismissible: X button (optional)
- Action: Optional link or button

**Inline Alert**:
- Within a form or section
- Icon and message
- Color-coded
- Dismissible or persistent

### Progress Indicators

**Progress Bar**:
- Horizontal bar
- Percentage or fraction display
- Color: Matches status (green=success, yellow=warning)
- Striped/Animated: For ongoing operations
- Determinate: Known progress
- Indeterminate: Unknown progress (animated)

**Loading Spinner**:
- Sizes: Small (16px), Medium (32px), Large (64px)
- Centered: In context or full-page
- Color: Matches theme
- Message: Optional text below

**Skeleton Screen**:
- Placeholder for content loading
- Mimics layout of actual content
- Animated shimmer effect
- Replaces with real content when loaded

### Charts and Visualizations

**Line Chart**:
- Time-series data
- X-axis: Time (configurable format)
- Y-axis: Value (with units)
- Multiple series: Different colors
- Legend: Shows series names, toggle visibility
- Hover: Show precise values, crosshair
- Zoom: Drag to zoom in, button to reset
- Export: Save as PNG

**Bar Chart**:
- Comparative data
- Vertical or horizontal orientation
- Grouped or stacked bars
- Color-coded categories
- Hover: Show value
- Clickable: Optional drill-down

**Pie/Donut Chart**:
- Proportional data
- Segments: Color-coded, labeled
- Legend: With percentages
- Hover: Highlight segment, show value/percentage
- Click: Optional drill-down

**Sparkline**:
- Mini line chart
- Inline with text
- No axes or labels
- Quick visual trend indicator

**Gauge/Meter**:
- Single value display
- Visual indicator (needle, fill)
- Color-coded zones (green, yellow, red)
- Current value and range

### Icons

**Icon Set**:
- Consistent style throughout (e.g., Feather Icons, Heroicons)
- Sizes: 16px, 24px, 32px (standard)
- Stroke width: Consistent (e.g., 2px)
- Colors: Inherit from parent or specified

**Common Icons**:
- System:
  - Home, Settings, Power, Info, Help
- Navigation:
  - Menu, Close, Back, Forward, More
- Actions:
  - Play, Pause, Stop, Refresh, Download, Upload
  - Edit, Delete, Add, Search, Filter
- Status:
  - Check (success), X (error), Warning triangle
  - Info circle, Question circle
- Content:
  - File, Folder, Document, Image
- Network:
  - Wifi, Ethernet, Signal
- Interface:
  - Chevron down/up/left/right, Arrow down/up/left/right

**Icon Usage**:
- Always with accessible label (ARIA or tooltip)
- Consistent mapping (same icon for same action)
- Size appropriate to context

### Navigation Elements

**Top Navigation Bar**:
- Project branding/logo
- Page title (optional)
- Global actions (settings, user menu)
- Mode indicator
- Breadcrumbs (optional)

**Sidebar Navigation**:
- Vertical menu
- Collapsible to icons-only
- Grouped sections (optional)
- Active page highlighted
- Hover state clear
- Sub-menus expandable
- Responsive: Overlay on mobile

**Tabs**:
- Horizontal list
- Active tab highlighted (underline or background)
- Hover state
- Keyboard navigation (arrow keys)
- Overflow: Scrollable or dropdown on small screens

**Breadcrumbs**:
- Shows current location
- Clickable ancestors
- Separator: > or /
- Current page: Not clickable, different style

**Pagination**:
- Page numbers: Current, adjacent, first, last
- Previous/Next buttons
- "Showing X-Y of Z items" info
- Rows per page selector (optional)
- Jump to page input (optional)

### Status Indicators

**Badge**:
- Small colored label
- Text or number
- Positions: Top-right of icon (notification count), inline with text
- Colors: Match purpose (red for alerts, blue for info)

**Dot Indicator**:
- Small circle
- Colors:
  - Green: Active, healthy, running
  - Red: Error, stopped, critical
  - Yellow: Warning, degraded
  - Gray: Inactive, disabled
  - Blue: Info, in progress

**Status Text**:
- Short status message
- Color-coded
- Icon optional
- Examples: "Connected", "Offline", "Processing"

---

## Navigation Structure

### Simple Mode Navigation

- **Structure**: Single scrollable page
- **Sections**: Vertical cards
- **Navigation**: Scroll or anchor links (if page long)
- **Mode Switch**: Button at top and bottom

### Advanced Mode Navigation

**Primary Navigation** (Sidebar):
- Vertical list of pages
- Icons + labels
- Collapsible to icons-only
- Active page highlighted
- Grouping (optional separators)
- Bottom: Mode switch

**Secondary Navigation** (Tabs):
- Within pages for related sub-sections
- Horizontal tabs
- Example: Network page → Interfaces, VLANs, Routing, Profiles

**Breadcrumbs**:
- Show path: Dashboard > Network > Interface Configuration
- Each level clickable
- Auto-generated from page hierarchy

**Quick Actions**:
- Floating action button (FAB) or toolbar
- Context-sensitive actions
- Example: "New Capture" button on Capture page

### Mobile Navigation Adaptations

**Simple Mode**:
- Already mobile-friendly
- Scrollable vertical layout
- Large touch targets

**Advanced Mode**:
- Hamburger menu icon (top-left)
- Sidebar overlays content when open
- Tap outside or close button to dismiss
- Breadcrumbs: Minimal, last two levels only
- Tabs: Scrollable horizontally

---

## Responsive Design

### Breakpoints

Standard responsive breakpoints:
- **Mobile**: 0 - 639px (phones)
- **Tablet**: 640px - 1023px (tablets, small laptops)
- **Desktop**: 1024px+ (laptops, desktops)

Additional breakpoints (if needed):
- **Large Desktop**: 1440px+ (large monitors)

### Layout Adaptations

**Mobile** (< 640px):
- Single column layout
- Stacked components
- Full-width cards
- Hamburger menu (Advanced mode)
- Tables → Card layout
- Modals → Full-screen
- Reduced font sizes (slightly)
- Larger touch targets

**Tablet** (640px - 1023px):
- Two-column layout (where appropriate)
- Sidebar: Collapsible or icons-only
- Tables: Reduce columns, most important first
- Modals: Large centered (not full-screen)
- Charts: Stack vertically or 2-column

**Desktop** (1024px+):
- Multi-column layouts
- Sidebar: Full width with labels
- Tables: All columns visible
- Modals: Sized appropriately
- Charts: Multi-column grid
- More whitespace

### Component Responsiveness

**Cards**:
- Mobile: Full width, stacked
- Tablet: 2 columns (if appropriate)
- Desktop: 3-4 columns or list view

**Tables**:
- Mobile: Convert to cards (vertical layout per row)
- Tablet: Reduce columns, horizontal scroll if needed
- Desktop: Full table

**Forms**:
- Mobile: Full width inputs, stacked labels
- Tablet: Two-column form layout (related fields)
- Desktop: Optimized for efficiency

**Navigation**:
- Mobile: Hamburger menu, bottom nav (optional)
- Tablet: Collapsible sidebar
- Desktop: Full sidebar

**Charts**:
- Mobile: Full width, vertical stack
- Tablet: Two charts per row
- Desktop: Grid layout (2x2, 3x1, etc.)

**Modals**:
- Mobile: Full-screen
- Tablet: Large centered
- Desktop: Appropriate size (small/medium/large)

### Touch Optimizations

**Touch Targets**:
- Minimum: 44x44px (Apple, WCAG guideline)
- Recommended: 48x48px (Material Design)
- Spacing: 8px between targets minimum

**Gestures**:
- Swipe: Navigate between tabs, dismiss cards
- Pull to refresh: On appropriate pages
- Long press: Context menu
- Pinch to zoom: Charts, images
- Tap: Primary action
- Double tap: Optional secondary action

**Feedback**:
- Visual: Highlight on touch
- Haptic: Optional, use sparingly
- Animation: Smooth, not janky

### Text and Readability

**Font Sizes**:
- Mobile:
  - Body: 16px minimum (for readability without zoom)
  - Headings: 24px, 20px, 18px (h1, h2, h3)
  - Small: 14px minimum
- Desktop:
  - Body: 16-18px
  - Headings: 32px, 24px, 20px
  - Small: 14px

**Line Height**:
- Body text: 1.5-1.6
- Headings: 1.2-1.3

**Line Length**:
- Optimal: 50-75 characters
- Maximum: 90 characters
- Use containers to constrain width

**Contrast**:
- WCAG AA minimum: 4.5:1 for normal text
- WCAG AAA preferred: 7:1 for normal text
- Large text (18pt+): 3:1 minimum

---

## Real-Time Updates

### WebSocket Connection

**Establishment**:
- Automatically on page load
- Connect to: `ws://192.168.50.1/ws/`
- Authentication: None (per requirements)
- Heartbeat: Every 30 seconds (ping/pong)

**Reconnection**:
- Automatic on disconnect
- Exponential backoff: 1s, 2s, 4s, 8s, max 30s
- Visual indicator: "Reconnecting..." message
- Resume normal operation on reconnect

**Message Format**:
- JSON structure:
  - `type`: Message type (e.g., "system_metrics", "network_status")
  - `timestamp`: ISO 8601 timestamp
  - `data`: Message payload (object)

**Message Types**:
- `system_metrics`: CPU, RAM, temp, disk (every 1-2 seconds)
- `network_status`: Interface status changes (on change + every 10s)
- `service_status`: Service state changes (on change)
- `alert`: New system alert (immediate)
- `capture_progress`: Active capture statistics (every 1 second)
- `serial_data`: Serial console data (real-time stream)
- `log_entry`: New log entry (if log page active)

**Client Handling**:
- Parse incoming messages
- Route to appropriate handlers
- Update UI components
- Buffer rapid updates (debounce/throttle)
- Queue updates if page not visible

### Update Frequencies

**System Metrics**:
- Frequency: Every 1-2 seconds
- Components: CPU, Memory, Temperature, Disk
- Throttle: Update UI maximum every second even if data arrives faster

**Network Status**:
- On change: Immediate update
- Periodic: Every 10 seconds (even if no change)
- Components: Interface status, IP addresses, connectivity

**Service Status**:
- On change: Immediate update (start, stop, fail)
- No periodic updates (change-driven only)

**Alerts**:
- Immediate: New alerts pushed instantly
- Display: Toast notification
- Update: Alerts panel/page

**Capture Progress**:
- Frequency: Every 1 second while active
- Components: Packet count, file size, duration, rate

**Serial Console**:
- Real-time: As data arrives (no buffering)
- Throttle: Only if necessary for performance

**Log Entries**:
- If log viewer active: Real-time stream
- If log viewer inactive: No push (fetch on page load)

### Fallback Mechanism

**WebSocket Unavailable**:
- Fall back to HTTP polling
- Polling interval: Every 5 seconds
- Display warning: "Real-time updates unavailable, using polling"

**Polling Behavior**:
- Sequential requests (not simultaneous)
- Same endpoints as WebSocket data would push
- Parse responses and update UI

**User Notification**:
- Banner message: "Reduced update frequency due to connection issues"
- Option: "Retry WebSocket connection" button

---

## Accessibility

### WCAG Compliance

**Target Level**: WCAG 2.1 Level AA (minimum)
- Perceivable: Content available to senses
- Operable: Interface navigable
- Understandable: Information and operation clear
- Robust: Compatible with assistive technologies

### Keyboard Navigation

**Tab Order**:
- Logical, top-to-bottom, left-to-right
- Skip to main content link (first tab stop)
- Interactive elements only (no decorative elements)
- No keyboard traps (can tab out of all elements)

**Keyboard Shortcuts**:
- Tab: Next element
- Shift+Tab: Previous element
- Enter/Space: Activate button or link
- Escape: Close modal, cancel action
- Arrow keys: Navigate within lists, dropdowns, tabs
- Custom shortcuts: Documented, configurable

**Focus Indicators**:
- Visible: High-contrast outline or border
- Never remove: :focus-visible supported, but fallback to :focus
- Consistent: Same style throughout application

### Screen Reader Support

**Semantic HTML**:
- Headings: Hierarchical (h1, h2, h3...)
- Lists: Use `<ul>`, `<ol>`, `<dl>` appropriately
- Forms: `<form>`, `<label>`, `<input>`, `<button>`
- Landmarks: `<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`

**ARIA Attributes**:
- Labels: `aria-label`, `aria-labelledby` for non-obvious elements
- Descriptions: `aria-describedby` for additional context
- States: `aria-expanded`, `aria-selected`, `aria-checked`
- Roles: `role="button"`, `role="dialog"`, etc. (only when semantic HTML insufficient)
- Live regions: `aria-live` for dynamic content updates

**Alt Text**:
- Images: Descriptive alt attribute (not empty unless decorative)
- Icons: `aria-label` if icon alone, or visible label nearby
- Decorative: `alt=""` or `aria-hidden="true"`

**Form Accessibility**:
- Labels: Associated with inputs (for attribute)
- Fieldsets: Group related inputs
- Error messages: Announced by screen reader
- Required fields: Indicated with `aria-required` and visual marker
- Validation: Errors announced in `aria-live` region

**Dynamic Content**:
- Live regions: Use `aria-live="polite"` or `"assertive"`
- Loading states: Announced when content loading
- Updates: Non-intrusive announcements

### Visual Accessibility

**Color Contrast**:
- Normal text: 4.5:1 minimum
- Large text (18pt or 14pt bold): 3:1 minimum
- UI components: 3:1 minimum
- Test: Use contrast checker tools

**Color Independence**:
- Never rely solely on color to convey information
- Use text labels, icons, patterns in addition to color
- Examples:
  - Status: Green dot + "Running" text
  - Error: Red border + error icon + message

**Text Sizing**:
- Base font: 16px minimum
- Scalable: Zoomable up to 200% without loss of functionality
- Responsive: Text reflows, doesn't truncate

**Focus Indicators**:
- Visible: Clearly distinguishable
- High contrast: Against background
- Not removed: Never use `outline: none` without replacement

**Animation**:
- Respect `prefers-reduced-motion` media query
- Disable or reduce animations if user preference set
- No flashing content (>3 flashes per second)

### Other Accessibility Features

**Language**:
- `lang` attribute on HTML tag
- Changes in language marked with `lang` on element

**Page Titles**:
- Unique and descriptive for each page
- Format: "Page Name - RPi Engineer-in-a-Box"

**Skip Links**:
- "Skip to main content" link (first tab stop, visible on focus)
- Additional skip links if needed (e.g., "Skip to navigation")

**Error Identification**:
- Clearly identify errors in forms
- Explain how to fix
- Move focus to first error (or error summary)

**Help and Documentation**:
- Accessible documentation
- Context-sensitive help
- Tooltips accessible via keyboard

---

## Performance Requirements

### Page Load Performance

**Initial Load**:
- Target: <3 seconds on Raspberry Pi 4
- Time to First Byte (TTFB): <500ms
- First Contentful Paint (FCP): <1.5 seconds
- Time to Interactive (TTI): <5 seconds
- Largest Contentful Paint (LCP): <2.5 seconds

**Asset Sizes**:
- HTML: <50KB per page
- CSS: <100KB total (minified, gzipped)
- JavaScript: <500KB total (minified, gzipped)
- Fonts: <200KB total
- Images: Optimized, <100KB each (use WebP or compressed)
- Total initial page weight: <2MB

**Optimization Techniques**:
- Minification: All CSS and JS
- Compression: Gzip or Brotli for text assets
- Caching: Long cache headers for static assets
- Code splitting: Load only needed JavaScript per page
- Lazy loading: Images and non-critical content
- Critical CSS: Inline critical styles
- Defer non-critical JS: Use defer or async attributes

### Runtime Performance

**Frame Rate**:
- Target: 60fps for animations and scrolling
- Smooth transitions and interactions
- No janky scrolling

**Rendering**:
- Minimize reflows and repaints
- Use CSS transforms for animations (GPU-accelerated)
- Avoid layout thrashing

**JavaScript Execution**:
- Non-blocking: Long tasks split into chunks
- Web Workers: For heavy computation (if needed)
- Debounce: Input handlers (search, resize)
- Throttle: Scroll and mouse move handlers

**Memory Usage**:
- No memory leaks
- Clean up event listeners and timers
- Garbage collection friendly (avoid excessive object creation)

### API and Data Performance

**API Response Time**:
- Target: <100ms for most endpoints
- Accept up to 500ms for complex operations
- Show loading states for anything >300ms

**Data Transfer**:
- Minimize payload size (send only needed data)
- Pagination: For large lists (not all at once)
- Compression: Gzip responses
- Caching: Cache appropriate responses

**Real-Time Updates**:
- WebSocket: Efficient, low overhead
- Throttle updates: Don't overwhelm UI
- Batch updates: Combine multiple changes if rapid

### Resource Management

**Caching Strategy**:
- Static assets: Cache for 1 year, bust with versioning/hash
- API responses: Cache where appropriate (GET requests, short TTL)
- Service worker: Offline support (future enhancement)

**Lazy Loading**:
- Images: Load when near viewport
- Charts: Load library when needed
- Modules: Load on demand
- Documentation: Load sections as accessed

**Bundle Optimization**:
- Tree shaking: Remove unused code
- Code splitting: Separate bundles per route/feature
- Dynamic imports: Load features on demand
- Vendor chunks: Separate third-party code

### Performance Monitoring

**Metrics to Track**:
- Page load times (real user monitoring)
- API response times
- Error rates
- Resource usage (CPU, memory from browser)
- WebSocket message latency

**Performance Budget**:
- JavaScript: <500KB
- CSS: <100KB
- Images: <2MB total
- Total page weight: <3MB
- API response: <100ms average

**Testing**:
- Test on actual Raspberry Pi 4 hardware
- Test on slower RPi 3B+ (ensure acceptable performance)
- Mobile device testing (various Android/iOS devices)
- Slow network simulation (3G)
- Lighthouse audits (target score >90)

### Optimization for Raspberry Pi

**Specific Considerations**:
- Limited CPU: Minimize JavaScript execution
- Limited memory: Avoid memory-intensive operations
- SD card I/O: Minimize writes, efficient reading
- Browser: Chromium on Raspberry Pi OS (if local display used)

**Recommendations**:
- Progressive enhancement: Core functionality works without JS
- Reduce animations on RPi 3B+ (check CPU model)
- Efficient DOM manipulation (virtual DOM or minimal updates)
- Avoid excessive console logging in production

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial web interface specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- API-REFERENCE.md
- DOCUMENTATION-GUIDELINES.md
- INSTALLATION-SPECIFICATION.md
# Packet Capture Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Capture Management](#capture-management)
3. [Filtering and Selection](#filtering-and-selection)
4. [Live Capture Viewing](#live-capture-viewing)
5. [Capture Analysis](#capture-analysis)
6. [Storage Management](#storage-management)
7. [Multiple Captures](#multiple-captures)
8. [Performance Considerations](#performance-considerations)
9. [Integration](#integration)
10. [Advanced Features](#advanced-features)

---

## Overview

### Purpose

The Packet Capture feature enables users to capture, view, analyze, and store network traffic from any available network interface. This is essential for troubleshooting network issues, analyzing application behavior, and documenting network activity.

### Core Requirements

**Functional Requirements**:
- Capture packets on any network interface
- Apply BPF (Berkeley Packet Filter) filters
- Live packet viewing in browser
- Save captures to PCAP format
- Basic traffic analysis and statistics
- Multiple simultaneous captures on different interfaces
- Scheduled and duration-limited captures
- Download captures for offline analysis

**Non-Functional Requirements**:
- Capture full-duplex gigabit traffic without packet loss (on RPi 4/5)
- Live viewing latency <500ms
- Support captures up to tens of GB in size
- Minimal CPU overhead
- Storage limited only by available disk space
- Compatible with Wireshark and other PCAP tools

### Use Cases

**Primary Use Case**: Basic Traffic Troubleshooting
- User experiencing connectivity issues
- Clicks "Capture Packets" in simple mode
- Selects interface (e.g., eth0)
- Clicks "Start Capture"
- Reproduces issue
- Stops capture
- Downloads PCAP for analysis in Wireshark

**Secondary Use Case**: Application Analysis
- Engineer needs to analyze application traffic
- Starts capture with filter (e.g., "tcp port 443")
- Opens live viewer to see traffic in real-time
- Identifies issue from packet details
- Exports relevant packets

**Tertiary Use Case**: Continuous Monitoring
- Needs to monitor traffic over extended period
- Starts capture with time limit (e.g., 1 hour)
- Capture runs unattended
- Automatic stop after duration
- Log reviewed later

### Technical Foundation

**Capture Engine**: 
- tcpdump (primary)
- tshark (for analysis)
- libpcap (underlying library)

**File Format**: 
- PCAP (packet capture)
- PCAPNG (packet capture next generation, optional)

**Filter Syntax**: 
- BPF (Berkeley Packet Filter)
- Standard tcpdump filter syntax

---

## Capture Management

### Capture Lifecycle

**Capture States**:
- **Configuring**: User setting up capture parameters
- **Starting**: Initializing capture process
- **Running**: Actively capturing packets
- **Paused**: Capture process suspended (optional feature)
- **Stopping**: Gracefully terminating capture
- **Completed**: Capture finished, file saved
- **Failed**: Error occurred during capture

**Capture Creation**:
1. User initiates new capture (clicks "New Capture")
2. Configuration modal presented
3. User selects interface
4. User optionally configures:
   - Capture filter
   - Duration/size limits
   - Advanced options
5. User clicks "Start Capture"
6. Backend validates configuration
7. Backend starts tcpdump process
8. Capture ID assigned (UUID)
9. Capture metadata created
10. User notified of successful start
11. Capture appears in active captures list

**Capture Termination**:
- **User-Initiated**: User clicks "Stop" button
- **Time-Limited**: Automatic stop after duration expires
- **Size-Limited**: Automatic stop when file size reached
- **Packet-Limited**: Automatic stop after N packets captured
- **Error**: Automatic stop on error (interface down, disk full, etc.)

**Post-Capture**:
1. tcpdump process terminates gracefully
2. Capture file finalized
3. Capture metadata updated (end time, final stats)
4. Capture moved from active to completed list
5. User notified of completion
6. Capture available for viewing and download

### Capture Configuration

**Basic Parameters**:

**Interface Selection**:
- Dropdown list of all available network interfaces
- Show: Friendly name, kernel name, IP address, status
- Only show UP interfaces by default
- Option to show all interfaces (including DOWN)
- Validation: Cannot capture on DOWN interface

**Capture Name**:
- Optional user-provided name
- If not provided, auto-generated:
  - Format: `<interface>_<timestamp>`
  - Example: `eth0_2026-02-01_14-30-00`
- Used for display and file naming

**Duration Limits**:
- **Unlimited** (default): Runs until manually stopped
- **Time-based**: Hours, minutes, seconds
  - Input fields for H:M:S
  - Converted to total seconds
  - Timer displayed during capture
  - Auto-stop when timer expires
- **Packet count**: Stop after N packets
  - Input field for count
  - Counter displayed during capture
  - Auto-stop when count reached
- **File size**: Stop when file reaches size
  - Input field in MB or GB
  - Size displayed during capture
  - Auto-stop when size reached (approximately)

**Advanced Options**:

**Promiscuous Mode**:
- Toggle: On (default) / Off
- On: Capture all packets seen by interface (even if not destined for this host)
- Off: Only capture packets destined for this host
- Explanation: "Enable to capture all traffic on network segment"

**Snapshot Length** (snaplen):
- Bytes to capture per packet
- Default: 0 (capture full packet)
- Options: 64, 128, 256, 512, 1024, 1518, 9000, unlimited
- Explanation: "Truncate packets to save space (0 = full packet)"
- Use case: Just need headers, not payload

**Buffer Size**:
- Capture buffer in MB
- Default: 2MB
- Range: 1-100MB
- Larger = fewer dropped packets but more memory

**Ring Buffer**:
- Toggle: Off (default) / On
- When on, circular capture:
  - Keep only last N MB
  - Oldest data overwritten
  - Useful for continuous monitoring
- Ring buffer size: MB (e.g., 100MB)
- Note: Cannot view live or seek backward

**File Rotation**:
- Toggle: Off (default) / On
- When on, split into multiple files:
  - Size per file: MB (e.g., 50MB)
  - Number of files: Count (e.g., 10)
  - Oldest file deleted when limit reached
- Useful for long captures

### Capture Metadata

**Information Tracked**:
- **Capture ID**: UUID
- **Capture Name**: User-provided or auto-generated
- **Interface**: Kernel name (e.g., eth0)
- **Start Time**: ISO 8601 timestamp
- **End Time**: ISO 8601 timestamp (when completed)
- **Duration**: Seconds (calculated or real-time)
- **Packet Count**: Total packets captured
- **Bytes Captured**: Total bytes in capture file
- **File Path**: Location on disk
- **File Size**: Size in bytes
- **Capture Filter**: BPF filter applied (if any)
- **Promiscuous Mode**: Boolean
- **Snapshot Length**: Bytes
- **Status**: Running, Paused, Completed, Failed
- **Error Message**: If failed
- **User Notes**: Optional user-added notes

**Metadata Storage**:
- Database record for each capture
- Allows querying and listing captures
- Separate from PCAP file (PCAP has limited metadata)

---

## Filtering and Selection

### Capture Filters

**Purpose**: 
- Reduce data captured
- Save disk space and CPU
- Focus on relevant traffic

**Filter Types**:
- **No Filter**: Capture everything (default in simple mode)
- **BPF Filter**: Advanced text-based filter
- **Simple Filter**: GUI-based filter builder (simple mode)

### BPF Filter Syntax

**Berkeley Packet Filter**:
- Standard syntax used by tcpdump, Wireshark
- Filters applied during capture (efficient)
- Complex filters possible

**Common Filter Examples**:

Protocol filters:
```
tcp                     # TCP traffic only
udp                     # UDP traffic only
icmp                    # ICMP traffic only
arp                     # ARP traffic only
ip                      # IP traffic (IPv4)
ip6                     # IPv6 traffic
```

Host filters:
```
host 192.168.1.1           # Traffic to/from specific IP
src host 192.168.1.1       # Traffic from specific IP
dst host 192.168.1.1       # Traffic to specific IP
net 192.168.1.0/24         # Traffic to/from subnet
```

Port filters:
```
port 80                    # Port 80 (HTTP)
src port 80                # From port 80
dst port 80                # To port 80
portrange 80-443           # Port range
```

Combined filters:
```
tcp and port 443           # HTTPS traffic
host 192.168.1.1 and tcp   # TCP to/from specific host
not arp and not icmp       # Exclude ARP and ICMP
(tcp port 80) or (tcp port 443)  # HTTP or HTTPS
```

Advanced filters:
```
tcp[tcpflags] & tcp-syn != 0     # TCP SYN packets
icmp[icmptype] == icmp-echo      # ICMP echo requests (ping)
ether src 00:11:22:33:44:55      # Specific MAC address
vlan                             # VLAN tagged traffic
greater 1000                     # Packets larger than 1000 bytes
less 100                         # Packets smaller than 100 bytes
```

**Filter Validation**:
- Syntax check before starting capture
- Use tcpdump's built-in validation
- Display clear error message if invalid
- Suggest corrections for common mistakes

**Filter Builder** (Simple Mode):

GUI components:
- **Protocol**: Dropdown (Any, TCP, UDP, ICMP, ARP)
- **Direction**: Dropdown (Any, Inbound, Outbound)
- **Source IP**: Text input with validation
- **Destination IP**: Text input with validation
- **Source Port**: Number input
- **Destination Port**: Number input
- **VLAN**: Toggle and VLAN ID input
- **Exclude**: Checkbox to negate filter

Multiple conditions:
- "Add Condition" button
- AND/OR between conditions
- Remove condition button
- Preview generated BPF filter

Example flow:
1. User selects "TCP" from protocol
2. User enters "443" in destination port
3. Filter builder generates: `tcp and dst port 443`
4. User clicks "Preview BPF"
5. Generated filter displayed
6. User can edit manually if needed

### Display Filters

**Purpose**:
- Filter already captured packets
- Doesn't reduce capture size
- Applied in viewer, not during capture

**Difference from Capture Filters**:
- Capture filter: What gets captured (tcpdump)
- Display filter: What gets shown (viewer)
- Display filters can be changed anytime in viewer
- Capture filter is fixed once capture starts

**Display Filter Syntax**:
- Similar to BPF but more powerful (if using tshark)
- Can filter by higher-level protocols
- Can filter by protocol fields

**Quick Filters**:
- Buttons in viewer for common filters:
  - TCP only
  - UDP only
  - ICMP only
  - HTTP traffic
  - DNS traffic
  - Errors only (RST, ICMP unreachable, etc.)

---

## Live Capture Viewing

### Live Viewer Architecture

**Data Flow**:
```
tcpdump → File → Parser → WebSocket → Browser
         ↓                              ↓
    Capture File                 Live Display
```

**Approaches**:

**Approach 1: Tail the file**
- tcpdump writes to file continuously
- Backend tails file (reads new data as written)
- Parser converts binary PCAP to JSON
- Send packets to browser via WebSocket
- Pro: Simple, reuses capture file
- Con: Higher latency, more CPU for parsing

**Approach 2: Duplicate stream**
- tcpdump writes to file AND to pipe
- Backend reads from pipe in real-time
- Parser converts to JSON immediately
- Send to browser via WebSocket
- Pro: Lower latency
- Con: More complex, duplicate processing

**Chosen Approach**: Approach 1 (tail file)
- Simpler to implement
- Latency <500ms acceptable
- Less chance of data loss

### Live Viewer UI

**Viewer Layout**:

Three-pane design:
1. **Top Pane**: Packet list (table)
2. **Middle Pane**: Packet details (tree)
3. **Bottom Pane**: Hex dump

**Packet List** (Top Pane):
- Table with columns:
  - **No.**: Packet number in capture
  - **Time**: Timestamp (relative, absolute, or delta)
  - **Source**: Source IP (or MAC if no IP)
  - **Destination**: Destination IP (or MAC)
  - **Protocol**: Highest-level protocol (HTTP, DNS, TCP, UDP, etc.)
  - **Length**: Packet length in bytes
  - **Info**: Protocol-specific summary (e.g., "GET /index.html")
  
- Features:
  - Auto-scroll (follows new packets)
  - Freeze display (stop auto-scroll)
  - Sortable columns
  - Row selection (click to view details)
  - Protocol-based coloring (optional):
    - TCP: Blue
    - UDP: Cyan
    - ICMP: Yellow
    - ARP: Orange
    - Errors: Red

**Packet Details** (Middle Pane):
- Tree view of selected packet
- Expandable protocol layers:
  - Frame (capture metadata)
  - Ethernet (MAC addresses, EtherType)
  - IP (source/dest IP, TTL, flags, etc.)
  - TCP/UDP (source/dest port, flags, checksums)
  - Application (HTTP, DNS, etc. parsed data)
  
- Features:
  - Click layer to expand/collapse
  - Show field names and values
  - Hex offset for each field
  - Copy field value

**Hex Dump** (Bottom Pane):
- Raw packet data in hexadecimal
- Offset column (hexadecimal)
- Hex bytes (16 bytes per line)
- ASCII representation (printable chars)
- Highlight selected field from details pane

**Controls** (Toolbar):
- **Display Filter**: Text input, Apply button
- **Quick Filters**: Button group (TCP, UDP, ICMP, HTTP, DNS, Clear)
- **Auto-Scroll**: Toggle button
- **Color Coding**: Toggle button
- **Time Format**: Dropdown (Relative, Absolute, Delta)
- **Name Resolution**: Toggle (resolve IPs to hostnames, ports to service names)
- **Stop Capture**: Button (stops capture, viewer remains open)
- **Download**: Button (download PCAP file)
- **Close**: Button (close viewer)

**Status Bar**:
- Total packets captured
- Displayed packets (after display filter)
- Capture duration
- File size
- Capture rate (packets/sec, Mbps)

### Live Streaming

**Update Frequency**:
- Poll capture file every 500ms (configurable)
- Read new packets since last poll
- Parse and send to browser
- Browser updates packet list

**Throttling**:
- If many packets arriving rapidly, send in batches
- Max batch size: 100 packets (configurable)
- Max update frequency: 2 times per second
- Prevents overwhelming browser

**Buffer Management**:
- Browser maintains packet list (virtual scrolling for performance)
- Max packets in memory: 10,000 (configurable)
- Older packets discarded if limit reached
- User can adjust limit or disable (memory permitting)

**Performance**:
- Virtual scrolling: Only render visible packets
- Lazy parsing: Only parse packet details on selection
- Efficient DOM updates: Batch inserts

---

## Capture Analysis

### Statistics

**Overview Statistics**:
- **Capture File**:
  - Filename and path
  - File size
  - Data rate (average Mbps)
  
- **Packets**:
  - Total packet count
  - Average packet size
  - Packet rate (average pps)
  - Packet size distribution (histogram)
  
- **Time**:
  - Start time
  - End time
  - Duration
  - First packet timestamp
  - Last packet timestamp

**Protocol Distribution**:
- Pie chart or bar chart showing:
  - Percentage by packet count
  - Percentage by byte count
- Protocols: Ethernet, IPv4, IPv6, TCP, UDP, ICMP, ARP, Other
- Drill-down to application protocols (HTTP, DNS, TLS, etc.)

**Protocol Hierarchy**:
- Tree view of protocols:
  ```
  Frame (100%)
    ├─ Ethernet (100%)
    │   ├─ IPv4 (80%)
    │   │   ├─ TCP (60%)
    │   │   │   ├─ HTTP (30%)
    │   │   │   ├─ TLS (20%)
    │   │   │   └─ Other (10%)
    │   │   ├─ UDP (15%)
    │   │   │   ├─ DNS (10%)
    │   │   │   └─ Other (5%)
    │   │   └─ ICMP (5%)
    │   ├─ IPv6 (15%)
    │   └─ ARP (5%)
  ```
- Packets and bytes per protocol
- Percentage of total

**Conversations**:
- List of unique communication pairs
- Table columns:
  - Source address
  - Destination address
  - Protocol
  - Packets (A→B and B→A)
  - Bytes (A→B and B→A)
  - Duration
  - Avg rate
- Sortable by any column
- Filter: Show only conversations with >N packets or >N bytes

**Endpoints**:
- List of unique IP addresses seen
- Table columns:
  - IP address
  - Hostname (if name resolution on)
  - Packets sent
  - Packets received
  - Bytes sent
  - Bytes received
  - Total packets
  - Total bytes
- Sortable by any column
- Identify "top talkers"

**IO Graph**:
- Line chart of traffic over time
- X-axis: Time (seconds or minutes)
- Y-axis: Packets/sec or Mbps
- Multiple series:
  - All traffic
  - TCP traffic
  - UDP traffic
  - Errors
- Identify traffic patterns, spikes, gaps

### Protocol-Specific Analysis

**HTTP Statistics** (if HTTP traffic present):
- HTTP requests by method (GET, POST, etc.)
- Response codes (200, 404, 500, etc.)
- Top requested URLs
- Top user agents
- Average response time

**DNS Statistics** (if DNS traffic present):
- Query types (A, AAAA, MX, etc.)
- Top queried domains
- Response codes (NOERROR, NXDOMAIN, etc.)
- Average query time

**TCP Analysis**:
- SYN/ACK analysis (connection setup)
- RST packets (connection errors)
- Retransmissions
- Out-of-order packets
- Window size issues
- Expert info (warnings, errors)

**Expert Information**:
- Automatically detected issues:
  - Warnings (retransmissions, duplicate ACKs)
  - Errors (checksum errors, malformed packets)
  - Notes (informational)
- Grouped by severity
- Click to see packets

### Advanced Analysis

**Follow Stream**:
- Select a packet
- "Follow TCP Stream" (or UDP)
- Show entire conversation
- Display as:
  - ASCII text
  - Hex dump
  - Both
- Color-coded by direction (client, server)
- Save stream to file

**Time Sequence Graph** (TCP):
- Graph showing sequence numbers over time
- Identify retransmissions, out-of-order
- Zoom and pan

**Compare Captures**:
- Load two captures
- Compare statistics side-by-side
- Useful for before/after troubleshooting

---

## Storage Management

### File Storage

**Storage Location**:
- Directory: `/opt/rpi-engineer/data/captures/`
- Subdirectories (optional): By date `/captures/2026/02/01/`
- Filename format: `<capture_name>.pcap`
- Example: `/opt/rpi-engineer/data/captures/eth0_2026-02-01_14-30-00.pcap`

**File Format**:
- PCAP (packet capture) - Standard format
- Compatible with Wireshark, tcpdump, tshark
- Optional: PCAPNG (more metadata, larger file)

**Storage Limits**:
- No hard limits (use all available disk space)
- Alert user when disk space low (<1GB free)
- Option: Set soft limit (e.g., captures can use max 10GB)
- Oldest captures can be auto-deleted (optional, off by default)

### File Management

**Capture List**:
- Table view of all captures (active + completed)
- Columns:
  - Capture name
  - Interface
  - Date/time
  - Duration
  - Packet count
  - File size
  - Status
  - Actions
- Sortable columns
- Filter: By interface, date range, name
- Search: Text search in capture names

**Actions per Capture**:
- **View/Analyze**: Open in analyzer modal
- **Download**: Download PCAP file to browser
- **Delete**: Delete capture file (with confirmation)
- **Add Notes**: User can add descriptive notes
- **Export**: Include in bulk export

**Bulk Actions**:
- Select multiple captures (checkboxes)
- **Download Selected**: Creates ZIP file with selected captures
- **Delete Selected**: Delete multiple (with confirmation)
- **Export All**: Export all captures as ZIP

**Cleanup Tools**:
- **Delete Old Captures**:
  - Specify date (older than X days)
  - Preview list of captures to be deleted
  - Confirm and delete
  
- **Delete Large Captures**:
  - Specify size (larger than X MB)
  - Preview and confirm
  
- **Free Space Wizard**:
  - Shows current disk usage
  - Suggests captures to delete
  - User selects and confirms

### Automatic Cleanup

**Policies** (optional, disabled by default):
- **Age-Based**: Delete captures older than X days
- **Size-Based**: Delete oldest captures when total exceeds X GB
- **Count-Based**: Keep only last X captures
- Configurable in System Settings
- Warnings before enabling
- Exclusions: Can mark captures as "Keep Always"

**Storage Alerts**:
- Warning when disk space <10% or <1GB
- Critical alert when <5% or <500MB
- Capture stops automatically if disk full
- User notified via web interface

---

## Multiple Captures

### Simultaneous Captures

**Capability**:
- Support multiple active captures simultaneously
- Each on different interface
- Independent configurations
- Independent logs and files

**Limitations**:
- Max simultaneous captures: 4 (configurable, consider CPU/disk I/O)
- Cannot capture same interface twice simultaneously
- System resources (CPU, memory, disk I/O) limit

**Use Cases**:
- Capture on multiple interfaces (eth0, wlan0) at same time
- Compare traffic on different VLANs
- Monitor multiple links simultaneously

### Management

**Active Captures List**:
- All active captures displayed
- Each shows:
  - Interface
  - Duration (running timer)
  - Packet count (updating)
  - File size (updating)
  - Capture rate (pps, Mbps)
  - Actions (View, Stop, Download)
  
**Per-Capture Status**:
- Real-time updates via WebSocket
- CPU usage per capture (if measurable)
- Dropped packets (if any)

**Start Another Capture**:
- "New Capture" button always available
- Validation: Check if max captures reached
- Check if interface already being captured
- Proceed if validations pass

### Resource Management

**CPU Usage**:
- Each capture: tcpdump process
- Monitor CPU usage of all tcpdump processes
- Alert if aggregate CPU >50%
- Consider limiting captures if high CPU

**Disk I/O**:
- Multiple captures = multiple files being written
- Disk I/O can be bottleneck
- Monitor I/O wait
- Optimize: Use fast SD card or USB SSD

**Memory**:
- Each capture: Buffer memory
- Default 2MB buffer per capture
- 4 captures = 8MB buffer total
- Monitor memory usage

---

## Performance Considerations

### Capture Performance

**Packet Loss**:
- Goal: Zero packet loss on gigabit capture (RPi 4/5)
- Monitor: tcpdump reports dropped packets at end
- Causes:
  - CPU overload (capture rate > CPU can handle)
  - Disk I/O bottleneck (write speed < capture rate)
  - Insufficient buffer
- Mitigations:
  - Increase buffer size
  - Use faster storage (SSD)
  - Reduce capture rate (use filters)
  - Close unnecessary processes

**CPU Usage**:
- tcpdump is efficient but CPU-intensive at high rates
- Without filter: 10-30% CPU at 1Gbps (RPi 4)
- With filter: Lower CPU (filtering is efficient)
- Live viewing adds overhead (parsing, WebSocket)

**Disk I/O**:
- Capture rate determines write rate
- Example: 100 Mbps = 12.5 MB/s write
- SD card: ~10-20 MB/s sequential write (Class 10)
- USB 3.0 SSD: ~100+ MB/s write
- Recommendation: Use USB SSD for high-rate captures

**Memory**:
- tcpdump buffer: 2MB default (configurable)
- Larger buffer: Fewer drops, more memory
- System must have free memory for buffers
- Monitor memory usage

### Viewer Performance

**Browser Performance**:
- Rendering 10,000+ rows is slow
- Use virtual scrolling (only render visible)
- Limit packets in memory (10,000 default)
- Lazy-load packet details (parse on demand)

**Parsing Overhead**:
- PCAP binary → JSON conversion is CPU-intensive
- Parse on backend (not browser)
- Cache parsed packets
- Limit parsing rate (throttle updates)

**WebSocket Efficiency**:
- Send packets in batches (not one-by-one)
- Compress data (optional)
- Binary format more efficient than JSON

### Scalability

**Large Captures**:
- Support captures up to 10GB+ (disk permitting)
- Can't load entire capture in browser
- Paginate or stream data
- Use server-side analysis (tshark) for large files

**Long-Duration Captures**:
- Can run for hours or days
- Monitor disk space continuously
- Rotate files if needed (file rotation option)
- Ensure system stability (no memory leaks)

---

## Integration

### API Endpoints

**Capture Management**:
- `GET /api/v1/capture/interfaces` - List available interfaces
- `POST /api/v1/capture/start` - Start new capture
- `GET /api/v1/capture/active` - List active captures
- `GET /api/v1/capture/active/{id}` - Get active capture details
- `POST /api/v1/capture/active/{id}/stop` - Stop capture
- `POST /api/v1/capture/active/{id}/pause` - Pause capture (if supported)
- `POST /api/v1/capture/active/{id}/resume` - Resume capture

**Completed Captures**:
- `GET /api/v1/capture/completed` - List completed captures (with filters)
- `GET /api/v1/capture/completed/{id}` - Get capture details
- `GET /api/v1/capture/completed/{id}/download` - Download PCAP file
- `DELETE /api/v1/capture/completed/{id}` - Delete capture
- `POST /api/v1/capture/completed/export` - Export multiple captures

**Analysis**:
- `GET /api/v1/capture/{id}/stats` - Get capture statistics
- `GET /api/v1/capture/{id}/packets` - Get packets (paginated)
- `GET /api/v1/capture/{id}/conversations` - Get conversations
- `GET /api/v1/capture/{id}/endpoints` - Get endpoints
- `GET /api/v1/capture/{id}/protocols` - Get protocol distribution

**WebSocket**:
- `WS /ws/capture/{id}` - WebSocket for live packet updates

### Web UI Integration

**Simple Mode**:
- "Capture Packets" button on landing page
- Click opens simplified capture dialog:
  - Interface selector
  - Duration (optional)
  - "Start Capture" button
- Capture starts, returns to landing page with notification
- Click notification to view live capture

**Advanced Mode**:
- "Packet Capture" in sidebar navigation
- Dedicated page:
  - New Capture button (prominent)
  - Active Captures section
  - Completed Captures section (with filters)
- Full feature set available

**Capture Viewer**:
- Full-screen modal or dedicated page
- Three-pane layout (list, details, hex)
- Controls toolbar
- Can open multiple viewers (one per capture)

---

## Advanced Features

### Scheduled Captures

**Use Case**: 
- Capture traffic at specific time
- Or recurring captures (e.g., daily at 2am)

**Configuration**:
- Start time: Date and time picker
- Duration: How long to capture
- Recurrence: None, Daily, Weekly (future)
- Interface and filter: Same as manual capture

**Execution**:
- Backend scheduler (cron-like)
- Starts capture at scheduled time
- Stops after duration
- User notified (if online)
- Capture appears in completed list

### Capture Profiles

**Use Case**: 
- Save commonly used capture configurations
- Quickly start captures with saved settings

**Profile Contains**:
- Name and description
- Interface (or "prompt at start")
- Filter
- Duration/size limits
- Advanced options

**Usage**:
- User creates profile from current configuration
- Profiles listed in capture dialog
- User selects profile, overrides if needed
- Quick start capture with one click

### Remote Capture

**Use Case**: 
- Capture on RPi, view in Wireshark on remote computer
- For users who prefer desktop tools

**Implementation**:
- Expose tcpdump via network (pipe over SSH or similar)
- Wireshark on remote computer connects to RPi
- Packets streamed in real-time
- Advanced feature (future enhancement)

### Capture Annotations

**Use Case**: 
- Mark important events during capture
- Add notes at specific times

**Usage**:
- While capture running, user clicks "Add Marker"
- Text annotation saved with timestamp
- Appears in analysis as event marker
- Useful for correlating network activity with user actions

### Decryption

**Use Case**: 
- Capture TLS traffic with session keys
- Decrypt for analysis

**Implementation**:
- Provide TLS session key log (SSLKEYLOGFILE)
- tshark decrypts traffic
- View decrypted application data
- Security warning: Keys must be protected

---

## Error Handling

### Capture Errors

**Cannot Start Capture**:
- **Cause**: Interface down, permission denied, invalid filter
- **Handling**:
  - Display clear error message
  - Suggest solutions (check interface, fix filter syntax)
  - Allow retry

**Capture Interrupted**:
- **Cause**: Interface went down, disk full, process killed
- **Handling**:
  - Detect error (tcpdump exit with error)
  - Mark capture as failed
  - Save partial capture (if any data)
  - Notify user with error details

**Packet Drops**:
- **Cause**: Capture rate too high for system
- **Handling**:
  - tcpdump reports drops at end
  - Display drop count in capture stats
  - Warning if significant drops (>1%)
  - Suggest: Use filter, increase buffer, faster storage

### Storage Errors

**Disk Full**:
- **Cause**: Capture filled all available space
- **Handling**:
  - Detect before starting (check free space)
  - Stop capture if disk fills during capture
  - Notify user immediately
  - Suggest: Delete old captures, expand storage

**Write Error**:
- **Cause**: SD card error, permissions issue
- **Handling**:
  - Capture stops
  - Error logged
  - User notified
  - Check file system, fix permissions

### Viewer Errors

**Cannot Parse Capture**:
- **Cause**: Corrupt PCAP file, unsupported format
- **Handling**:
  - Display error message
  - Attempt to repair (if possible)
  - Offer download for offline analysis

**Large Capture Performance**:
- **Cause**: Capture file too large for browser
- **Handling**:
  - Warn user before opening
  - Load first X packets only
  - Offer server-side analysis instead

---

## Testing and Validation

### Functional Testing

**Capture Operations**:
- Start/stop captures
- Multiple simultaneous captures
- All filter types and combinations
- Duration/size/count limits
- File rotation and ring buffer
- Capture on all interface types

**Live Viewing**:
- Real-time packet updates
- Display filters
- Packet selection and details
- Follow TCP stream
- Search functionality

**Analysis**:
- All statistics accurate
- Protocol detection correct
- Conversations and endpoints
- Export functions

### Performance Testing

**High-Rate Capture**:
- Saturate gigabit link (RPi 4/5)
- Measure packet loss
- Monitor CPU and disk I/O
- Test on RPi 3B+ (lower specs)

**Large Captures**:
- Multi-GB capture files
- Viewer performance
- Analysis speed
- Download speed

**Multiple Captures**:
- 4 simultaneous captures
- Aggregate throughput
- Resource usage
- System stability

### Compatibility Testing

**PCAP File Compatibility**:
- Test with Wireshark (latest version)
- Test with older Wireshark versions
- Test with tcpdump
- Test with tshark

**Filter Compatibility**:
- Validate BPF filters
- Test complex filters
- Edge cases and error handling

---

## Documentation Requirements

### User Documentation

**Getting Started**:
- How to start a basic capture
- Viewing capture in real-time
- Stopping and downloading capture
- Opening capture in Wireshark

**Feature Guides**:
- Using capture filters
- Advanced capture options
- Understanding statistics
- Analyzing conversations
- Following TCP streams
- Troubleshooting common network issues

**Example Scenarios**:
- Troubleshooting connectivity issues
- Analyzing slow application
- Monitoring for specific traffic
- Capturing only HTTP traffic

### Technical Documentation

**Architecture**:
- Capture pipeline
- Live viewer data flow
- Storage format and structure

**Filter Reference**:
- BPF syntax guide
- Common filter examples
- Tips and tricks

**Performance Tuning**:
- Optimizing for high-rate captures
- Reducing resource usage
- Storage considerations

---

## Future Enhancements

### Advanced Analysis

**Deep Packet Inspection**:
- Parse more application protocols
- Extract files from HTTP, FTP, SMB
- Malware detection (pattern matching)

**Machine Learning**:
- Anomaly detection
- Traffic classification
- Baseline normal traffic

### Integration

**External Tools**:
- Export to Wireshark Cloud
- Integration with Zeek (Bro) for analysis
- SIEM integration (send captures or alerts)

**Reporting**:
- Generate PDF reports from analysis
- Scheduled reports (e.g., weekly traffic summary)
- Email reports

### Collaboration

**Multi-User**:
- Share captures with team
- Collaborative analysis
- Comments and annotations

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial packet capture specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- WEB-INTERFACE-SPECIFICATION.md
- NETWORK-MANAGEMENT-SPECIFICATION.md
- API-REFERENCE.md

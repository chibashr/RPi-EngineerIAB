# Network Management Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Network Management Overview](#network-management-overview)
2. [Interface Detection](#interface-detection)
3. [Interface Configuration](#interface-configuration)
4. [Connection Priority and Failover](#connection-priority-and-failover)
5. [WiFi Hotspot Management](#wifi-hotspot-management)
6. [VLAN Configuration](#vlan-configuration)
7. [Routing Management](#routing-management)
8. [Network Profiles](#network-profiles)
9. [Connectivity Testing](#connectivity-testing)
10. [Network Monitoring](#network-monitoring)
11. [Factory Reset](#factory-reset)

---

## Network Management Overview

### Purpose

The Network Management system provides comprehensive control over all network interfaces on the Raspberry Pi, ensuring reliable connectivity for both remote access (WAN) and local network operations (LAN). The system must:

- Automatically detect and configure network interfaces
- Provide intelligent failover between WAN connections
- Maintain always-on WiFi hotspot for local access
- Support advanced features (VLANs, static routes) in Advanced mode
- Allow saving and loading of network configurations
- Ensure system remains accessible even during network changes

### Network Topology

```
                    ┌─────────────────────────────────┐
                    │     Raspberry Pi Device         │
                    │                                 │
                    │  ┌──────────────────────────┐  │
  Internet          │  │  usb0 (USB Jetpack)     │  │
  (Cellular) ◄──────┼──┤  Priority: 1            │  │
                    │  │  Metric: 100            │  │
                    │  │  Role: WAN (Primary)    │  │
                    │  └──────────────────────────┘  │
                    │                                 │
                    │  ┌──────────────────────────┐  │
  Internet/LAN      │  │  eth0 (Ethernet)        │  │
  (Wired)    ◄──────┼──┤  Priority: 2            │  │
                    │  │  Metric: 200            │  │
                    │  │  Role: WAN or LAN       │  │
                    │  │  VLAN: Capable          │  │
                    │  └──────────────────────────┘  │
                    │                                 │
                    │  ┌──────────────────────────┐  │
  Mobile Devices    │  │  wlan0 (WiFi Hotspot)   │  │
  (Local Access) ◄──┼──┤  Always On              │  │
                    │  │  192.168.50.0/24        │  │
                    │  │  Role: LAN (Hotspot)    │  │
                    │  └──────────────────────────┘  │
                    │                                 │
                    └─────────────────────────────────┘
```

### Network Roles

**WAN (Wide Area Network)**:
- Purpose: Internet connectivity for remote access and updates
- Interfaces: usb0/usb1 (USB jetpack), eth0 (optional)
- Priority: USB first, then Ethernet
- DHCP client mode typical

**LAN (Local Area Network)**:
- Purpose: Connection to local network devices for diagnostics
- Interfaces: eth0 (typical), VLANs on eth0
- Configuration: DHCP or Static as needed
- May bridge to specific network segments

**Hotspot**:
- Purpose: Local wireless access for mobile devices
- Interface: wlan0 (dedicated)
- Configuration: Always static (192.168.50.1/24)
- Always active regardless of other network states

### Design Principles

1. **Resilience**: Network changes never make system inaccessible
2. **Automatic**: Minimal manual intervention required
3. **Transparent**: Clear indication of network status and changes
4. **Safe**: Configuration changes require confirmation
5. **Recoverable**: Factory reset available if misconfigured

---

## Interface Detection

### Automatic Detection

**On System Boot**:
1. System enumerates all network interfaces
2. Identifies interface types (USB, Ethernet, WiFi)
3. Reads current configuration from system
4. Tests connectivity on potential WAN interfaces
5. Establishes routing priority
6. Starts all configured services

**On USB Device Hotplug**:
1. udev event triggers detection
2. New USB network interface identified
3. Interface brought up with DHCP
4. Connectivity tested
5. If successful and higher priority, becomes default route
6. Previous WAN interface becomes backup

### Interface Types

#### USB Network Interfaces (usb0, usb1, etc.)

**Detection Criteria**:
- Interface name matches usb* pattern
- USB device with network class
- Typically CDC NCM or RNDIS device

**Common Devices**:
- Verizon Jetpack
- AT&T cellular modems
- T-Mobile hotspots
- USB tethered phones

**Configuration**:
- Default: DHCP client
- Automatic MTU detection
- DNS from DHCP preferred

**Priority**: Highest (metric 100)

#### Ethernet Interface (eth0)

**Detection Criteria**:
- Interface name: eth0
- Hardware type: Ethernet

**Capabilities**:
- Support for VLANs (802.1Q)
- Jumbo frames (if supported by network)
- Link speed auto-negotiation
- Full duplex operation

**Configuration**:
- Default: DHCP client
- Can be configured as Static
- VLAN subinterfaces (eth0.10, eth0.20, etc.)

**Roles**:
- WAN (secondary priority, metric 200)
- LAN (for local network diagnostics)
- Both (with policy routing)

#### WiFi Interface (wlan0)

**Detection Criteria**:
- Interface name: wlan0
- Wireless device

**Mode**: Access Point (AP) only
- Station mode not used
- Always operates as hotspot

**Configuration**:
- Static IP: 192.168.50.1/24
- DHCP server for clients
- DNS forwarder
- NAT to WAN interface

**Priority**: Not in WAN routing (dedicated local access)

### Interface Naming

**Consistent Naming**:
- Use predictable network interface names
- systemd-networkd naming scheme
- Fallback to traditional names if needed

**Display Names**:
- Technical: eth0, usb0, wlan0
- Friendly: "Ethernet", "USB Jetpack", "WiFi Hotspot"
- Both displayed in Advanced mode
- Friendly only in Simple mode

### Hardware Information

**Collected for Each Interface**:
- MAC address
- Driver name
- Device vendor and model
- Link status (up/down)
- Link speed and duplex (Ethernet)
- Signal strength (WiFi AP)
- MTU
- Hardware capabilities

---

## Interface Configuration

### Configuration Methods

**DHCP Client**:
- Automatic IP address assignment
- Receive gateway and DNS from server
- Default for most interfaces
- Lease renewal automatic
- Fallback to link-local if DHCP fails

**Static IP**:
- Manual IP address configuration
- User specifies IP, netmask, gateway
- Manual DNS configuration
- Used for fixed network requirements

**Access Point** (wlan0 only):
- Static IP for AP interface
- DHCP server for connected clients
- Fixed configuration

### Configuration Parameters

#### IPv4 Configuration

**For DHCP Mode**:
- Enable/disable DHCP client
- DHCP client ID (optional)
- Hostname to send in DHCP request
- Request specific IP (optional)

**For Static Mode**:
- IP Address (e.g., 192.168.1.100)
- Subnet Mask or CIDR (e.g., 255.255.255.0 or /24)
- Gateway IP (optional)
- Primary DNS server
- Secondary DNS server (optional)

**Advanced Settings**:
- MTU (default 1500, customizable)
- Metric (routing priority)
- Custom routing table
- Policy routing rules

#### IPv6 Configuration

**Support Level**: Basic support, not primary focus

**Configuration**:
- Enable/disable IPv6
- SLAAC (automatic)
- Static IPv6 address
- IPv6 gateway and DNS

**Default**: Disabled initially, can be enabled

### Configuration Interface

#### Simple Mode

**Not Available**: Network configuration not exposed in Simple mode
- Prevents accidental misconfiguration
- Default configuration sufficient for most cases
- Switch to Advanced mode required

#### Advanced Mode

**Interface Configuration Page**:

**Per-Interface Settings**:
- Connection mode (DHCP/Static)
- IP address configuration
- Gateway and DNS settings
- MTU and metric
- Enable/disable interface

**Configuration Modal**:
- Form-based input
- Real-time validation
- Field constraints enforced
- Preview changes before apply
- Confirm/cancel buttons

**Validation Rules**:
- IP addresses in valid format
- Subnet mask appropriate for IP
- Gateway in same subnet
- No IP conflicts between interfaces
- DNS servers reachable

### Configuration Application

**Apply Process**:
1. User submits configuration changes
2. Validation performed
3. Preview of changes shown
4. User confirms changes
5. System applies configuration:
   - Updates system network files
   - Restarts network service for interface
   - Tests connectivity
   - Updates routing if needed
6. Success or error reported
7. Configuration saved

**Rollback on Failure**:
- If connectivity test fails after change
- Automatic rollback after 60 seconds
- User can confirm changes to prevent rollback
- "Are you still there?" prompt in web interface

**No Downtime**:
- Other interfaces remain operational
- Web interface accessible via hotspot
- Phased application of changes

---

## Connection Priority and Failover

### Priority System

**Routing Metrics**:
- Lower metric = higher priority
- Default route uses lowest metric interface

**Priority Order**:
1. **USB Interfaces** (usb0, usb1): Metric 100
2. **Ethernet WAN** (eth0 when in WAN role): Metric 200
3. **No Default Route**: No WAN connectivity

**WiFi Hotspot** (wlan0): Not in WAN routing, local only

### Connectivity Testing

**Test Procedure**:
1. **ICMP Ping Test**: ping -c 3 8.8.8.8
   - Success: 1+ replies received
   - Failure: 0 replies or timeout
2. **DNS Resolution Test**: nslookup google.com
   - Success: IP address returned
   - Failure: Resolution timeout or error
3. **Both Must Pass**: For interface considered "connected"

**Test Frequency**:
- On interface state change (up/down)
- Every 60 seconds for active WAN interface
- On user-requested test
- After configuration change

**Test Timeout**: 10 seconds total

### Failover Mechanism

**Automatic Failover Sequence**:

```
Primary WAN Active (usb0)
         │
         ▼
┌─────────────────────┐
│ Connectivity Test   │
│ Failed (3 attempts) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Mark Interface      │
│ as Degraded         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Test Secondary WAN  │
│ (eth0)              │
└──────────┬──────────┘
           │
      ┌────┴────┐
      │ Success?│
      └────┬────┘
      Yes  │  No
      │    │
      │    ▼
      │  ┌─────────────────────┐
      │  │ Alert: No WAN       │
      │  │ Keep trying both    │
      │  └─────────────────────┘
      │
      ▼
┌─────────────────────┐
│ Switch Default      │
│ Route to eth0       │
│ (metric 200)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Notify Services     │
│ - Update Manager    │
│ - Remote Access     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Continue Testing    │
│ Primary (usb0)      │
│ Every 60 seconds    │
└──────────┬──────────┘
           │
           ▼
    (If recovers)
┌─────────────────────┐
│ Switch Back to      │
│ Primary (usb0)      │
└─────────────────────┘
```

**Failback Behavior**:
- Primary interface recovery detected
- Wait 2 minutes to ensure stability
- Switch back to primary
- Notification sent

**Hysteresis**:
- Prevent rapid switching (flapping)
- 3 consecutive test failures before failover
- 5 consecutive test successes before failback
- Minimum 2 minutes between switches

### Status Reporting

**WAN Status Displayed**:
- Active WAN interface (usb0, eth0, or none)
- Connection status (Connected, Degraded, Failed)
- Last successful test time
- Next test scheduled time
- Failover history (last 10 events)

**Notifications**:
- WAN connection lost
- Failover occurred
- Failback occurred
- Persistent connection failure

---

## WiFi Hotspot Management

### Hotspot Configuration

**SSID**:
- Format: `RPi-Engineer-[last4MAC]`
- Example: `RPi-Engineer-A1B2`
- Configurable during installation
- Changeable in Advanced mode

**Security**:
- Mode: WPA2-PSK (preferred) or WPA3-PSK (if supported)
- Password: 8-63 characters
- Set during installation
- Changeable in Advanced mode
- Not displayed by default (show/hide toggle)

**Radio Configuration**:
- Band: 2.4 GHz (default), 5 GHz if supported and configured
- Channel: Auto-select (default), manual selection available
- Transmit power: Default (configurable for range adjustment)
- Hidden SSID: Option to hide (not recommended)

**IP Configuration**:
- IP Address: 192.168.50.1/24 (fixed)
- DHCP Range: 192.168.50.10 - 192.168.50.100
- Lease Time: 24 hours
- DNS Server: Self (192.168.50.1)

### DHCP Server

**Configuration**:
- Range: Configurable within subnet
- Default range: .10 to .100
- Lease time: Configurable (default 24h)
- Maximum clients: Configurable (default 50)

**DHCP Options**:
- Gateway: 192.168.50.1
- DNS: 192.168.50.1
- Domain: local
- NTP: System time

**Static DHCP Leases** (Future):
- Reserve IP for specific MAC
- Managed via web interface

### DNS Forwarding

**Function**: DNS requests from hotspot clients forwarded to WAN DNS

**Implementation**:
- dnsmasq DNS forwarder
- Cache DNS results (1000 entries)
- Forward to WAN interface DNS servers
- Fallback to 8.8.8.8 if no WAN DNS

**Local Resolution**:
- rpi-engineer.local → 192.168.50.1
- *.local → mDNS resolution

### NAT Configuration

**Masquerading**: Traffic from hotspot clients NATed to WAN

**iptables Rules**:
- MASQUERADE from 192.168.50.0/24 to WAN interface
- Allow established and related connections
- Allow new connections from LAN to WAN
- Block new connections from WAN to LAN

**Port Forwarding** (Future):
- Expose services to hotspot clients
- UPnP support (optional)

### Client Management

**Connected Clients**:
- View list of connected clients
- Display: IP, MAC, hostname, connection time
- Signal strength (if available)
- Bandwidth usage (if available)

**Client Control**:
- Disconnect client
- Block MAC address (blacklist)
- Bandwidth limiting per client (future)

### Hotspot Control

**Always-On Policy**: Hotspot should never be disabled

**Restart Hotspot**:
- Available in Advanced mode
- Disconnects all clients
- Applies new configuration
- Automatically restarts

**Troubleshooting**:
- Test hostapd configuration
- View hostapd logs
- Check WiFi driver status
- Channel survey (interference check)

---

## VLAN Configuration

### VLAN Support

**Availability**: Advanced mode only

**Interface**: eth0 only (primary Ethernet)

**Standard**: IEEE 802.1Q

**Use Cases**:
- Connect to multiple network segments
- Isolate traffic by VLAN
- Access management VLAN
- Trunk port configuration

### VLAN Interface Creation

**VLAN Interface Naming**:
- Format: `eth0.[VLAN_ID]`
- Example: `eth0.10`, `eth0.100`, `eth0.4094`

**VLAN ID Range**: 1-4094

**Configuration Per VLAN**:
- VLAN ID (required)
- VLAN name/description
- IP configuration (DHCP or Static)
- Gateway (if different from parent)
- DNS servers
- Metric (routing priority)

### VLAN Configuration Process

**Create VLAN**:
1. Navigate to Network → Interfaces → Add VLAN
2. Select parent interface (eth0)
3. Enter VLAN ID (validate uniqueness)
4. Enter description
5. Configure IP settings
6. Preview configuration
7. Confirm and apply
8. VLAN interface created and brought up

**Modify VLAN**:
- Change IP configuration only
- VLAN ID immutable (delete and recreate)

**Delete VLAN**:
- Confirmation required
- Interface brought down
- Configuration removed
- Check for routing dependencies

### VLAN Tagging

**Native VLAN**:
- Parent interface (eth0) can have untagged traffic
- Configured separately from VLAN interfaces
- Typically not used (all traffic tagged)

**Tagged Traffic**:
- All VLAN interfaces send tagged packets
- 802.1Q header added by kernel
- Switch must be configured for trunking

**VLAN Priority**: 802.1p QoS bits (future support)

### VLAN Limitations

**Hardware**:
- Raspberry Pi Ethernet supports VLANs
- USB Ethernet adapters may not support VLANs
- WiFi interface cannot have VLANs

**Performance**:
- Multiple VLANs increase CPU usage
- Each VLAN adds routing overhead
- Monitor system performance

**Network Switch**:
- Switch must support 802.1Q
- Port must be configured as trunk
- Native VLAN should match (if used)

---

## Routing Management

### Routing Tables

**Main Routing Table**:
- Default route to WAN interface (lowest metric)
- Local network routes (directly connected)
- Static routes (user-configured)

**Interface Routes**:
- Automatically added for each interface
- Network/subnet derived from IP and netmask
- Examples:
  - 192.168.50.0/24 dev wlan0
  - 10.20.30.0/24 dev usb0
  - 192.168.1.0/24 dev eth0

**Default Route**:
- Points to WAN gateway
- Lowest metric interface selected
- Updated on failover

### Static Routes

**Purpose**:
- Route specific networks via specific gateways
- Override default routing
- Support complex network topologies

**Configuration**:
- Destination network (CIDR notation)
- Gateway IP address
- Interface (optional, auto-selected if omitted)
- Metric (priority)

**Use Cases**:
- Access specific subnet via LAN gateway
- Split tunneling (some traffic via specific interface)
- Multi-homed routing

**Management**:
- Add static route
- View all routes
- Delete static route
- Validate routes (no conflicts)

### Policy Routing

**Use Case**: Route traffic based on source or other criteria

**Implementation** (Future):
- Multiple routing tables
- Rules to select routing table
- Mark packets for routing

**Example Scenarios**:
- All traffic from specific IP via specific gateway
- Localhost traffic via specific interface

---

## Network Profiles

### Purpose

**Save Network Configurations**:
- Store complete network configuration
- Quickly apply configuration for specific sites
- Backup configuration before changes
- Share configuration between devices

### Profile Contents

**Included in Profile**:
- All interface configurations (IP, gateway, DNS)
- Static routes
- VLAN configurations
- WiFi hotspot settings (optional)
- Metric and priority settings

**Excluded from Profile**:
- Remote access credentials
- System-specific settings (hostname)
- Temporary state information

### Profile Management

**Create Profile**:
1. Navigate to Network → Profiles → Save Current
2. Enter profile name
3. Optionally include hotspot password
4. Profile saved

**Load Profile**:
1. Navigate to Network → Profiles
2. Select profile from list
3. Preview changes (diff current vs profile)
4. Confirm application
5. Configuration applied
6. Network services restarted as needed

**Export Profile**:
- Download as JSON file
- Transfer to other devices
- Backup externally

**Import Profile**:
- Upload JSON file
- Validate format
- Add to profile list

**Delete Profile**:
- Confirmation required
- Profile removed from list

### Profile Storage

**Location**: `/etc/rpi-engineer/network_profiles/`

**Format**: JSON

**Example Structure**:
- Profile metadata (name, date created, description)
- Interface configurations (array)
- Routing configuration
- VLAN configuration

**Naming Convention**: `profile_name.json`

---

## Connectivity Testing

### Manual Testing

**Test Interface**:
- Button available per interface in Advanced mode
- Runs standard connectivity test (ping + DNS)
- Reports result immediately
- Updates interface status

**Test WAN**:
- Tests current default route
- Reports overall WAN connectivity
- Provides details on which tests passed/failed

### Automated Testing

**Schedule**:
- WAN interfaces tested every 60 seconds
- Triggers failover if failures occur
- Automatic recovery when connection restored

**Test Logging**:
- All test results logged
- Available in logs viewer
- Includes timestamp, interface, result, latency

### Connectivity Indicators

**Visual Status**:
- Green dot: Connected, tests passing
- Yellow dot: Degraded, intermittent failures
- Red dot: Failed, no connectivity
- Gray dot: Interface down or disabled

**Detailed Status**:
- Last test time
- Last success time
- Failure count
- Average latency

---

## Network Monitoring

### Real-Time Statistics

**Per-Interface Metrics**:
- RX bytes, packets
- TX bytes, packets
- Errors, dropped packets
- Current throughput (bps)

**Update Frequency**: Every 5 seconds

**Display**:
- Simple mode: Not displayed
- Advanced mode: Per-interface cards and graphs

### Historical Data

**Metrics Stored**:
- Throughput over time
- Error counts
- Connection uptime
- Failover events

**Retention**: 7 days (configurable)

**Visualization**:
- Line graphs for throughput
- Bar charts for errors
- Event timeline for failovers

### Alerts

**Conditions**:
- Interface down
- WAN connectivity lost
- Excessive errors on interface
- Failover occurred
- DHCP lease lost

**Display**:
- Web interface banner
- Dashboard alerts section
- Log entries

---

## Factory Reset

### Purpose

Reset network configuration to installation defaults

### Reset Scope

**Network Settings Reset**:
- All interface configurations to DHCP (except wlan0)
- WiFi hotspot configuration preserved
- All static routes removed
- All VLANs removed
- All saved profiles removed
- Routing metrics to defaults

**Preserved**:
- WiFi hotspot SSID and password
- Hostname
- Remote access configuration
- Other system settings

### Reset Process

**Trigger**: Advanced mode → Network → Factory Reset

**Confirmation**:
1. Warning dialog displayed
2. Checkbox: "I understand this will reset network settings"
3. Confirm button enabled after checkbox
4. User confirms
5. Reset executed

**Execution**:
1. Stop network services
2. Delete custom configuration files
3. Restore default configuration
4. Restart network services
5. Re-test WAN connectivity
6. Display result

**Result**:
- Success message with current status
- Automatic redirect to dashboard
- User may need to reconnect if on Ethernet

### Emergency Reset

**If Web Interface Inaccessible**:
- Physical button press (if hardware supports)
- Serial console command
- Documented manual procedure

---

## Error Handling

### Common Error Scenarios

**IP Address Conflict**:
- Detection: ARP probe before applying
- Resolution: Alert user, suggest different IP

**Invalid Gateway**:
- Detection: Gateway not in same subnet
- Resolution: Validation error, block save

**DNS Resolution Failure**:
- Detection: Test DNS after configuration
- Resolution: Warning, allow to proceed

**DHCP Failure**:
- Detection: No IP obtained after 30 seconds
- Resolution: Fallback to link-local, alert user

**Interface Down**:
- Detection: Link status check
- Resolution: Alert user, check cable

### Configuration Rollback

**Automatic Rollback**:
- After 60 seconds if user doesn't confirm
- If connectivity test fails critically
- User can extend timer if needed

**Manual Rollback**:
- Undo last change button
- Restore from profile
- Factory reset

---

## Performance Considerations

### Throughput

**Expected Performance**:
- Raspberry Pi 4/5: Near line-rate Gigabit (900+ Mbps)
- Raspberry Pi 3B+: ~300 Mbps (USB 2.0 limited)

**Optimization**:
- Enable hardware offload where supported
- Minimize iptables rules
- Use efficient routing

### CPU Usage

**Network Services**:
- Keep CPU usage under 10% during normal operation
- Monitor during high throughput
- Throttle if CPU overloaded

### Latency

**Target Latency**:
- Configuration changes: Apply within 5 seconds
- Failover: Complete within 30 seconds
- Interface status updates: Within 1 second

---

## Security Considerations

### Firewall Rules

**Default Policy**:
- Allow outbound traffic
- Block inbound traffic on WAN
- Allow inbound on hotspot (limited)

**Protected Services**:
- Web interface: Accessible only on hotspot and LAN
- SSH: Disabled by default on WAN
- Serial console: Local only

### WiFi Security

**Encryption**:
- WPA2-PSK minimum
- WPA3-PSK if hardware supports
- Strong password required (8+ chars)

**Client Isolation** (Future):
- Prevent clients from seeing each other
- Security enhancement

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial network management specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- WEB-INTERFACE-SPECIFICATION.md
- SECURITY-SPECIFICATION.md
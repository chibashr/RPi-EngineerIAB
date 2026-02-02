# Deployment Guide

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Configuration Export and Import](#configuration-export-and-import)
4. [Site Deployment Procedures](#site-deployment-procedures)
5. [On-Site Reconfiguration](#on-site-reconfiguration)
6. [Common Deployment Scenarios](#common-deployment-scenarios)
7. [Troubleshooting at Deployment](#troubleshooting-at-deployment)
8. [Post-Deployment Verification](#post-deployment-verification)

---

## Overview

### Purpose

This guide provides procedures for preparing, deploying, and verifying RPi Engineer-in-a-Box devices at customer sites. It covers pre-deployment preparation, on-site procedures, and post-deployment validation.

### Audience

- Field technicians deploying devices
- Network engineers preparing devices for remote use
- IT staff managing device fleet

### Related Documents

- INSTALLATION-SPECIFICATION.md - Initial installation
- NETWORK-MANAGEMENT-SPECIFICATION.md - Network configuration
- UPDATE-MAINTENANCE-SPECIFICATION.md - Backup and restore

---

## Pre-Deployment Checklist

### Hardware Preparation

**Required**:
- [ ] Raspberry Pi (3B+, 4, or 5) with power supply
- [ ] MicroSD card (32GB minimum, Class 10 or better)
- [ ] USB cellular modem (jetpack) for mobile connectivity
- [ ] USB-to-serial adapter(s) for console access
- [ ] Ethernet cable
- [ ] Optional: HDMI display for status
- [ ] Optional: USB battery pack for portable use

**Verify**:
- [ ] All components tested and functional
- [ ] Serial adapters compatible (FTDI, Prolific, or CH340)
- [ ] Sufficient storage for captures and logs

### Software Preparation

**Installation**:
- [ ] Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+) installed on SD card
- [ ] RPi Engineer-in-a-Box installed via install script
- [ ] Installation completed successfully
- [ ] All services running
- [ ] Web interface accessible

**Configuration**:
- [ ] Hostname set (if site-specific)
- [ ] Remote access tool configured (AnyDesk, TeamViewer, VNC, or Raspberry Pi Connect)
- [ ] WiFi hotspot password set (strong, unique)
- [ ] Network profile saved (if site has known config)

### Pre-Deployment Testing

**Connectivity**:
- [ ] USB jetpack obtains IP and has internet
- [ ] Ethernet works when connected
- [ ] WiFi hotspot allows client connection
- [ ] Web interface loads from hotspot client

**Features**:
- [ ] Serial console detects USB adapter
- [ ] Packet capture starts and stops
- [ ] Remote access tool shows connection ID
- [ ] Update check works (if WAN available)

### Documentation and Credentials

**Prepare**:
- [ ] Site-specific instructions (if any)
- [ ] Contact information for remote engineer
- [ ] WiFi credentials card/label (for on-site reference)
- [ ] Remote access credentials (if different from install)
- [ ] Backup of configuration (export)

### Packing

**For Transport**:
- [ ] Device and cables in protective case
- [ ] Power supply and adapters
- [ ] Printed quick-start sheet (optional)
- [ ] Serial cables for target equipment

---

## Configuration Export and Import

### Exporting Configuration

**Purpose**: Transfer configuration to another device or backup before changes

**Steps**:
1. Access web interface (Advanced mode)
2. Navigate to Settings → Backup
3. Click "Export Configuration"
4. Save JSON file to secure location
5. Note: Passwords may need to be re-entered on import

**What Is Exported**:
- System configuration
- Network profiles
- Module configurations
- Excludes: Remote access passwords (security)

**What Is Not Exported**:
- Packet captures
- Serial logs
- Runtime state

### Importing Configuration

**Purpose**: Apply configuration to new or reset device

**Steps**:
1. Access web interface on target device
2. Navigate to Settings → Backup
3. Click "Import Configuration"
4. Select exported JSON file
5. Review preview of changes
6. Confirm import
7. Re-enter any passwords not in export
8. Restart affected services if prompted

**Compatibility**:
- Same version: Full compatibility
- Different minor version: Usually compatible, test
- Different major version: May require migration

### Network Profile Transfer

**For Site-Specific Network**:
1. Configure network on reference device at site (or lab)
2. Save as network profile (Settings → Network → Profiles)
3. Export profile or full configuration
4. Import on deployment device
5. Profile available for quick apply at site

---

## Site Deployment Procedures

### Standard Deployment Sequence

**1. Physical Setup** (5-10 minutes):
1. Place device in secure, accessible location
2. Connect power (outlet or battery pack)
3. Connect USB cellular modem (jetpack)
4. Connect Ethernet to local network (if available)
5. Connect serial cables to target equipment
6. Connect display (if using)
7. Power on device

**2. Boot and Connect** (2-5 minutes):
1. Wait for boot (~2 minutes)
2. Connect to WiFi hotspot from phone/laptop
   - SSID: RPi-Engineer-XXXX (last 4 of MAC)
   - Password: [from preparation]
3. Open browser to http://192.168.50.1
4. Verify web interface loads

**3. Network Verification** (2-5 minutes):
1. Check WAN status on dashboard
2. Verify internet connectivity (USB jetpack or Ethernet)
3. If Ethernet used: Verify correct network profile if pre-configured
4. Test remote access: Note connection ID, verify from engineer workstation

**4. Feature Verification** (5-10 minutes):
1. Serial Console: Verify devices detected, open test session
2. Packet Capture: Start brief capture on appropriate interface
3. Remote Access: Engineer connects, verifies full access
4. Document any issues for follow-up

**5. Handoff**:
1. Provide WiFi credentials to on-site personnel (if needed)
2. Provide remote access connection ID to engineer
3. Confirm engineer has access
4. Document deployment completion

### Quick Deployment (Minimal)

**When Time Is Limited**:
1. Power, USB modem, Ethernet, serial - connect all
2. Boot, connect to hotspot
3. Verify web interface and WAN
4. Share connection ID with engineer
5. Engineer verifies remote access
6. Detailed verification can be done remotely

---

## On-Site Reconfiguration

### When Reconfiguration Is Needed

- Site network different from expected
- VLAN requirements discovered on-site
- Different serial devices than planned
- WiFi interference requires channel change

### Network Reconfiguration

**Steps**:
1. Connect to web interface (via hotspot - always available)
2. Navigate to Advanced → Network
3. Modify interface configuration as needed
4. Apply changes (with confirmation)
5. Verify connectivity after change
6. Save as network profile for this site (optional)

**Rollback**: If change causes loss of access, wait 60 seconds for automatic rollback, or use factory reset if necessary.

### Adding Serial Devices

**Hot-Plug**:
1. Connect USB-to-serial adapter
2. Wait 10-30 seconds for detection
3. Refresh Serial Console page if needed
4. Device appears in list
5. Configure baud rate if not default (9600)

### Changing Remote Access Tool

**Requires**:
- May need to run installation script again with different selection
- Or: Manual install of alternate tool, configure
- Document in INSTALLATION-SPECIFICATION for manual tool install

---

## Common Deployment Scenarios

### Scenario 1: Remote Site, Cellular Only

**Setup**:
- USB jetpack for WAN
- No Ethernet
- Serial to network devices
- Engineer connects remotely via AnyDesk

**Procedure**:
1. Power, jetpack, serial - connect
2. Boot, ensure jetpack gets cellular signal
3. Connect to hotspot, verify WAN shows connected
4. Engineer uses connection ID to connect
5. All access via remote desktop

**Considerations**: Cellular signal strength, data usage for remote desktop

### Scenario 2: Site with Ethernet, Local and Remote Access

**Setup**:
- Ethernet to site network (WAN or LAN)
- USB jetpack as backup WAN
- Serial and packet capture on Ethernet
- Both on-site and remote users

**Procedure**:
1. Connect Ethernet to correct port/VLAN
2. Apply network profile if pre-configured
3. Verify routing (WAN via Ethernet or jetpack)
4. On-site: Connect to hotspot for web access
5. Remote: Connect via remote access tool
6. Packet capture on eth0 for local traffic

### Scenario 3: Multiple Devices, Same Site

**Setup**:
- Several RPi devices for different network segments
- Each with serial to different equipment
- Shared configuration base

**Procedure**:
1. Prepare first device with base configuration
2. Export configuration
3. Install and import on subsequent devices
4. Customize hostname per device
5. Customize network (VLAN, IP) per segment
6. Deploy each at designated location

### Scenario 4: Pre-Configured for Specific Customer

**Setup**:
- Device configured in lab with customer network details
- Network profile saved
- Remote access pre-configured
- Ready for plug-and-play at site

**Procedure**:
1. Complete pre-deployment checklist in lab
2. Export full configuration (backup)
3. At site: Physical connect only
4. Boot, connect to hotspot
5. Apply network profile (one click)
6. Verify - minimal on-site configuration

---

## Troubleshooting at Deployment

### Cannot Connect to Hotspot

**Check**:
- Device powered and booted (wait 3 minutes)
- Correct SSID (RPi-Engineer-XXXX)
- Correct password
- WiFi enabled on client device

**Try**: Power cycle device, wait for full boot

### No WAN Connectivity

**USB Jetpack**:
- Jetpack powered and has signal
- USB cable firmly connected
- Jetpack may need activation/subscription

**Ethernet**:
- Cable connected, link light on
- Correct VLAN if applicable
- DHCP available on network
- Try different port on switch

### Web Interface Not Loading

**Check**:
- Connected to correct hotspot (192.168.50.x)
- URL: http://192.168.50.1 (not https)
- Try different browser
- Clear cache

**Verify**: Ping 192.168.50.1 from client

### Serial Devices Not Detected

**Check**:
- USB adapter firmly connected
- Adapter compatible (FTDI, Prolific, CH340)
- Wait 30 seconds after connect
- Refresh Serial Console page
- Try different USB port

### Remote Access Connection Fails

**Check**:
- WAN connectivity on device
- Correct connection ID
- Correct password
- Remote access service running (see web interface status)
- Firewall on engineer network allowing outbound

### Slow or Unresponsive

**Check**:
- Adequate power supply (5V 3A for RPi 4)
- SD card quality (use Class 10 or better)
- Temperature (ensure ventilation)
- Close unnecessary browser tabs

---

## Post-Deployment Verification

### Verification Checklist

**Connectivity**:
- [ ] Web interface accessible from hotspot
- [ ] WAN shows connected (if internet available)
- [ ] Remote engineer can connect

**Features**:
- [ ] Serial console opens for each connected device
- [ ] Packet capture can be started
- [ ] Remote desktop session functional

**Stability**:
- [ ] Device runs 15+ minutes without issue
- [ ] No unexpected service restarts
- [ ] Logs show no critical errors

### Documentation

**Record**:
- Deployment date and site
- Device hostname and/or identifier
- Network configuration applied
- Serial devices connected
- Any issues and resolutions
- Contact for remote engineer

### Handoff to Remote Engineer

**Provide**:
- WiFi hotspot credentials (SSID, password)
- Web interface URL (http://192.168.50.1)
- Remote access connection ID and password
- Any site-specific notes

**Confirm**:
- Engineer has successfully connected
- Engineer can access serial consoles
- Engineer can perform packet capture
- No blocking issues

### Follow-Up

**Within 24 Hours**:
- Remote engineer confirms ongoing access
- Address any issues discovered
- Update configuration if needed

**Ongoing**:
- Monitor for alerts (if monitoring configured)
- Plan for updates per maintenance schedule
- Collect feedback for process improvement

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial deployment guide |

## Related Documents
- INSTALLATION-SPECIFICATION.md
- NETWORK-MANAGEMENT-SPECIFICATION.md
- UPDATE-MAINTENANCE-SPECIFICATION.md
- REMOTE-ACCESS-SPECIFICATION.md
- DOCUMENTATION-GUIDELINES.md

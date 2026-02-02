# Security Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Threat Model and Assumptions](#threat-model-and-assumptions)
3. [Network Security](#network-security)
4. [Application Security](#application-security)
5. [Service Privilege Separation](#service-privilege-separation)
6. [Remote Access Security](#remote-access-security)
7. [Update Security](#update-security)
8. [Data Protection](#data-protection)
9. [Security Best Practices for Users](#security-best-practices-for-users)
10. [Future Security Enhancements](#future-security-enhancements)

---

## Overview

### Purpose

This specification defines the security model, threat assumptions, and security measures for the RPi Engineer-in-a-Box platform. The design balances security with the primary use case: a portable field diagnostic tool where ease of access and simplicity are prioritized.

### Security Posture

**Design Philosophy**:
- **Defense in Depth**: Multiple layers of protection
- **Principle of Least Privilege**: Minimal permissions for each component
- **Secure by Default**: Safe defaults, opt-in for risky features
- **Transparency**: Security assumptions and limitations documented

**Explicit Non-Goals** (per PROJECT-OVERVIEW):
- No authentication required for web interface (simplified field use)
- WiFi hotspot is primary access method (assumed private network)
- Physical security assumed (device in controlled environment)

### Scope

This document covers:
- Network and firewall security
- Application input validation and injection prevention
- Service isolation and privileges
- Remote access tool security
- Update integrity
- User guidance for secure deployment

---

## Threat Model and Assumptions

### Trust Assumptions

**We Assume**:
- Device is deployed in physically controlled or semi-controlled environment
- Users connecting to hotspot are authorized (technicians, engineers)
- Remote access users are trusted (organization members)
- Raspberry Pi hardware and Debian-based OS (Ubuntu/Raspberry Pi OS) base are trusted
- Git repository for updates is trusted
- No persistent adversary with sophisticated capabilities

**We Do NOT Assume**:
- Network is trusted (WAN may be hostile)
- All hotspot users are trusted (use strong WiFi password)
- Physical security is guaranteed (device may be left unattended)
- Updates are always safe (verify source)

### Threat Actors

**Tier 1 - Opportunistic**:
- Unauthorized WiFi connection attempt
- Casual network scanning
- Default credential exploitation

**Mitigation**: Strong WiFi password, no default credentials, firewall

**Tier 2 - Network Attacker**:
- Man-in-the-middle on WAN
- Malicious DNS
- Exploitation of exposed services

**Mitigation**: Firewall blocks WAN inbound, use HTTPS for updates, validate sources

**Tier 3 - Physical Access**:
- Theft of device
- Serial console access to connected equipment
- USB device tampering

**Mitigation**: Physical security, user awareness, optional disk encryption (future)

### Assets to Protect

**High Value**:
- Serial console logs (may contain device credentials)
- Packet captures (network traffic)
- Configuration (network profiles, settings)
- Access to connected network equipment

**Medium Value**:
- Remote access session (full system control)
- Web interface (configuration changes)

**Lower Value**:
- System metrics, logs (operational data)

---

## Network Security

### Firewall Rules

**Default Policy** (iptables/nftables):
- **INPUT**: Deny by default, allow specific
- **FORWARD**: Allow hotspot→WAN, deny WAN→LAN
- **OUTPUT**: Allow (for outbound connectivity)

**Allowed Inbound**:
- Hotspot interface (wlan0): HTTP (80), HTTPS (443 if enabled) from 192.168.50.0/24
- LAN interface (eth0): Same, from configured LAN subnet
- Loopback: All (local services)

**Blocked Inbound**:
- WAN interfaces (usb0, eth0 when WAN): All inbound
- SSH from WAN: Disabled by default
- All other unsolicited inbound

**NAT**:
- MASQUERADE for hotspot clients to WAN
- No port forwarding by default

### Interface Isolation

**WAN Interfaces**:
- No inbound connections accepted
- Outbound only (for remote access, updates)
- Failover does not change firewall

**Hotspot**:
- Clients isolated from each other (optional, future)
- Clients can reach: Web interface, API, device
- Clients NAT to WAN for internet

**VLANs**:
- Each VLAN follows same rules as physical interface
- No inter-VLAN routing by default (configurable)

### WiFi Security

**Encryption**:
- WPA2-PSK minimum
- WPA3-PSK if supported by hardware
- No open/WEP networks

**Password Requirements**:
- Minimum 8 characters (enforced at installation)
- Recommend: 12+ characters, mixed character types
- No default password (user must set)

**SSID**:
- Format: RPi-Engineer-[last4MAC] (reduces predictability)
- Configurable (user can change)

### DNS Security

**Hotspot DNS**:
- dnsmasq forwards to WAN DNS
- Fallback to 8.8.8.8 if no WAN DNS
- No DNS amplification (rate limit responses)
- Local resolution for rpi-engineer.local

---

## Application Security

### Input Validation

**All User Input**:
- Validate type (string, number, etc.)
- Validate length (prevent overflow)
- Validate format (IP address, CIDR, etc.)
- Reject invalid input with clear error
- Never trust client-side validation alone

**API Input**:
- JSON schema validation for request bodies
- Parameter sanitization
- Reject unknown fields (strict mode) or ignore

**File Upload**:
- Validate file type (whitelist)
- Limit file size
- Scan for malicious content (future)
- Store outside web root with restricted permissions

### Injection Prevention

**SQL Injection**:
- Use parameterized queries exclusively
- ORM or prepared statements
- No string concatenation for SQL

**Command Injection**:
- Avoid shell execution with user input
- If necessary: Use subprocess with list args, not shell=True
- Whitelist allowed commands
- Validate and sanitize any dynamic arguments

**Path Traversal**:
- Validate file paths
- Use allowlists for file access
- Resolve paths, reject if outside allowed directory

**Log Injection**:
- Sanitize user input before logging
- Structured logging to prevent log forging

### Output Encoding

**Web Interface**:
- Escape all user-controlled output (HTML entity encoding)
- Use framework auto-escaping where available
- Content-Security-Policy header (future)

**API Responses**:
- JSON encoding (no script injection)
- Appropriate Content-Type headers

### Session Security

**Current Model**: No authentication, no sessions

**If Authentication Added** (future):
- Secure session tokens
- HttpOnly, Secure cookies
- Session timeout
- CSRF protection

---

## Service Privilege Separation

### Service User

**User**: `rpi-engineer`
**Group**: `rpi-engineer`

**Purpose**: Run application services with minimal privileges

**Capabilities**:
- Read/write application directories
- Read configuration
- Bind to privileged ports (via systemd capability or ambient)
- Access serial devices (dialout group)
- Access network (net_admin for some operations)

**Does NOT Have**:
- Root/sudo
- Access to other users' files
- Unrestricted system modification

### Service Isolation

**Process Separation**:
- Each manager service runs as separate process
- Failure of one does not crash others
- systemd restarts failed services

**File Permissions**:
```
/opt/rpi-engineer/     - root:rpi-engineer, 755 (dirs), 644 (files)
/etc/rpi-engineer/    - root:root, 755 (dirs), 600 (config with secrets)
/var/lib/rpi-engineer/ - root:rpi-engineer, 755 (dirs), 640 (data)
/var/log/rpi-engineer/ - root:rpi-engineer, 755 (dirs), 640 (logs)
```

**Principle**: Config with secrets (600) - only root. Data and logs - service user.

### Privileged Operations

**Operations Requiring Root**:
- Network configuration (interface, routing)
- Firewall rules
- Service installation/update
- WiFi hotspot configuration
- Package installation

**Implementation**:
- Use sudo or polkit for specific commands
- Minimal privilege escalation
- Audit logged
- Or: Dedicated helper binary with setuid (avoid if possible)

---

## Remote Access Security

### Remote Access Tools

**AnyDesk, TeamViewer, VNC**:
- Third-party tools with own security model
- Encrypted connections (AnyDesk, TeamViewer)
- VNC: Unencrypted by default - use over VPN or SSH tunnel if sensitive

**Unattended Access**:
- Pre-configured during installation
- Strong password required
- User responsible for credential security

### Recommendations

**For Sensitive Deployments**:
- Use VPN before remote access (connect device to VPN, access via VPN)
- Restrict remote access tool to specific networks (if supported)
- Use VNC over SSH tunnel for full control
- Consider time-limited access

**Credentials**:
- Use unique password per device
- Rotate passwords periodically
- Do not share credentials broadly

### Display of Connection IDs

**Risk**: Connection IDs visible on web interface and optional display

**Mitigation**:
- IDs alone do not grant access (password required)
- Assumes authorized users have web/hotspot access
- Optional: Hide IDs, require authentication to view (future)

---

## Update Security

### Update Source Verification

**HTTPS**: All Git operations over HTTPS (certificate verification)

**Repository**: Known, trusted repository URL

**Optional Enhancements**:
- Signed tags for releases (verify with GPG)
- Commit hash pinning for reproducible builds
- Checksum verification of downloaded files

### Update Integrity

**Before Apply**:
- Verify download integrity
- Validate file structure
- Check version compatibility

**During Apply**:
- Atomic file replacement where possible
- Backup before overwrite
- Rollback on failure

### Malicious Update Mitigation

**Assumptions**:
- Repository not compromised
- Supply chain trusted

**If Repository Compromised**:
- Manual update from known-good source
- Verify checksums from alternate channel
- Reinstall from scratch if necessary

**User Action**: Use official repository, verify URL

---

## Data Protection

### Data at Rest

**Sensitive Data**:
- WiFi password (in config, restrict permissions)
- Remote access passwords (in tool configs)
- Serial logs (may contain device credentials)
- Packet captures (network traffic)

**Protection**:
- File permissions (600 for config with secrets)
- No unnecessary logging of secrets
- User responsibility: Secure device physically

**Future**: Optional disk encryption (LUKS) for full partition

### Data in Transit

**Web Interface**:
- HTTP by default (per requirements - simplified deployment)
- HTTPS recommended for production (user can configure)
- WiFi encryption (WPA2) protects hotspot traffic

**API**:
- Same as web (HTTP or HTTPS)
- No sensitive data in URL (use POST body)

**Remote Access**:
- AnyDesk/TeamViewer: Encrypted
- VNC: Unencrypted - use VPN or tunnel

### Data Retention

**Logs**: Per LOGGING-MONITORING-SPECIFICATION (7-30 days)

**Serial Logs**: Until manually deleted (user responsibility)

**Packet Captures**: Until manually deleted (user responsibility)

**Backups**: Per UPDATE-MAINTENANCE-SPECIFICATION

---

## Security Best Practices for Users

### Deployment

1. **Change Defaults**: Set strong WiFi password during installation
2. **Physical Security**: Store device securely when unattended
3. **Network Isolation**: Deploy on isolated segment when possible
4. **Updates**: Apply updates periodically, verify source

### Operational

1. **Serial Logs**: Delete logs containing credentials when done
2. **Packet Captures**: Secure capture files; they may contain sensitive traffic
3. **Remote Access**: Use strong passwords, limit credential distribution
4. **Backups**: Encrypt backups if containing sensitive data; store securely

### Monitoring

1. **Review Logs**: Periodically check for anomalies
2. **Connection History**: Review remote access connections
3. **Alerts**: Act on security-related alerts (failed logins if auth added)

### Incident Response

1. **Compromise Suspected**: Disconnect from network, preserve logs
2. **Credential Exposure**: Change passwords, rotate remote access credentials
3. **Physical Theft**: Change all credentials, consider device as compromised

---

## Future Security Enhancements

### Authentication

- Optional password for web interface
- Role-based access (viewer, operator, admin)
- Session management with timeout

### Encryption

- HTTPS by default with auto-generated or Let's Encrypt cert
- Optional full disk encryption
- Encrypted backups

### Hardening

- Security headers (CSP, HSTS, X-Frame-Options)
- Rate limiting on API
- Audit logging for sensitive operations

### Compliance

- Document compliance with relevant standards (if required)
- Security audit support
- Vulnerability disclosure process

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial security specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- NETWORK-MANAGEMENT-SPECIFICATION.md
- REMOTE-ACCESS-SPECIFICATION.md
- UPDATE-MAINTENANCE-SPECIFICATION.md
- LOGGING-MONITORING-SPECIFICATION.md

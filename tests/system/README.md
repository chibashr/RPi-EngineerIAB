# System Test Checklist

Use this checklist for full-stack validation on target hardware or a VM,
aligned with `.planning/TESTING-VALIDATION-SPECIFICATION.md`.

## Environment

- Raspberry Pi 4 (minimum) or Pi 5 preferred
- Fresh Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+)
- Ethernet + WiFi available
- USB-to-serial adapter available

## Installation

- [ ] Run the installation script on a clean system
- [ ] Verify all services start
- [ ] Verify web interface loads from hotspot client

## Network

- [ ] Verify WAN detection and routing
- [ ] Connect to hotspot from phone/laptop
- [ ] Confirm internet access from hotspot client
- [ ] Test WAN failover (disconnect primary)

## Serial Console

- [ ] Connect USB-to-serial adapter
- [ ] Open console session from web interface
- [ ] Verify data send/receive
- [ ] Verify log is created

## Packet Capture

- [ ] Start capture on eth0 or loopback
- [ ] Generate traffic and stop capture
- [ ] Download capture and open in Wireshark
- [ ] Verify live view

## Remote Access

- [ ] Confirm remote access tool is running
- [ ] Retrieve connection ID from web interface
- [ ] Connect from remote workstation

## Update & Rollback

- [ ] Run update check
- [ ] Apply update
- [ ] Verify version change
- [ ] Trigger rollback and verify restore

## Verification Summary

- [ ] Web interface responsive in Simple mode
- [ ] Web interface responsive in Advanced mode
- [ ] No critical errors in logs

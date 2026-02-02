# API Reference

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Base URL and Versioning](#base-url-and-versioning)
3. [Request and Response Format](#request-and-response-format)
4. [Error Handling](#error-handling)
5. [Network API](#network-api)
6. [Serial API](#serial-api)
7. [Capture API](#capture-api)
8. [System API](#system-api)
9. [Updates API](#updates-api)
10. [Backup API](#backup-api)
11. [Logs API](#logs-api)
12. [Modules API](#modules-api)
13. [Remote Access API](#remote-access-api)
14. [WebSocket API](#websocket-api)
15. [Rate Limiting and Authentication](#rate-limiting-and-authentication)

---

## Overview

### Purpose

This document provides the complete API reference for the RPi Engineer-in-a-Box platform. All backend services expose functionality through REST APIs and WebSocket connections, routed through the API Gateway.

### API Gateway

**Role**: Unified entry point for all API requests

**Base Path**: `/api/v1/`

**Protocol**: HTTP/1.1, WebSocket for real-time endpoints

---

## Base URL and Versioning

### Base URL

- **Local (hotspot)**: `http://192.168.50.1`
- **Full API base**: `http://192.168.50.1/api/v1/`

### Versioning

**Current Version**: v1

**Strategy**: URL path versioning (`/api/v1/`)

**Backward Compatibility**: v1 endpoints remain stable within major version. New endpoints may be added. Breaking changes require new version (v2).

---

## Request and Response Format

### Content Types

**Request**: `Content-Type: application/json` for POST/PUT with body

**Response**: `Content-Type: application/json` for all JSON responses

### Request Format

**GET**: Query parameters for filters, pagination

**POST/PUT**: JSON body

```json
{
  "field": "value",
  "nested": {
    "key": "value"
  }
}
```

### Response Format

**Success** (200, 201):
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-02-02T14:30:00Z"
  }
}
```

**List Response**:
```json
{
  "data": [ ... ],
  "meta": {
    "total": 42,
    "page": 1,
    "per_page": 20
  }
}
```

### Timestamps

**Format**: ISO 8601 (`YYYY-MM-DDTHH:MM:SS.sssZ`)

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { }
  }
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Success |
| 201 | Created - Resource created |
| 204 | No Content - Success, no body |
| 400 | Bad Request - Invalid input |
| 404 | Not Found - Resource not found |
| 409 | Conflict - State conflict |
| 500 | Internal Server Error - Server error |

### Error Codes

| Code | Description |
|------|-------------|
| VALIDATION_ERROR | Input validation failed |
| NOT_FOUND | Resource not found |
| CONFLICT | Operation conflicts with current state |
| DEVICE_BUSY | Device in use |
| PERMISSION_DENIED | Access denied |
| INTERNAL_ERROR | Unexpected server error |

---

## Network API

### List Interfaces

```
GET /api/v1/network/interfaces
```

**Response**:
```json
{
  "data": {
    "interfaces": [
      {
        "id": "eth0",
        "name": "eth0",
        "friendly_name": "Ethernet",
        "type": "ethernet",
        "status": "up",
        "ip_address": "192.168.1.100",
        "gateway": "192.168.1.1",
        "metric": 200,
        "role": "wan"
      }
    ]
  }
}
```

### Get Interface Details

```
GET /api/v1/network/interfaces/{id}
```

### Update Interface

```
PUT /api/v1/network/interfaces/{id}
```

**Body**:
```json
{
  "mode": "static",
  "ip_address": "192.168.1.100",
  "netmask": "255.255.255.0",
  "gateway": "192.168.1.1",
  "dns": ["8.8.8.8"]
}
```

### Get Routes

```
GET /api/v1/network/routes
```

### Add Route

```
POST /api/v1/network/routes
```

**Body**:
```json
{
  "destination": "10.0.0.0/8",
  "gateway": "192.168.1.1",
  "interface": "eth0"
}
```

### Get Network Profiles

```
GET /api/v1/network/profiles
```

### Save Profile

```
POST /api/v1/network/profiles
```

**Body**:
```json
{
  "name": "Site-A",
  "description": "Configuration for Site A"
}
```

### Load Profile

```
POST /api/v1/network/profiles/{name}/load
```

### Get Status

```
GET /api/v1/network/status
```

**Response**:
```json
{
  "data": {
    "wan_interface": "usb0",
    "wan_status": "connected",
    "hotspot_status": "active",
    "last_test": "2026-02-02T14:30:00Z"
  }
}
```

---

## Serial API

### List Devices

```
GET /api/v1/serial/devices
```

**Response**:
```json
{
  "data": {
    "devices": [
      {
        "id": "/dev/ttyUSB0",
        "path": "/dev/ttyUSB0",
        "friendly_name": "Router-Core",
        "chipset": "FTDI",
        "status": "available",
        "baud_rate": 9600,
        "config": {}
      }
    ]
  }
}
```

### Get Device Details

```
GET /api/v1/serial/devices/{id}
```

### Update Device Configuration

```
PUT /api/v1/serial/devices/{id}
```

**Body**:
```json
{
  "friendly_name": "Router-Core-01",
  "baud_rate": 9600,
  "data_bits": 8,
  "parity": "none",
  "stop_bits": 1,
  "flow_control": "none"
}
```

### Test Device

```
POST /api/v1/serial/devices/{id}/test
```

### Create Session

```
POST /api/v1/serial/sessions
```

**Body**:
```json
{
  "device_id": "/dev/ttyUSB0",
  "config": {
    "baud_rate": 9600
  }
}
```

**Response**:
```json
{
  "data": {
    "session_id": "uuid",
    "device_id": "/dev/ttyUSB0",
    "websocket_url": "ws://192.168.50.1/ws/serial/uuid"
  }
}
```

### List Sessions

```
GET /api/v1/serial/sessions
```

### Get Session Details

```
GET /api/v1/serial/sessions/{id}
```

### Update Session (Pause/Resume Logging)

```
PUT /api/v1/serial/sessions/{id}
```

**Body**:
```json
{
  "logging_paused": true
}
```

### Close Session

```
DELETE /api/v1/serial/sessions/{id}
```

### List Logs

```
GET /api/v1/serial/logs
```

**Query**: `?device=`, `?since=`, `?limit=`

### Get Log Content

```
GET /api/v1/serial/logs/{id}/content
```

### Delete Log

```
DELETE /api/v1/serial/logs/{id}
```

### Export Logs

```
POST /api/v1/serial/logs/export
```

**Body**:
```json
{
  "log_ids": ["id1", "id2"]
}
```

---

## Capture API

### List Interfaces

```
GET /api/v1/capture/interfaces
```

### Start Capture

```
POST /api/v1/capture/start
```

**Body**:
```json
{
  "interface": "eth0",
  "filter": "tcp port 80",
  "duration_seconds": 3600,
  "max_size_mb": 100,
  "name": "capture-1"
}
```

### List Active Captures

```
GET /api/v1/capture/active
```

### Get Active Capture Details

```
GET /api/v1/capture/active/{id}
```

### Stop Capture

```
POST /api/v1/capture/active/{id}/stop
```

### List Completed Captures

```
GET /api/v1/capture/completed
```

**Query**: `?interface=`, `?since=`, `?limit=`

### Get Completed Capture Details

```
GET /api/v1/capture/completed/{id}
```

### Download Capture

```
GET /api/v1/capture/completed/{id}/download
```

**Response**: Binary PCAP file, `Content-Disposition: attachment`

### Delete Capture

```
DELETE /api/v1/capture/completed/{id}
```

### Get Capture Statistics

```
GET /api/v1/capture/{id}/stats
```

**Response**:
```json
{
  "data": {
    "packet_count": 1234,
    "byte_count": 567890,
    "duration_seconds": 60,
    "protocols": {},
    "start_time": "...",
    "end_time": "..."
  }
}
```

### Get Packets (Paginated)

```
GET /api/v1/capture/{id}/packets?page=1&per_page=50
```

### Get Conversations

```
GET /api/v1/capture/{id}/conversations
```

### Get Protocol Distribution

```
GET /api/v1/capture/{id}/protocols
```

---

## System API

### Get System Status

```
GET /api/v1/system/status
```

**Response**:
```json
{
  "data": {
    "status": "healthy",
    "services": {
      "api_gateway": "running",
      "network_manager": "running"
    },
    "resources": {
      "cpu_percent": 12.5,
      "memory_percent": 45,
      "disk_percent": 32,
      "temperature_c": 48
    },
    "uptime_seconds": 3600
  }
}
```

### List Services

```
GET /api/v1/system/services
```

### Control Service

```
POST /api/v1/system/services
```

**Body**:
```json
{
  "service": "network_manager",
  "action": "restart"
}
```

**Actions**: `start`, `stop`, `restart`

### Power Control

```
POST /api/v1/system/power
```

**Body**:
```json
{
  "action": "reboot"
}
```

**Actions**: `shutdown`, `reboot`

### Get System Info

```
GET /api/v1/system/info
```

**Response**:
```json
{
  "data": {
    "hostname": "rpi-engineer",
    "version": "1.0.0",
    "model": "Raspberry Pi 4 Model B",
    "os": "Ubuntu 22.04 or Raspberry Pi OS Bookworm"
  }
}
```

---

## Updates API

### Check for Updates

```
GET /api/v1/updates/check
```

**Response**:
```json
{
  "data": {
    "current_version": "1.0.0",
    "update_available": true,
    "available_version": "1.1.0",
    "release_notes": "..."
  }
}
```

### Apply Update

```
POST /api/v1/updates/apply
```

**Response**: Long-running, progress via WebSocket or polling

### Rollback

```
POST /api/v1/updates/rollback
```

---

## Backup API

### Download Configuration Backup

```
GET /api/v1/backup/config
```

**Response**: JSON or archive file download

### Restore Configuration

```
POST /api/v1/backup/restore
```

**Body**: `multipart/form-data` with backup file

---

## Logs API

### List Log Files

```
GET /api/v1/logs/system
```

**Response**:
```json
{
  "data": {
    "files": [
      {
        "name": "api_gateway.log",
        "size": 12345,
        "modified": "2026-02-02T14:30:00Z"
      }
    ]
  }
}
```

### Get Log Content

```
GET /api/v1/logs/system?file={name}&tail={n}
```

**Query**:
- `file`: Log file name
- `tail`: Last N lines (default 100)
- `level`: Filter by level
- `search`: Text search

### Export Logs

```
GET /api/v1/logs/export
```

**Query**: `?files=`, `?since=`

**Response**: ZIP archive download

---

## Modules API

### List Modules

```
GET /api/v1/modules/list
```

**Response**:
```json
{
  "data": {
    "modules": [
      {
        "id": "display_driver",
        "name": "Display Driver",
        "version": "1.0.0",
        "enabled": true,
        "description": "..."
      }
    ]
  }
}
```

### Install Module

```
POST /api/v1/modules/install
```

**Body**:
```json
{
  "module_url": "https://...",
  "module_id": "display_driver"
}
```

### Uninstall Module

```
DELETE /api/v1/modules/uninstall/{id}
```

---

## Remote Access API

### Get Status

```
GET /api/v1/remote/status
```

**Response**:
```json
{
  "data": {
    "tools": [
      {
        "name": "anydesk",
        "status": "running",
        "connection_id": "123 456 789",
        "ready": true
      }
    ]
  }
}
```

### Get Connection Info

```
GET /api/v1/remote/info
```

**Response**:
```json
{
  "data": {
    "connection_ids": {
      "anydesk": "123 456 789",
      "teamviewer": "123 456 789"
    },
    "status": {}
  }
}
```

---

## WebSocket API

### Serial Console

**URL**: `ws://192.168.50.1/ws/serial/{session_id}`

**Connect**: After creating session via REST API

**Message Types (Client → Server)**:

```json
{"type": "data", "data": "show version\n"}
{"type": "resize", "rows": 24, "cols": 80}
{"type": "control", "action": "pause_logging"}
```

**Message Types (Server → Client)**:

```json
{"type": "data", "data": "Router# show version\n"}
{"type": "status", "bytes_tx": 100, "bytes_rx": 500}
{"type": "error", "message": "Device disconnected"}
```

### Live Capture Stream

**URL**: `ws://192.168.50.1/ws/capture/{capture_id}`

**Purpose**: Real-time packet stream for live viewer

**Message Format**: JSON with packet data

### System Events (Future)

**URL**: `ws://192.168.50.1/ws/events`

**Purpose**: Real-time system status, alerts

---

## Rate Limiting and Authentication

### Rate Limiting

**Current**: No rate limiting (per requirements)

**Future**: May add per-IP limits for abuse prevention

### Authentication

**Current**: No authentication (per PROJECT-OVERVIEW)

**Future**: If added:
- Bearer token or session cookie
- 401 Unauthorized for protected endpoints
- Login endpoint for credential exchange

### CORS

**Allowed**: Same-origin and hotspot subnet (192.168.50.0/24)

**Headers**: Standard CORS headers for API access from web interface

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial API reference |

## Related Documents
- SYSTEM-ARCHITECTURE.md
- All feature specifications
- DEVELOPMENT-GUIDE.md

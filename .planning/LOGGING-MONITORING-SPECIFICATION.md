# Logging and Monitoring Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Logging Architecture](#logging-architecture)
3. [Log Levels and Format](#log-levels-and-format)
4. [Log Rotation and Retention](#log-rotation-and-retention)
5. [System Metrics Collection](#system-metrics-collection)
6. [Health Monitoring](#health-monitoring)
7. [Alert Generation and Display](#alert-generation-and-display)
8. [Log Viewing and Export](#log-viewing-and-export)
9. [Performance Monitoring](#performance-monitoring)
10. [Integration](#integration)

---

## Overview

### Purpose

The Logging and Monitoring system provides operational visibility into the RPi Engineer-in-a-Box platform. It enables troubleshooting, performance analysis, and proactive identification of issues through centralized logging, metrics collection, and health monitoring.

### Core Requirements

**Functional Requirements**:
- Structured logging from all services
- Configurable log levels per service
- Log rotation and retention management
- System metrics (CPU, RAM, disk, temperature)
- Health checks for services and connectivity
- Alert generation for critical conditions
- Log viewing and export via web interface and API
- Performance metrics for key operations

**Non-Functional Requirements**:
- Logging overhead <2% CPU
- Metrics collection every 5-60 seconds (configurable)
- Log retention: 7-30 days (configurable)
- Alerts displayed within 30 seconds of condition
- Export completes for typical log sizes within 60 seconds

### Design Principles

1. **Centralized**: All services log to consistent locations
2. **Structured**: Machine-parseable format for analysis
3. **Configurable**: Levels and retention adjustable
4. **Non-Intrusive**: Minimal impact on system performance
5. **Actionable**: Alerts indicate clear next steps

---

## Logging Architecture

### Log Sources

**Application Services**:
- API Gateway
- Network Manager
- Serial Manager
- Capture Manager
- System Manager
- Update Manager
- Module Manager
- Remote Access Manager

**System Components**:
- nginx (access, error)
- hostapd (WiFi)
- dnsmasq (DHCP/DNS)
- systemd (service lifecycle)

### Log Destinations

**Primary Location**: `/var/log/rpi-engineer/`

```
/var/log/rpi-engineer/
├── api_gateway.log
├── network_manager.log
├── serial_manager.log
├── capture_manager.log
├── system_manager.log
├── update_manager.log
├── module_manager.log
├── remote_access.log
├── update.log              # Update operations
└── combined.log            # Optional: All application logs
```

**System Logs** (read-only access):
- `/var/log/syslog` - System messages
- `journalctl` - systemd journal

### Logging Service

**Purpose**: Centralized log collection and API

**Location**: `/opt/rpi-engineer/services/logging_service/`

**Responsibilities**:
- Aggregate log entries from services
- Provide log viewing API
- Handle log export
- Manage log rotation coordination
- Filter and search support

**Note**: Each service writes directly to its log file. Logging Service reads and serves logs; it does not receive log streams from services.

---

## Log Levels and Format

### Log Levels

**Standard Levels** (Python logging):
- **DEBUG**: Detailed diagnostic information
- **INFO**: General operational messages
- **WARNING**: Something unexpected but handled
- **ERROR**: Error that prevented specific operation
- **CRITICAL**: System-level failure, immediate attention

**Default Level**: INFO for production, DEBUG for development

**Per-Service Configuration**:
```json
{
  "api_gateway": "INFO",
  "network_manager": "INFO",
  "serial_manager": "DEBUG",
  "capture_manager": "INFO"
}
```

### Log Format

**Structured Format** (JSON for machine parsing):
```json
{
  "timestamp": "2026-02-02T14:30:00.123Z",
  "level": "INFO",
  "service": "network_manager",
  "message": "WAN failover: switched to eth0",
  "extra": {
    "previous_interface": "usb0",
    "reason": "connectivity_test_failed"
  }
}
```

**Human-Readable Format** (default for file output):
```
2026-02-02 14:30:00,123 INFO [network_manager] WAN failover: switched to eth0 (previous=usb0, reason=connectivity_test_failed)
```

**Format Configuration**:
- File: Human-readable (for direct inspection)
- API/Export: JSON (for programmatic use)
- Optional: Both formats in separate files

### Log Message Guidelines

**Include**:
- Timestamp (automatic)
- Service name (automatic)
- Clear, actionable message
- Context (IDs, interface names, etc.)
- Error details (stack trace for ERROR+)

**Avoid**:
- Sensitive data (passwords, keys)
- Excessive verbosity at INFO level
- PII in logs

---

## Log Rotation and Retention

### Rotation Policy

**Tool**: logrotate (system) or Python logging handler

**Rotation Triggers**:
- Size: Rotate when file reaches 10MB
- Time: Daily rotation as fallback
- Both: Whichever comes first

**Rotation Action**:
- Compress rotated files (gzip)
- Keep N rotated files (default: 7)
- No rotation during active write (copytruncate or similar)

### Retention

**Default Retention**: 7 days of logs

**Configurable**: 1, 3, 7, 14, 30 days

**Storage Consideration**:
- Raspberry Pi storage may be limited
- Recommend 7 days for 8GB+ storage
- 3 days for minimal storage

**Retention by Log Type**:
- Application logs: Per retention setting
- Update logs: 30 days (for troubleshooting updates)
- System logs: Per system default

### Configuration

**Location**: `/etc/rpi-engineer/logging.conf`

```ini
[retention]
days = 7
max_size_mb = 100

[rotation]
max_file_size_mb = 10
compress = true

[levels]
default = INFO
api_gateway = INFO
network_manager = INFO
```

---

## System Metrics Collection

### Collected Metrics

**System Resources**:
- CPU usage (overall, per-core optional)
- Memory: Used, available, percent
- Disk: Used, available, percent (root, data partition)
- Temperature: CPU temperature (RPi)
- Uptime: System uptime

**Network**:
- Interface statistics (bytes, packets, errors) per interface
- WAN connectivity status
- Active connections count (optional)

**Services**:
- Service status (running/stopped)
- Process count
- Restart count (if applicable)

### Collection Interval

**Default**: Every 30 seconds

**Configurable**: 5, 15, 30, 60 seconds

**Storage**: Rolling buffer, last 24 hours at collection interval

### Metrics Storage

**Format**: Time-series in SQLite or in-memory with periodic flush

**Schema** (conceptual):
```
metrics (timestamp, metric_name, value, tags)
```

**Examples**:
- (2026-02-02 14:30:00, cpu_percent, 12.5, {})
- (2026-02-02 14:30:00, memory_percent, 45.2, {})
- (2026-02-02 14:30:00, disk_percent, 32.1, {mount: "/"})
- (2026-02-02 14:30:00, temperature_c, 48, {})

**Retention**: 7 days default, configurable

---

## Health Monitoring

### Health Checks

**Service Health**:
- Each service responds to health endpoint or heartbeat
- Check: Process running, responsive
- Interval: Every 60 seconds

**Connectivity Health**:
- WAN: Ping + DNS test (from Network Manager)
- Hotspot: hostapd running, clients can connect
- API: HTTP 200 from /api/v1/system/status

**Resource Health**:
- Disk space >10% free (warning if below)
- Memory <90% used (warning if above)
- Temperature <80°C (warning if above, critical at 85°C)

### Health Status Levels

- **Healthy**: All checks pass
- **Degraded**: Non-critical check failed (e.g., WAN down but hotspot up)
- **Unhealthy**: Critical failure (e.g., API not responding)
- **Unknown**: Cannot determine (e.g., check timeout)

### Health Check Flow

```
Monitor Service
      │
      ▼
┌─────────────────┐
│ Collect Metrics │
│ (CPU, RAM, etc.)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Services  │
│ (process, API)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Network   │
│ (WAN, hotspot)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Aggregate       │
│ Status          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update Dashboard│
│ Emit Alerts     │
└─────────────────┘
```

---

## Alert Generation and Display

### Alert Conditions

**Critical** (Immediate attention):
- API Gateway not responding
- Disk >95% full
- CPU temperature >85°C
- System service crash loop

**Warning** (Attention soon):
- WAN connectivity lost
- Disk >90% full
- CPU temperature >80°C
- Service restart occurred
- Memory >90% used

**Info** (Informational):
- Update available
- Failover occurred
- Backup completed

### Alert Display

**Web Interface**:
- Banner at top when active alerts
- Color-coded: Red (critical), Yellow (warning), Blue (info)
- Dismissible (per session)
- Link to relevant page or log

**Dashboard Widget**:
- Alert count badge
- Last 5 alerts list
- "View All" link to logs

### Alert Persistence

**Storage**: Alerts logged to system log

**Retention**: Same as log retention

**Acknowledgment**: Optional - user can acknowledge to hide from banner (stored in session or config)

---

## Log Viewing and Export

### Log Viewing API

**Endpoints** (see API-REFERENCE.md):
- `GET /api/v1/logs/system` - List available log files
- `GET /api/v1/logs/system?file={name}&tail={n}` - Get log content
- `GET /api/v1/logs/export` - Export logs as download

**Query Parameters**:
- `file`: Log file name
- `tail`: Last N lines (default 100)
- `level`: Filter by level
- `service`: Filter by service
- `since`: ISO timestamp, logs after
- `search`: Text search in logs

### Web Interface Log Viewer

**Location**: Advanced Mode → System → Logs

**Features**:
- Select log file from dropdown
- Tail view (auto-scroll)
- Search within log
- Filter by level
- Download button
- Refresh

**Performance**:
- Lazy load for large logs
- Virtual scrolling for >1000 lines
- Search uses backend (not load full log)

### Export

**Formats**:
- Plain text (.log)
- ZIP archive (multiple files)

**Scope**:
- Single log file
- All application logs
- Include system logs (optional)
- Date range filter

**Download**: Direct download via browser

---

## Performance Monitoring

### Key Performance Indicators

**API**:
- Request latency (p50, p95, p99)
- Request count per endpoint
- Error rate

**Serial Console**:
- Session count
- Data throughput (bytes/sec)
- Connection latency

**Packet Capture**:
- Active capture count
- Packet rate
- Storage usage

**System**:
- Boot time
- Service start time

### Monitoring Overhead

**Target**: <2% CPU for logging, <1% for metrics

**Optimization**:
- Async logging where possible
- Batch metric writes
- Sample high-frequency metrics
- Disable DEBUG in production

---

## Integration

### With Other Services

**Network Manager**: Provides WAN status to health check

**Update Manager**: Logs update operations to update.log

**API Gateway**: All requests logged (access log)

**Web Interface**: Displays metrics, logs, alerts

### With External Systems

**Future**:
- Syslog export to external SIEM
- SNMP for enterprise monitoring
- Webhook for alert notification

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial logging and monitoring specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- API-REFERENCE.md
- UPDATE-MAINTENANCE-SPECIFICATION.md
- WEB-INTERFACE-SPECIFICATION.md

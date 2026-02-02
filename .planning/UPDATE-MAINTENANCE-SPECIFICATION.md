# Update and Maintenance Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Update Mechanism](#update-mechanism)
3. [Update Check Process](#update-check-process)
4. [Update Application](#update-application)
5. [Rollback Procedures](#rollback-procedures)
6. [Backup and Restore](#backup-and-restore)
7. [Export and Import](#export-and-import)
8. [Web Interface Integration](#web-interface-integration)
9. [Error Handling](#error-handling)
10. [Security Considerations](#security-considerations)

---

## Overview

### Purpose

The Update and Maintenance system provides safe, reliable mechanisms for updating the RPi Engineer-in-a-Box software, backing up configuration, and recovering from failed updates. The design prioritizes system availability and data preservation.

### Core Requirements

**Functional Requirements**:
- Git-based update mechanism
- Update check on boot (optional, configurable)
- Manual update application via web interface
- Automatic rollback on update failure
- Configuration backup before every update
- Full backup and restore procedures
- Export/import of configuration and data

**Non-Functional Requirements**:
- Updates complete within 5 minutes typical
- No data loss during updates
- System remains accessible during update preparation
- Minimal downtime during update application
- Clear user feedback throughout process

### Design Principles

1. **Safety First**: Always backup before changes
2. **User Control**: Updates applied manually, not automatically
3. **Recoverable**: Failed updates automatically rolled back
4. **Transparent**: Clear status and progress reporting
5. **Idempotent**: Update process can be retried safely

---

## Update Mechanism

### Git-Based Updates

**Repository Structure**:
- Updates pulled from Git repository
- Branch: `main` (configurable)
- Tag-based releases preferred for production
- Commit hash recorded for rollback reference

**Update Source**:
```
Repository: https://github.com/chibashr/RPi-EngineerIAB.git
Branch: main
Stable releases: Tags (v1.0.0, v1.1.0, etc.)
```

**What Gets Updated**:
- Application code in `/opt/rpi-engineer/`
- Service definitions (if changed)
- Web interface assets
- Module updates (if bundled)

**What Is Preserved**:
- Configuration in `/etc/rpi-engineer/`
- Data in `/var/lib/rpi-engineer/`
- User data (captures, serial logs)
- Network profiles
- Module configurations

### Update Manager Service

**Location**: `/opt/rpi-engineer/services/update_manager/`

**Responsibilities**:
- Check for available updates
- Download and stage updates
- Execute update procedure
- Perform rollback on failure
- Manage backup/restore
- Report status to API

**Service User**: Runs as `rpi-engineer` user with appropriate permissions

---

## Update Check Process

### Check Triggers

**On Boot** (Optional):
- Configurable: enabled/disabled in system config
- Default: Enabled
- Runs 60 seconds after boot (allows network to stabilize)
- Non-blocking: Does not delay boot
- Result displayed in web interface dashboard

**Manual Check**:
- User clicks "Check for Updates" in web interface
- Immediate check initiated
- Result displayed within 30 seconds

**Scheduled Check** (Future):
- Optional daily/weekly check
- Configurable schedule
- Notification only, no auto-apply

### Check Procedure

```
1. Verify network connectivity (WAN)
2. Fetch remote repository metadata (git ls-remote)
3. Compare remote ref with current installed version
4. If update available:
   - Record available version/tag/commit
   - Display in web interface
   - Offer "Apply Update" button
5. If no update:
   - Display "System is up to date"
```

### Version Comparison

**Installed Version**:
- Stored in `/etc/rpi-engineer/version` or `/var/lib/rpi-engineer/version`
- Format: Semantic version (1.0.0) or commit hash
- Set during installation and each update

**Available Version**:
- From `git describe --tags` or branch HEAD
- Displayed to user before apply

**Update Types**:
- **Patch** (1.0.0 → 1.0.1): Bug fixes, low risk
- **Minor** (1.0.0 → 1.1.0): New features, moderate risk
- **Major** (1.0.0 → 2.0.0): Breaking changes, higher risk (user warning)

---

## Update Application

### Pre-Update Steps

**1. Pre-Flight Checks**:
- WAN connectivity available
- Sufficient disk space (2x update size minimum)
- No critical services in failed state
- No active serial console sessions (warning only)
- No active packet captures (warning only)

**2. Create Backup**:
- Full configuration backup (see Backup section)
- Stored in `/var/lib/rpi-engineer/backups/pre-update-{timestamp}/`
- Backup must succeed before proceeding

**3. Stage Update**:
- Clone or fetch to staging directory
- Verify integrity (checksums if available)
- Do not overwrite live files yet

### Update Procedure

```
┌─────────────────────────────┐
│ User Clicks "Apply Update"  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Pre-Flight Checks           │
│ - Connectivity, disk, etc.  │
└──────────────┬──────────────┘
               │ Pass
               ▼
┌─────────────────────────────┐
│ Create Configuration       │
│ Backup                      │
└──────────────┬──────────────┘
               │ Success
               ▼
┌─────────────────────────────┐
│ Stop Application Services   │
│ (API, managers, etc.)       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Copy New Files to           │
│ /opt/rpi-engineer/          │
│ (preserve config, data)     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Update systemd units        │
│ (if changed)                │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Run post-update script      │
│ (migrations, etc.)          │
└──────────────┬──────────────┘
               │
        ┌──────┴──────┐
        │ Success?    │
        └──────┬──────┘
         Yes   │   No
         │     │
         │     ▼
         │  ┌─────────────────────┐
         │  │ ROLLBACK             │
         │  │ Restore from backup  │
         │  └─────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Start Application Services  │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Verify Services Running     │
└──────────────┬──────────────┘
               │
        ┌──────┴──────┐
        │ All OK?     │
        └──────┬──────┘
         Yes   │   No
         │     │
         │     ▼
         │  ┌─────────────────────┐
         │  │ ROLLBACK             │
         │  └─────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ Record New Version          │
│ Display Success             │
└─────────────────────────────┘
```

### Service Handling

**During Update**:
- Stop order: API Gateway → Other managers → Supporting services
- Stop timeout: 30 seconds per service
- Force kill if necessary (then rollback)

**After Update**:
- Start order: Supporting services → Managers → API Gateway
- Start timeout: 60 seconds per service
- Health check before declaring success

### Post-Update Script

**Location**: `/opt/rpi-engineer/bin/post-update.sh`

**Purpose**:
- Database migrations (if any)
- Configuration schema updates
- Permission fixes
- Cleanup of deprecated files

**Execution**: Run once after file copy, before service start

**Failure**: Triggers rollback

---

## Rollback Procedures

### Automatic Rollback Triggers

- Post-update script exits non-zero
- Any service fails to start
- Health check fails within 2 minutes of update
- Critical error during file copy

### Rollback Procedure

```
1. Stop any partially started services
2. Restore files from pre-update backup
   - /opt/rpi-engineer/ from backup
   - /etc/systemd/system/rpi-engineer*.service from backup
3. Restore version file
4. Run systemctl daemon-reload
5. Start all services
6. Verify health
7. Notify user of rollback
8. Retain backup for manual inspection
```

### Rollback Data

**Preserved**:
- All user data (captures, logs) - never touched by update
- Configuration - restored from backup

**Rollback Backup Retention**:
- Keep last 3 pre-update backups
- Location: `/var/lib/rpi-engineer/backups/`
- Naming: `pre-update-YYYYMMDD-HHMMSS/`

### Manual Rollback

**Web Interface**:
- "Rollback Last Update" button (if rollback occurred)
- Or "Restore from Backup" to select specific backup

**CLI** (if web inaccessible):
```bash
sudo /opt/rpi-engineer/bin/rollback.sh
```

---

## Backup and Restore

### Backup Scope

**Full Backup Includes**:
- `/etc/rpi-engineer/` - All configuration
- `/var/lib/rpi-engineer/` - State, database
- Network profiles
- Module configurations
- System configuration (hostname, etc.)

**Excluded**:
- Packet capture files (large, optional include)
- Serial log files (large, optional include)
- Temporary files
- Log files (can be large)

### Backup Types

**Pre-Update Backup** (Automatic):
- Triggered before every update
- Full configuration and state
- Retained for rollback

**Manual Backup** (User-Initiated):
- User clicks "Backup Now" in web interface
- Same scope as pre-update
- User can name and download

**Scheduled Backup** (Future):
- Optional daily/weekly
- Retained locally, configurable count

### Backup Format

**Structure**:
```
backup-YYYYMMDD-HHMMSS/
├── manifest.json          # Backup metadata, file list
├── config/                 # Configuration files
│   ├── system.conf
│   └── ...
├── data/                   # State and database
│   └── ...
└── checksums.json          # Optional integrity check
```

**Manifest**:
```json
{
  "version": "1.0",
  "created": "2026-02-02T14:30:00Z",
  "source_version": "1.0.0",
  "includes": ["config", "data", "network_profiles"],
  "excludes": ["captures", "serial_logs"]
}
```

### Restore Procedure

**From Web Interface**:
1. User uploads backup file (tar.gz or zip)
2. System validates backup format
3. Preview of what will be restored
4. User confirms
5. Stop services
6. Restore files (preserve existing if conflict)
7. Start services
8. Verify

**Restore Options**:
- **Full Restore**: Replace all configuration
- **Selective Restore**: Choose components (e.g., network only)
- **Merge**: Restore missing files only (advanced)

---

## Export and Import

### Configuration Export

**Purpose**: Transfer configuration between devices or backup externally

**Export Contents**:
- System configuration
- Network profiles
- Module configurations
- Excludes: Passwords, secrets (user prompted to re-enter)

**Format**: JSON or encrypted archive

**Web Interface**: Settings → Backup → Export Configuration

### Configuration Import

**Purpose**: Apply configuration from another device or restore from export

**Process**:
1. Upload export file
2. Validate format and version compatibility
3. Preview changes (diff)
4. User confirms
5. Apply configuration
6. Restart affected services

**Version Compatibility**:
- Same major version: Full compatibility
- Different minor: Warn, attempt import
- Different major: May require migration

### Data Export

**Packet Captures**: Download individually or bulk (ZIP)

**Serial Logs**: Download individually or bulk (ZIP)

**All User Data**: Full export for migration to new device

---

## Web Interface Integration

### Update Status Display

**Dashboard**:
- Current version
- "Check for Updates" button
- If update available: Version, "Apply Update" button
- Last check time

**Update Page** (Advanced Mode):
- Current version details
- Update history (last 5 updates)
- Check for updates
- Apply update (with confirmation)
- Rollback (if applicable)
- Backup/Restore section

### Update Confirmation Dialog

**Before Apply**:
- Available version
- Warning about brief downtime
- Checkbox: "I have ensured no critical operations are in progress"
- Apply / Cancel buttons

**During Update**:
- Progress indicator (stages)
- "Do not close this page" message
- Estimated time remaining

**After Update**:
- Success: New version, "Refresh" to reload
- Failure: Rollback message, support info

### API Endpoints

See API-REFERENCE.md for:
- `GET /api/v1/updates/check`
- `POST /api/v1/updates/apply`
- `POST /api/v1/updates/rollback`
- `GET /api/v1/backup/config`
- `POST /api/v1/backup/restore`

---

## Error Handling

### Common Errors

**No Network**:
- Cannot check for updates
- Message: "Connect to internet to check for updates"

**Insufficient Disk Space**:
- Block update
- Message: "Free at least X MB to update"

**Update Download Failed**:
- Retry up to 3 times
- If persistent: Abort, suggest manual update

**Service Start Failure**:
- Automatic rollback
- Log detailed error
- Notify user

**Partial Update**:
- Rollback restores complete previous state
- No partial/corrupt state

### Logging

**Update Log**:
- All update steps logged to `/var/log/rpi-engineer/update.log`
- Retained for 30 days
- Included in system log export

---

## Security Considerations

### Update Source Verification

**Recommendations**:
- Use HTTPS for Git operations
- Verify repository identity (SSH key or known host)
- Consider signed tags for release verification (future)

### Backup Security

- Backups may contain sensitive data (passwords, keys)
- Store in restricted location (0700 permissions)
- Encrypt exports if containing secrets
- User responsible for secure external backup storage

### Privilege Separation

- Update runs with elevated privileges (root)
- Backup/restore requires root
- Web interface triggers update via authenticated service call

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial update and maintenance specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- INSTALLATION-SPECIFICATION.md
- API-REFERENCE.md
- SECURITY-SPECIFICATION.md

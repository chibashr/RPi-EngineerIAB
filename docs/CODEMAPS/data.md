# Data

<!-- Generated: 2026-03-06 | Files scanned: 140+ | Token estimate: ~350 -->

## Overview

No central RDBMS. Config and state in files; optional SQLite per module for event storage.

## Config / Version

- **App version**: `config/version` or `data/version` (file), else env `RPI_ENGINEER_VERSION` (default 1.0.0). Update manager writes git ref to version file after apply.
- **System config**: e.g. config/system.conf (referenced by install and services).
- **Backup/restore**: Export/import of config (backup API).

## Module SQLite (optional)

- **SNMP traps**: `modules/snmp_trap_receiver/receiver.py` — sqlite3; tables for stored traps; prune logic.
- **Syslog**: `modules/syslog_receiver/receiver.py` — sqlite3; stored logs; schema migration helpers (_ensure_column), prune.

No shared database; no migration history in repo. Module DB paths typically under data or module-specific dir.

## Persistence Summary

| Concern | Location |
|---------|----------|
| App version | config/version or data/version |
| System/config | config/, backup API |
| SNMP traps | Module SQLite (receiver) |
| Syslog events | Module SQLite (receiver) |
| Captures | capture_manager (files on disk) |
| Serial logs | serial_manager (files) |

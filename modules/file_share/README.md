# File Share Module

Provides FTP and SFTP/SCP access to a shared folder with module-managed users.

## Features

- FTP server with optional anonymous access (off/read-only/read-write).
- SFTP/SCP server using the same module-managed users.
- Web UI with drag-and-drop upload to the share folder.
- Configurable bind addresses and ports for safety.

## Configuration

Config is stored under the app data directory in `file_share/config.json`.

Key settings:

- `share_path`: Absolute path to the share folder. Defaults to the app data share folder.
- `enable_ftp`: Enable FTP service (explicit opt-in).
- `enable_sftp_scp`: Enable SFTP/SCP service (explicit opt-in).
- `ftp_bind_addresses`: Comma-separated IPs to bind FTP.
- `sftp_bind_addresses`: Comma-separated IPs to bind SFTP/SCP.
- `ftp_port`: FTP port (default 2121).
- `sftp_port`: SFTP/SCP port (default 2222).
- `ftp_anonymous`: `off`, `readonly`, or `readwrite`.
- `ftp_anonymous_write_dir`: Optional subdir for anonymous write access.

## Users

Users are stored in `file_share/users.json` (hashed passwords). Create and manage
users from the File Share page in Advanced mode.

## Dependencies

Python dependencies declared in `module.json`:

- `pyftpdlib` for FTP
- `paramiko` for SFTP/SCP

## Notes

- Services are disabled by default for safety.
- Bind to specific interface IPs to limit access to trusted networks.

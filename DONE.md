# Security Hardening — Completion Summary

## What was built (by prompt)

- **Prompt 1 (INSTALL)**: Installer: hotspot interface detection, `config/network.conf`, iptables for eth1, TLS cert generation, hotspot password, AnyDesk/TeamViewer hardening.
- **Prompt 2 (AUTH)**: Auth manager (HMAC tokens, PAM + bcrypt), login endpoint, lockout, `require_admin`, `verify_token`, audit logging.
- **Prompt 3 (ROUTES)**: `require_admin` applied to admin-only routes (updates/reconfigure, reinstall, rollback; modules install/uninstall/enable/disable/install-from-repo/update; system/settings; backup/restore; serial delete log; capture delete).
- **Prompt 4 (WEBSOCKETS)**: Token query param verification on `/ws/updates/apply`; close with 1008 when token missing/invalid.
- **Prompt 5 (FRONTEND)**: Login modal, sessionStorage token, Authorization header injection, admin-only UI gating.
- **Prompt 6–10**: (Assumed prior work: network interface protection for hotspot PUT, module allowlist, etc.)
- **Prompt 11 (VERIFY + FINALIZE)**: Tests fixed and added, README Security section, DONE.md, lint clean.

## AGENTS.md assumptions — held or adjusted

| Assumption | Status |
|------------|--------|
| Token: HMAC-signed, `config/auth.conf` hashed admin password | **Held** |
| Admin password: PAM user `pi`, fallback bcrypt in `config/auth.conf` | **Held** |
| Hotspot interface in `config/network.conf` under `hotspot_interface` | **Held** |
| eth0 LAN binding in `config/network.conf` `bind_lan_interface` (default false) | **Held** |
| AnyDesk config path `/etc/anydesk/service.conf` | **Held** (verify on target Pi OS) |
| TeamViewer config path `/opt/teamviewer/config/global.conf` | **Held** (verify on target Pi OS) |
| Audit log: `data/audit.log`, JSON lines, logrotate 50MB × 10 (500MB cap) | **Held** |
| Raspberry Pi Connect outbound-only endpoints | **Held** (no change) |

## Deviations from security-analysis.md

- No `security-analysis.md` file was present in the repo. Auth matrix and route protection were implemented per AGENTS.md and existing route structure (admin-only vs open). No formal deviation log.

## Known limitations

- **Module allowlist central distribution**: The module allowlist (`config/modules-allowed.conf`) and repo allowlist (`config/modules-allowed-repos.conf`) are **local config files only**. There is no central distribution mechanism for these allowlists; operators must manage them per device. This is an explicit open item.

---

*Author: chibashr*

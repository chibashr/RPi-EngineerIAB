---
name: Phase 5 Installation and Deployment Plan
overview: Detailed implementation plan for Phase 5 (Installation Script and Deployment) of RPi Engineer-in-a-Box. Implements full one-command install and post-install verification per INSTALLATION-SPECIFICATION, SYSTEM-ARCHITECTURE, DEPLOYMENT-GUIDE, REMOTE-ACCESS-SPECIFICATION, and MODULE-SYSTEM-SPECIFICATION.
parentPlan: full_implementation_plan_e49592f8.plan.md
todos:
  - id: phase5-install-deps
    content: Implement dependency installation (apt packages, Python venv, pip)
    status: pending
  - id: phase5-app-install
    content: Implement application installation (copy files, directories, permissions)
    status: pending
  - id: phase5-systemd-units
    content: Create systemd units for API gateway and all services
    status: pending
  - id: phase5-nginx-config
    content: Configure nginx for web UI and API proxy
    status: pending
  - id: phase5-hotspot-config
    content: Configure hostapd and dnsmasq for WiFi hotspot
    status: pending
  - id: phase5-remote-access
    content: Implement remote access tool install (AnyDesk/TeamViewer/VNC/Raspberry Pi Connect)
    status: pending
  - id: phase5-module-install
    content: Implement optional module installation during setup
    status: pending
  - id: phase5-wizard-full
    content: Complete interactive wizard (all prompts per spec)
    status: pending
  - id: phase5-config-gen
    content: Generate config files from wizard choices
    status: pending
  - id: phase5-idempotent
    content: Make install script idempotent and safe to re-run
    status: pending
  - id: phase5-post-install
    content: Implement post-install summary and reboot prompt
    status: pending
  - id: phase5-verify
    content: Verify on clean Ubuntu 22.04+ or Raspberry Pi OS (RPi or VM)
    status: pending
isProject: false
---

# Phase 5: Installation Script and Deployment – Detailed Implementation Plan

This plan implements the **Installation Script and Deployment** phase from [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md). It references the specification suite in [.planning/](../.planning/) in detail.

---

## Goal

One-command install and post-install verification per [INSTALLATION-SPECIFICATION](.planning/INSTALLATION-SPECIFICATION.md). On a clean Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+) (RPi or compatible), run the install command and get a working system (web UI, hotspot, remote access, core features).

---

## Document References

| Document | Path | Relevant Sections |
|----------|------|-------------------|
| **INSTALLATION-SPECIFICATION** | [.planning/INSTALLATION-SPECIFICATION.md](../.planning/INSTALLATION-SPECIFICATION.md) | §1–2 Overview/Prerequisites, §3 Installation Methods, §4 Installation Script (256–413), §5 Setup Wizard (358–458), §6–9 Dependency/App/Service/Module/Remote, §10–11 Post-Install/Verification, §12 Troubleshooting |
| **SYSTEM-ARCHITECTURE** | [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md) | §6 File System Structure (368–398), §8 Service Architecture (459–538), §9 Module System Architecture (541–648) |
| **DEPLOYMENT-GUIDE** | [.planning/DEPLOYMENT-GUIDE.md](../.planning/DEPLOYMENT-GUIDE.md) | §2 Pre-Deployment Checklist, §7 Troubleshooting at Deployment, §8 Post-Deployment Verification |
| **REMOTE-ACCESS-SPECIFICATION** | [.planning/REMOTE-ACCESS-SPECIFICATION.md](../.planning/REMOTE-ACCESS-SPECIFICATION.md) | §3 Installation and Configuration (119–150), AnyDesk/TeamViewer/VNC/Raspberry Pi Connect install steps |
| **MODULE-SYSTEM-SPECIFICATION** | [.planning/MODULE-SYSTEM-SPECIFICATION.md](../.planning/MODULE-SYSTEM-SPECIFICATION.md) | §3 Module Structure (136–200), §5 Module Lifecycle, §10 Example Modules |
| **NETWORK-MANAGEMENT-SPECIFICATION** | [.planning/NETWORK-MANAGEMENT-SPECIFICATION.md](../.planning/NETWORK-MANAGEMENT-SPECIFICATION.md) | Hotspot configuration, hostapd, dnsmasq |
| **DEVELOPMENT-GUIDE** | [.planning/DEVELOPMENT-GUIDE.md](../.planning/DEVELOPMENT-GUIDE.md) | §5 Implementation Order, install script location |

---

## Prerequisites (Phase 5 Assumes Phases 1–4 Complete)

- Phase 1: Repo structure, API gateway skeleton, install.sh framework
- Phase 2: Core backend services (System, Network, Serial, Capture, Remote)
- Phase 3: Web interface (Simple and Advanced modes)
- Phase 4: Update, Logging, Monitor, Module Manager

The install script must deploy all of the above to the target system.

---

## Deliverable 1: Dependency Installation

### Spec References

- **INSTALLATION-SPECIFICATION** §6 Dependency Installation (lines 479–556): System package updates, required packages, Python venv and pip.
- **INSTALLATION-SPECIFICATION** §2 Prerequisites (lines 148–198): Ubuntu 22.04+ or Raspberry Pi OS (Bookworm+), 64-bit ARM, internet required.

### Required apt Packages (per INSTALLATION-SPECIFICATION §6)

| Category | Packages |
|----------|----------|
| Python | python3, python3-pip, python3-venv |
| Web server | nginx |
| Network | network-manager, dnsmasq, hostapd, iptables, bridge-utils, vlan |
| Serial | cu, minicom, screen |
| Packet capture | tcpdump, tshark, wireshark-common |
| System | git, curl, wget, jq, bc, lsof |
| USB | usbutils, usb-modeswitch, usb-modeswitch-data |
| Build | build-essential, python3-dev |
| SSL | openssl, ca-certificates |

### Python Dependencies

- Create venv at `$INSTALL_DIR/venv`
- Install from `requirements.txt` (Flask, pyserial, scapy, psutil, pyudev, etc. per INSTALLATION-SPECIFICATION §6 lines 544–556)

### Todos

- [ ] **phase5-install-deps**: Implement `install_system_dependencies()` and `install_required_packages()` and `install_python_dependencies()` in install.sh. Run `apt-get update` and `apt-get upgrade -y` before packages. Handle idempotency (skip if already installed).

---

## Deliverable 2: Application Installation

### Spec References

- **INSTALLATION-SPECIFICATION** §6 Application Installation (lines 560–627): Directory creation, file deployment, user and permissions.
- **SYSTEM-ARCHITECTURE** §6 File System Structure (lines 368–398): Target layout under `/opt/rpi-engineer/`.

### Directory Structure (per INSTALLATION-SPECIFICATION §6)

```
/opt/rpi-engineer/
├── bin/
├── services/
├── web/
├── modules/
├── lib/
/etc/rpi-engineer/
├── network_profiles/
├── module_config/
/var/lib/rpi-engineer/
├── captures/
├── serial_logs/
├── backups/
├── database/
/var/log/rpi-engineer/
```

### Constants (per INSTALLATION-SPECIFICATION §4)

```bash
INSTALL_DIR="/opt/rpi-engineer"
CONFIG_DIR="/etc/rpi-engineer"
DATA_DIR="/var/lib/rpi-engineer"
LOG_DIR="/var/log/rpi-engineer"
SERVICE_USER="rpi-engineer"
SERVICE_GROUP="rpi-engineer"
```

### User and Permissions

- Create `rpi-engineer` system user (if not exists): `useradd -r -s /bin/false -d $INSTALL_DIR`
- Add to groups: `dialout` (serial), `netdev` (network)
- chown: `$INSTALL_DIR`, `$DATA_DIR`, `$LOG_DIR` to `rpi-engineer:rpi-engineer`
- chmod: 755 install dir, 640 config files, 750 bin scripts

### Todos

- [ ] **phase5-app-install**: Implement `create_directories()`, `deploy_files()` (copy from repo or source dir), `setup_user_permissions()`. Support install from git clone or from existing repo. Handle idempotency (backup before overwrite if re-run).

---

## Deliverable 3: systemd Service Units

### Spec References

- **INSTALLATION-SPECIFICATION** §7 Service Configuration (lines 631–648): Master service, individual services.
- **SYSTEM-ARCHITECTURE** §8 Service Architecture (lines 459–538): rpi-engineer.service, rpi-engineer-api.service, rpi-engineer-network.service, etc.

### Services to Create (per INSTALLATION-SPECIFICATION §7)

| Service | Purpose |
|---------|---------|
| rpi-engineer.service | Master (oneshot, runs start.sh/stop.sh) |
| rpi-engineer-api.service | API Gateway |
| rpi-engineer-network.service | Network Manager |
| rpi-engineer-serial.service | Serial Manager |
| rpi-engineer-capture.service | Capture Manager |
| rpi-engineer-system.service | System Manager |
| rpi-engineer-monitor.service | Monitor Service |
| rpi-engineer-update.service | Update Manager |
| rpi-engineer-logging.service | Logging Service |

### Master Service (per SYSTEM-ARCHITECTURE §8)

```ini
[Unit]
Description=RPi Engineer-in-a-Box Master Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/rpi-engineer/bin/start.sh
ExecStop=/opt/rpi-engineer/bin/stop.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
```

### Todos

- [ ] **phase5-systemd-units**: Create all systemd unit files. Implement `create_master_service()` and individual service creation. Ensure `bin/start.sh` and `bin/stop.sh` exist and start/stop all child services. Enable services at end of install.

---

## Deliverable 4: nginx Configuration

### Spec References

- **INSTALLATION-SPECIFICATION** §7 nginx Configuration (lines 748–796): Server block for static files, API proxy, WebSocket.
- **SYSTEM-ARCHITECTURE** §2 Web Server: nginx serves frontend, proxies API to backend.

### nginx Config Requirements

- Listen on 80 (default_server)
- Root: `/opt/rpi-engineer/web`
- `location /`: try_files for static assets
- `location /api/`: proxy_pass to http://127.0.0.1:5000
- `location /ws/`: WebSocket proxy with Upgrade headers, read_timeout 86400
- Symlink from sites-available to sites-enabled
- Remove default site

### Todos

- [ ] **phase5-nginx-config**: Implement `configure_nginx()`. Run `nginx -t` before enabling. Restart nginx after config.

---

## Deliverable 5: WiFi Hotspot Configuration

### Spec References

- **INSTALLATION-SPECIFICATION** §7 WiFi Hotspot Setup (lines 654–702): hostapd.conf, dnsmasq.conf, wlan0 interface.
- **INSTALLATION-SPECIFICATION** §5 Setup Wizard (lines 416–434): SSID (RPi-Engineer-[last4MAC]), password.
- **SYSTEM-ARCHITECTURE** §7 Network Architecture: wlan0 as AP, 192.168.50.1/24, DHCP 192.168.50.10–100.

### hostapd Configuration

- interface=wlan0, driver=nl80211
- ssid from wizard (default: RPi-Engineer-[last4MAC])
- wpa_passphrase from wizard
- hw_mode=g, channel=6, wpa=2, WPA-PSK

### dnsmasq Configuration

- interface=wlan0
- dhcp-range=192.168.50.10,192.168.50.100,255.255.255.0,24h
- address=/rpi-engineer.local/192.168.50.1

### Network Interface

- /etc/network/interfaces.d/wlan0: static 192.168.50.1/24

### Todos

- [ ] **phase5-hotspot-config**: Implement `configure_hotspot()`. Use wizard values for SSID and password. Create network-priority.sh script per INSTALLATION-SPECIFICATION §7 (lines 706–743). Handle case where wlan0 may not exist (warn, skip hotspot).

---

## Deliverable 6: Remote Access Setup

### Spec References

- **INSTALLATION-SPECIFICATION** §9 Remote Access Setup (lines 827–904): AnyDesk, TeamViewer, VNC install functions.
- **REMOTE-ACCESS-SPECIFICATION** §3 Installation and Configuration (lines 119–150): Unattended access, connection ID retrieval.

### Remote Access Tool Options (per Setup Wizard)

1. AnyDesk (Recommended)
2. TeamViewer
3. TigerVNC
4. Install multiple (select after)
5. Skip

### AnyDesk

- Add repo, apt install anydesk
- Configure unattended: `anydesk --set-password`, `anydesk --get-id` → store in $CONFIG_DIR

### TeamViewer

- Download arm64 .deb, apt install
- teamviewer setup, teamviewer passwd, teamviewer info → store ID

### TigerVNC

- apt install tigervnc-standalone-server
- vncpasswd, create systemd service for VNC

### Todos

- [ ] **phase5-remote-access**: Implement `install_anydesk()`, `install_teamviewer()`, `install_vnc()`. Wire to wizard selection. Enable services (anydesk, teamviewerd, etc.). Store connection IDs in $CONFIG_DIR for web UI display. Handle apt-key deprecation for AnyDesk (use signed-by in sources.list).

---

## Deliverable 7: Module Installation

### Spec References

- **INSTALLATION-SPECIFICATION** §8 Module Installation (lines 802–824): install_module(), module.json parsing, install.sh, modules_enabled.txt.
- **INSTALLATION-SPECIFICATION** §5 Setup Wizard (lines 451–465): Module selection (LCD Display, iperf3, SNMP, VPN, DNS/DHCP).
- **MODULE-SYSTEM-SPECIFICATION** §3 Module Structure (lines 136–200): module.json, install.sh, dependencies.

### Module Installation Flow

1. User selects modules in wizard (comma-separated numbers)
2. For each selected module: check exists under $INSTALL_DIR/modules/
3. Parse module.json for dependencies (system packages, Python packages)
4. Install dependencies
5. Run module install.sh if present
6. Append module name to $CONFIG_DIR/modules_enabled.txt (or equivalent)

### Idempotency

- If module already in enabled list, skip or re-run install.sh per module contract.

### Todos

- [ ] **phase5-module-install**: Implement `install_module()` and wire to wizard. Support at least one example module (e.g., display_driver) to validate. Handle JSON parsing (jq or Python one-liner). Create modules_enabled.txt or use Module Manager config format.

---

## Deliverable 8: Interactive Setup Wizard (Full)

### Spec References

- **INSTALLATION-SPECIFICATION** §5 Setup Wizard (lines 358–458): All six interactive sections.

### Wizard Sections (in order)

1. **Welcome and Confirmation** (lines 366–394): Banner, system info, estimated time, continue y/n
2. **Remote Access Tool Selection** (lines 398–421): 1–5, or multi-select if 4
3. **WiFi Hotspot Configuration** (lines 416–434): SSID (default RPi-Engineer-[MAC]), password (8–63 chars)
4. **Hostname Configuration** (lines 438–447): Current hostname, optional new
5. **Module Selection** (lines 451–465): Checkboxes/list, comma-separated numbers
6. **Configuration Summary** (lines 469–486): Review all choices, confirm y/n

### Configuration Storage

- Write to `/etc/rpi-engineer/install.conf` (INI format per INSTALLATION-SPECIFICATION §5 lines 490–472)
- Store: version, install_date, hostname, remote tools, hotspot_ssid, hotspot_password_hash, enabled modules

### Todos

- [ ] **phase5-wizard-full**: Implement all six wizard sections with the exact prompts and validation per spec. Store choices in variables, then write install.conf. Validate password length (8–63). Use `hostnamectl set-hostname` for hostname change.

---

## Deliverable 9: Configuration Generation

### Spec References

- **INSTALLATION-SPECIFICATION** §10 Final Configuration (lines 908–959): generate_configs(), system.conf, enable_services().

### Config Files to Generate

- `$CONFIG_DIR/system.conf`: general, network, remote_access, web, logging sections
- Populate from wizard choices and constants

### Todos

- [ ] **phase5-config-gen**: Implement `generate_configs()`. Create system.conf with [general], [network], [remote_access], [web], [logging]. Use wizard values. Implement `enable_services()` to systemctl enable all rpi-engineer* and nginx, hostapd, dnsmasq.

---

## Deliverable 10: Idempotency and Re-run Safety

### Spec References

- **INSTALLATION-SPECIFICATION** §1 Installation Philosophy (lines 26–32): Idempotent, can run multiple times safely.
- **INSTALLATION-SPECIFICATION** §12 Troubleshooting (lines 1038–1042): Debug mode.

### Idempotency Requirements

- Pre-flight: Allow re-run (e.g., skip or update)
- Dependencies: Skip if package already installed
- App install: Backup existing before overwrite, or merge
- Config: Merge or overwrite with confirmation
- Services: Restart if already enabled
- Document: "safe to re-run where specified" per full plan

### Debug Mode

- `DEBUG=1 sudo ./install.sh`: Verbose output, no cleanup on failure, step-by-step confirmation

### Todos

- [ ] **phase5-idempotent**: Add idempotency checks throughout. At start, detect if already installed (e.g., $INSTALL_DIR exists) and offer: "Upgrade/Reconfigure/Abort". For upgrade: skip dir creation, update files. For reconfigure: re-run wizard, regenerate configs. Add DEBUG handling.

---

## Deliverable 11: Post-Installation and Verification

### Spec References

- **INSTALLATION-SPECIFICATION** §10 Post-Installation (lines 963–1006): Summary display, reboot prompt.
- **INSTALLATION-SPECIFICATION** §11 Verification (lines 1010–1056): Post-reboot checks, health check script.
- **DEPLOYMENT-GUIDE** §8 Post-Deployment Verification (lines 374–416): Verification checklist.

### Post-Install Summary (per INSTALLATION-SPECIFICATION §10)

Display:
- Installation Complete banner
- Checklist (deps, app, services, hotspot, remote, modules)
- WiFi SSID, password (masked), web URL (http://192.168.50.1)
- Remote access ID(s)
- Next steps (reboot, connect WiFi, open browser)
- Install log path
- "Press Enter to reboot now, or Ctrl+C to reboot manually later"

### Health Check Script

- Create `$INSTALL_DIR/bin/health-check.sh` (or similar)
- Check: rpi-engineer, rpi-engineer-api, nginx active
- Check: wlan0 has 192.168.50.1
- Check: curl http://localhost/api/v1/system/status succeeds

### Todos

- [ ] **phase5-post-install**: Implement `show_installation_summary()` and `reboot_system()`. Create health-check.sh. Log install to /tmp/rpi-engineer-install-*.log. Prompt for reboot; if user presses Enter, run `reboot`.

---

## Deliverable 12: Verification on Target

### Spec References

- **Full Implementation Plan** Phase 5 Exit Criteria: On clean Ubuntu 22.04+ or Raspberry Pi OS (RPi or compatible), run install and get working system.
- **DEPLOYMENT-GUIDE** §2 Pre-Deployment Checklist, §8 Post-Deployment Verification.

### Verification Steps

1. Start with clean Ubuntu Server 22.04+ or Raspberry Pi OS (VM or RPi)
2. Run: `curl -fsSL [URL]/install.sh | sudo bash` or `sudo ./install.sh` from clone
3. Complete wizard
4. Wait for install to finish
5. Reboot
6. Verify:
   - `systemctl status rpi-engineer` (active)
   - `systemctl status rpi-engineer-api` (active)
   - `systemctl status nginx` (active)
   - Connect to WiFi hotspot, open http://192.168.50.1
   - `curl http://localhost/api/v1/system/status` returns 200
   - Remote access tool shows ID (if installed)

### Todos

- [ ] **phase5-verify**: Run full install on clean Ubuntu 22.04+ or Raspberry Pi OS VM or RPi. Document any deviations. Fix issues until exit criteria met. Update INSTALLATION-SPECIFICATION if behavior differs from spec.

---

## Exit Criteria (from Full Implementation Plan)

1. On a clean Ubuntu Server 22.04+ or Raspberry Pi OS (RPi or compatible), run install command and get a working system.
2. Web UI accessible at http://192.168.50.1 (after connecting to hotspot).
3. Hotspot configured and clients can connect.
4. Remote access tool installed and shows connection ID.
5. Core features (API, serial, capture) reachable via web interface.
6. Install script is idempotent and safe to re-run where specified.

---

## Todo Summary

| ID | Content | Status |
|----|---------|--------|
| phase5-install-deps | Implement dependency installation (apt packages, Python venv, pip) | pending |
| phase5-app-install | Implement application installation (copy files, directories, permissions) | pending |
| phase5-systemd-units | Create systemd units for API gateway and all services | pending |
| phase5-nginx-config | Configure nginx for web UI and API proxy | pending |
| phase5-hotspot-config | Configure hostapd and dnsmasq for WiFi hotspot | pending |
| phase5-remote-access | Implement remote access tool install (AnyDesk/TeamViewer/VNC) | pending |
| phase5-module-install | Implement optional module installation during setup | pending |
| phase5-wizard-full | Complete interactive wizard (all prompts per spec) | pending |
| phase5-config-gen | Generate config files from wizard choices | pending |
| phase5-idempotent | Make install script idempotent and safe to re-run | pending |
| phase5-post-install | Implement post-install summary and reboot prompt | pending |
| phase5-verify | Verify on clean Ubuntu 22.04+ or Raspberry Pi OS (RPi or VM) | pending |

---

## Dependencies and Order

```
phase5-wizard-full (gather all choices)
    │
    ├─▶ phase5-install-deps
    │
    ├─▶ phase5-app-install
    │       │
    │       ├─▶ phase5-systemd-units
    │       ├─▶ phase5-nginx-config
    │       ├─▶ phase5-hotspot-config
    │       ├─▶ phase5-remote-access (uses wizard remote choice)
    │       └─▶ phase5-module-install (uses wizard module choice)
    │
    ├─▶ phase5-config-gen (uses all wizard choices)
    │
    └─▶ phase5-idempotent (applied throughout)
            │
            └─▶ phase5-post-install
                    │
                    └─▶ phase5-verify
```

**Recommended execution order**: wizard-full → install-deps → app-install → (systemd-units, nginx-config, hotspot-config in parallel) → remote-access → module-install → config-gen → post-install → verify. Apply idempotent logic as each deliverable is implemented.

---

## Risks and Notes

- **apt-key deprecation**: AnyDesk install may use `apt-key add`; modern Ubuntu prefers signed-by in sources.list. Check REMOTE-ACCESS-SPECIFICATION for current method.
- **wlan0 may not exist**: On headless RPi without WiFi, wlan0 might not be present. Script should detect and warn; allow skip of hotspot or document USB WiFi dongle requirement.
- **Single large script**: Per full plan risks, consider splitting into sourced steps (e.g., `install-steps/01-deps.sh`, `02-app.sh`) while keeping single `install.sh` entrypoint.
- **Generalize for GitHub**: Use `[organization]` placeholder in REPO_URL; author "chibashr" per user rules. No project-specific IDs in script.

---

## Related Documents

- [.planning/INSTALLATION-SPECIFICATION.md](../.planning/INSTALLATION-SPECIFICATION.md)
- [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md)
- [.planning/DEPLOYMENT-GUIDE.md](../.planning/DEPLOYMENT-GUIDE.md)
- [.planning/REMOTE-ACCESS-SPECIFICATION.md](../.planning/REMOTE-ACCESS-SPECIFICATION.md)
- [.planning/MODULE-SYSTEM-SPECIFICATION.md](../.planning/MODULE-SYSTEM-SPECIFICATION.md)
- [.planning/NETWORK-MANAGEMENT-SPECIFICATION.md](../.planning/NETWORK-MANAGEMENT-SPECIFICATION.md)
- [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md)

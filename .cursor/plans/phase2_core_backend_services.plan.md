---
name: Phase 2 - Core Backend Services
overview: Detailed implementation plan for Phase 2 of RPi Engineer-in-a-Box. Implements System Manager, Network Manager, Remote Access integration, Serial Manager, and Capture Manager per the specification suite. Each sub-phase wires into the API Gateway and replaces stubs.
todos:
  - id: phase2-2a-system
    content: "2a. Implement System Manager service (status, metrics, power, services)"
    status: pending
  - id: phase2-2a-gateway
    content: "2a. Wire System Manager into API Gateway, replace stubs"
    status: pending
  - id: phase2-2b-interfaces
    content: "2b. Implement Network Manager - interface detection and configuration"
    status: pending
  - id: phase2-2b-failover
    content: "2b. Implement Network Manager - failover, hotspot, VLANs, routing"
    status: pending
  - id: phase2-2b-profiles
    content: "2b. Implement Network Manager - profiles, status, wire to gateway"
    status: pending
  - id: phase2-2c-remote
    content: "2c. Implement Remote Access API (status, info) per REMOTE-ACCESS-SPECIFICATION"
    status: pending
  - id: phase2-2d-devices
    content: "2d. Implement Serial Manager - device detection (pyudev), sessions"
    status: pending
  - id: phase2-2d-websocket
    content: "2d. Implement Serial Manager - WebSocket console, logging, wire to gateway"
    status: pending
  - id: phase2-2e-capture
    content: "2e. Implement Capture Manager - tcpdump/tshark, BPF, storage"
    status: pending
  - id: phase2-2e-live
    content: "2e. Implement Capture Manager - live stream WebSocket, wire to gateway"
    status: pending
isProject: false
---

# Phase 2: Core Backend Services – Detailed Plan

This plan expands Phase 2 from [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md). It references the specification suite in [.planning/](../.planning/) and the implementation order in [DEVELOPMENT-GUIDE.md](../.planning/DEVELOPMENT-GUIDE.md). **Execute sub-phases in order: 2a → 2b → 2c → 2d → 2e.**

---

## Document References

| Spec | Path | Phase 2 Relevance |
|------|------|-------------------|
| API-REFERENCE | [.planning/API-REFERENCE.md](../.planning/API-REFERENCE.md) | All endpoints, request/response formats, error codes |
| SYSTEM-ARCHITECTURE | [.planning/SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md) | Service layout, API structure, data flow |
| DEVELOPMENT-GUIDE | [.planning/DEVELOPMENT-GUIDE.md](../.planning/DEVELOPMENT-GUIDE.md) | Implementation order, coding standards |
| NETWORK-MANAGEMENT-SPECIFICATION | [.planning/NETWORK-MANAGEMENT-SPECIFICATION.md](../.planning/NETWORK-MANAGEMENT-SPECIFICATION.md) | 2b – interfaces, failover, hotspot, VLANs, profiles |
| REMOTE-ACCESS-SPECIFICATION | [.planning/REMOTE-ACCESS-SPECIFICATION.md](../.planning/REMOTE-ACCESS-SPECIFICATION.md) | 2c – status, info, connection IDs |
| SERIAL-CONSOLE-SPECIFICATION | [.planning/SERIAL-CONSOLE-SPECIFICATION.md](../.planning/SERIAL-CONSOLE-SPECIFICATION.md) | 2d – devices, sessions, WebSocket, logging |
| PACKET-CAPTURE-SPECIFICATION | [.planning/PACKET-CAPTURE-SPECIFICATION.md](../.planning/PACKET-CAPTURE-SPECIFICATION.md) | 2e – capture lifecycle, BPF, live view, storage |

---

## Phase 2a: System Manager

**Goal**: Implement system status, resource metrics, power control, and service management. Replace API Gateway stubs under `system/`.

**Reference**: [API-REFERENCE.md](../.planning/API-REFERENCE.md) § System API, [SYSTEM-ARCHITECTURE.md](../.planning/SYSTEM-ARCHITECTURE.md) § System Manager Service.

### Deliverables

1. **System Manager service** (`services/system_manager/`)
   - **Status**: `GET /api/v1/system/status` – health, services map, resources (CPU, memory, disk, temperature), uptime
   - **Info**: `GET /api/v1/system/info` – hostname, version, model, OS
   - **Services**: `GET /api/v1/system/services` – list; `POST /api/v1/system/services` – start/stop/restart
   - **Power**: `POST /api/v1/system/power` – shutdown, reboot
   - Use `psutil` for CPU, memory, disk; `/sys/class/thermal/` for temperature; `systemctl` or D-Bus for services; `subprocess` for power

2. **API Gateway integration**
   - Replace stubs in `routes/system.py` with calls to System Manager
   - Ensure response format matches API-REFERENCE (data, meta, timestamps)

### Todos

- [ ] **phase2-2a-system**: Implement System Manager service (status, metrics, power, services)
- [ ] **phase2-2a-gateway**: Wire System Manager into API Gateway, replace stubs

### Exit Criteria

- `GET /api/v1/system/status` returns real data (CPU, memory, disk, temperature)
- `GET /api/v1/system/info` returns hostname, version, model, OS
- Service list and control work; power actions execute (with appropriate safeguards)

---

## Phase 2b: Network Manager

**Goal**: Implement network interface management, failover, hotspot, VLANs, routing, and profiles per [NETWORK-MANAGEMENT-SPECIFICATION.md](../.planning/NETWORK-MANAGEMENT-SPECIFICATION.md).

**Reference**: [API-REFERENCE.md](../.planning/API-REFERENCE.md) § Network API.

### Deliverables

1. **Interface detection and configuration**
   - `GET /api/v1/network/interfaces` – list interfaces (ip/NetworkManager)
   - `GET /api/v1/network/interfaces/{id}` – details
   - `PUT /api/v1/network/interfaces/{id}` – DHCP/static config (mode, ip_address, netmask, gateway, dns)
   - Interface types: usb*, eth0, wlan0; friendly names per spec
   - Hardware info: MAC, driver, link status, speed, MTU

2. **Failover and connectivity**
   - Priority: USB (metric 100) > Ethernet (metric 200)
   - Connectivity test: ping 8.8.8.8 + DNS; every 60s; 3 failures before failover; 5 successes before failback
   - `GET /api/v1/network/status` – wan_interface, wan_status, hotspot_status, last_test

3. **Routing**
   - `GET /api/v1/network/routes` – list
   - `POST /api/v1/network/routes` – add (destination, gateway, interface)

4. **Profiles**
   - `GET /api/v1/network/profiles` – list
   - `POST /api/v1/network/profiles` – save (name, description)
   - `POST /api/v1/network/profiles/{name}/load` – load profile
   - Storage: `/etc/rpi-engineer/network_profiles/` (JSON)

5. **WiFi hotspot**
   - hostapd + dnsmasq; SSID `RPi-Engineer-[last4MAC]`; 192.168.50.1/24; DHCP .10–.100
   - NAT to WAN; WPA2-PSK

6. **VLANs** (Advanced)
   - Create/delete VLAN interfaces (eth0.X); 802.1Q; per-VLAN IP config

### Todos

- [ ] **phase2-2b-interfaces**: Implement Network Manager – interface detection and configuration
- [ ] **phase2-2b-failover**: Implement Network Manager – failover, hotspot, VLANs, routing
- [ ] **phase2-2b-profiles**: Implement Network Manager – profiles, status, wire to gateway

### Exit Criteria

- All network API endpoints return real data
- Failover logic runs; hotspot serves clients; profiles save/load

---

## Phase 2c: Remote Access Integration

**Goal**: Implement `remote/status` and `remote/info` per [REMOTE-ACCESS-SPECIFICATION.md](../.planning/REMOTE-ACCESS-SPECIFICATION.md). No new long-running manager; read from config/CLI.

**Reference**: [API-REFERENCE.md](../.planning/API-REFERENCE.md) § Remote Access API.

### Deliverables

1. **Status endpoint**
   - `GET /api/v1/remote/status`
   - Response: `tools[]` with name, status, connection_id, ready
   - Read from `/etc/rpi-engineer/remote_access.conf` or query CLI:
     - AnyDesk: `anydesk --get-id`
     - TeamViewer: `teamviewer info`
     - VNC: connection string `<ip>:5901`

2. **Info endpoint**
   - `GET /api/v1/remote/info`
   - Response: `connection_ids` map (anydesk, teamviewer, vnc), status
   - Format IDs for display (e.g., `123 456 789`)

3. **API Gateway**
   - Wire `remote/` routes; replace stubs

### Todos

- [ ] **phase2-2c-remote**: Implement Remote Access API (status, info) per REMOTE-ACCESS-SPECIFICATION

### Exit Criteria

- `GET /api/v1/remote/status` and `GET /api/v1/remote/info` return connection IDs when tools are installed

---

## Phase 2d: Serial Manager

**Goal**: Implement serial device management, sessions, WebSocket console, and logging per [SERIAL-CONSOLE-SPECIFICATION.md](../.planning/SERIAL-CONSOLE-SPECIFICATION.md).

**Reference**: [API-REFERENCE.md](../.planning/API-REFERENCE.md) § Serial API, WebSocket API.

### Deliverables

1. **Device management**
   - `GET /api/v1/serial/devices` – list (path, friendly_name, chipset, status, baud_rate)
   - `GET /api/v1/serial/devices/{id}` – details
   - `PUT /api/v1/serial/devices/{id}` – config (friendly_name, baud_rate, data_bits, parity, stop_bits, flow_control)
   - `POST /api/v1/serial/devices/{id}/test` – test connection
   - Detection: pyudev for hotplug; scan `/dev/ttyUSB*`, `/dev/ttyACM*`, `/dev/serial/by-id/*`
   - Chipset DB: FTDI (0x0403), Prolific (0x067b), CH340 (0x1a86)

2. **Session management**
   - `POST /api/v1/serial/sessions` – create (device_id, config) → session_id, websocket_url
   - `GET /api/v1/serial/sessions` – list active
   - `GET /api/v1/serial/sessions/{id}` – details
   - `PUT /api/v1/serial/sessions/{id}` – pause/resume logging
   - `DELETE /api/v1/serial/sessions/{id}` – close
   - Use pyserial; one session per device; max 8 simultaneous

3. **WebSocket console**
   - `WS /ws/serial/{session_id}`
   - Client→Server: `{type: "data", data: "..."}`, `{type: "resize", rows, cols}`, `{type: "control", action: "pause_logging"}`
   - Server→Client: `{type: "data", data: "..."}`, `{type: "status", bytes_tx, bytes_rx}`, `{type: "error", message}`

4. **Logging**
   - `GET /api/v1/serial/logs` – list (device, since, limit)
   - `GET /api/v1/serial/logs/{id}/content` – content
   - `DELETE /api/v1/serial/logs/{id}` – delete
   - `POST /api/v1/serial/logs/export` – export selected
   - Log path: `/opt/rpi-engineer/data/serial_logs/`; format per spec (header, timestamps, direction)

5. **File transfer** (optional for Phase 2)
   - Defer to later if time-constrained; spec supports Raw, XMODEM, YMODEM, ZMODEM

### Todos

- [ ] **phase2-2d-devices**: Implement Serial Manager – device detection (pyudev), sessions
- [ ] **phase2-2d-websocket**: Implement Serial Manager – WebSocket console, logging, wire to gateway

### Exit Criteria

- Devices detected; sessions created; WebSocket bidirectional I/O works; logs written and listable

---

## Phase 2e: Capture Manager

**Goal**: Implement packet capture with tcpdump/tshark, BPF filters, storage, and live stream per [PACKET-CAPTURE-SPECIFICATION.md](../.planning/PACKET-CAPTURE-SPECIFICATION.md).

**Reference**: [API-REFERENCE.md](../.planning/API-REFERENCE.md) § Capture API, WebSocket API.

### Deliverables

1. **Capture lifecycle**
   - `GET /api/v1/capture/interfaces` – list interfaces (from Network Manager or ip)
   - `POST /api/v1/capture/start` – start (interface, filter, duration_seconds, max_size_mb, name)
   - `GET /api/v1/capture/active` – list active
   - `GET /api/v1/capture/active/{id}` – details
   - `POST /api/v1/capture/active/{id}/stop` – stop
   - `GET /api/v1/capture/completed` – list completed (interface, since, limit)
   - `GET /api/v1/capture/completed/{id}` – details
   - `GET /api/v1/capture/completed/{id}/download` – binary PCAP
   - `DELETE /api/v1/capture/completed/{id}` – delete
   - Use tcpdump; BPF filter validation; storage `/opt/rpi-engineer/data/captures/`

2. **Statistics and analysis**
   - `GET /api/v1/capture/{id}/stats` – packet_count, byte_count, duration, protocols, start/end time
   - `GET /api/v1/capture/{id}/packets` – paginated
   - `GET /api/v1/capture/{id}/conversations` – conversations
   - `GET /api/v1/capture/{id}/protocols` – protocol distribution
   - Use tshark for analysis where needed

3. **Live stream**
   - `WS /ws/capture/{capture_id}` – real-time packet stream
   - Tail capture file or pipe; parse PCAP; send JSON to browser
   - Throttle: max batch size, max update frequency

4. **API Gateway**
   - Wire all capture routes; WebSocket endpoint

### Todos

- [ ] **phase2-2e-capture**: Implement Capture Manager – tcpdump/tshark, BPF, storage
- [ ] **phase2-2e-live**: Implement Capture Manager – live stream WebSocket, wire to gateway

### Exit Criteria

- Start/stop captures; BPF filters work; completed captures listable and downloadable; live WebSocket streams packets

---

## Phase 2 Exit Criteria (Overall)

- All core API groups (system, network, serial, capture, remote) implemented and reachable through the gateway
- WebSocket endpoints for serial console and capture live data working
- Stubs replaced with real implementations
- Each sub-phase tested before moving to the next

---

## Execution Order

1. **2a** – System Manager → wire to gateway → test
2. **2b** – Network Manager (interfaces → failover/hotspot → profiles) → wire → test
3. **2c** – Remote Access API → wire → test
4. **2d** – Serial Manager (devices → sessions → WebSocket → logs) → wire → test
5. **2e** – Capture Manager (capture → stats → live) → wire → test

---

## Dependencies and Risks

- **Hardware**: Network (hotspot, failover), serial (USB devices), capture (interfaces) best validated on real RPi + USB hardware
- **CI**: Unit/integration tests with mocks for CI; hardware tests manual or on target
- **Permissions**: Serial needs `dialout`; network config may need root; capture may need cap_net_raw
- **Spec alignment**: Any conflict resolved in favor of the spec; document deviations

---

## Related Plans

- [full_implementation_plan_e49592f8.plan.md](full_implementation_plan_e49592f8.plan.md) – Parent plan
- Phase 3 (Web Interface) depends on Phase 2 completion

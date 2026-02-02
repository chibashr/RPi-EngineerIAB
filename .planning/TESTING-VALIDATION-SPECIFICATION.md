# Testing and Validation Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Overview](#overview)
2. [Unit Testing Requirements](#unit-testing-requirements)
3. [Integration Testing Scenarios](#integration-testing-scenarios)
4. [System Testing Procedures](#system-testing-procedures)
5. [Performance Testing Benchmarks](#performance-testing-benchmarks)
6. [User Acceptance Testing Criteria](#user-acceptance-testing-criteria)
7. [Regression Testing Approach](#regression-testing-approach)
8. [Test Automation Strategy](#test-automation-strategy)
9. [Test Data and Environments](#test-data-and-environments)
10. [Quality Gates](#quality-gates)

---

## Overview

### Purpose

The Testing and Validation specification defines the quality assurance approach for the RPi Engineer-in-a-Box platform. It ensures reliability, performance, and correctness through structured testing at multiple levels.

### Testing Philosophy

**Principles**:
- **Test Early**: Unit tests during development
- **Test Often**: Automated runs on commit/PR
- **Test Realistically**: Integration and system tests on target hardware
- **Document Results**: Clear pass/fail criteria, traceability

**Priority**: Functional correctness first, performance second, edge cases third

### Test Pyramid

```
        ┌─────────┐
        │   E2E   │  Few, critical paths
        │  Tests  │
        ├─────────┤
        │Integration│  Moderate, key interactions
        │  Tests   │
        ├─────────┤
        │  Unit   │  Many, fast, isolated
        │  Tests  │
        └─────────┘
```

---

## Unit Testing Requirements

### Scope

**Backend (Python)**:
- All public functions in services
- Utility functions in lib/
- Configuration parsing
- Data validation logic
- Error handling paths

**Exclusions**:
- Trivial getters/setters
- Pure wrappers around system calls (mock at integration)
- Third-party library code

### Framework

**Python**: pytest
- Fixtures for common setup
- Parametrized tests for multiple inputs
- Mocking: unittest.mock or pytest-mock

**Coverage Target**: 70% minimum for service code, 80% for lib/

### Test Structure

**Location**: `tests/unit/` mirroring source structure

```
tests/
├── unit/
│   ├── services/
│   │   ├── test_network_manager.py
│   │   ├── test_serial_manager.py
│   │   └── ...
│   └── lib/
│       └── test_utils.py
```

**Naming**: `test_<function_or_feature>_<scenario>`

**Example**:
```python
def test_validate_ip_address_valid():
    assert validate_ip_address("192.168.1.1") == True

def test_validate_ip_address_invalid():
    assert validate_ip_address("not.an.ip") == False

def test_validate_ip_address_empty_raises():
    with pytest.raises(ValueError):
        validate_ip_address("")
```

### Mocking Guidelines

**Mock**:
- External system calls (subprocess, file I/O for non-test)
- Network requests
- Hardware access (serial, USB)
- Time-dependent logic (freeze time)

**Do Not Mock**:
- Pure logic (test with real implementation)
- Simple data structures

### Running Unit Tests

```bash
pytest tests/unit/ -v --cov=services --cov=lib --cov-report=term-missing
```

---

## Integration Testing Scenarios

### Scope

**Service-to-Service**:
- API Gateway → Manager services
- Module Manager → Module loading
- Update Manager → Backup/Restore

**Service-to-System**:
- Network Manager → systemd-networkd/NetworkManager
- Serial Manager → /dev/ttyUSB* (with mock device or loopback)
- Capture Manager → tcpdump (with test interface)

### Framework

**Python**: pytest with integration markers

```python
@pytest.mark.integration
def test_api_returns_network_interfaces():
    response = client.get("/api/v1/network/interfaces")
    assert response.status_code == 200
    assert "interfaces" in response.json()
```

### Key Integration Scenarios

**Network**:
- Interface list retrieval
- Configuration apply (with rollback)
- Failover trigger (simulated)
- Profile save/load

**Serial**:
- Device enumeration (mock udev)
- Session create/close
- WebSocket data flow (with mock serial)

**Capture**:
- Start/stop capture (loopback interface)
- Filter application
- File creation and metadata

**System**:
- Service status aggregation
- Health check response
- Update check (mock git)

### Test Environment

**Requirements**:
- Linux environment (Ubuntu 22.04+ or Raspberry Pi OS preferred)
- Some tests require root (network, capture)
- Mock or loopback for hardware-dependent tests

**Docker** (Optional):
- Container with Ubuntu for CI
- Privileged mode for network tests
- Serial: Use socat or similar for virtual serial pair

---

## System Testing Procedures

### Scope

**Full Stack**:
- Web interface → API → Services → System
- Real hardware where applicable
- End-to-end user workflows

### Test Environment

**Target Hardware**: Raspberry Pi 4 (minimum), Pi 5 preferred

**Setup**:
- Fresh Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+)
- Install via install script
- USB serial adapter (for serial tests)
- Ethernet and WiFi available

### System Test Scenarios

**Installation**:
1. Run install script on fresh system
2. Verify all services start
3. Access web interface via hotspot
4. Verify default configuration

**Network**:
1. Connect USB jetpack (or simulate with USB Ethernet)
2. Verify WAN detection and routing
3. Connect to hotspot from phone/laptop
4. Verify internet access through device
5. Test failover (disconnect primary)

**Serial Console**:
1. Connect USB-to-serial adapter
2. Open console from web interface
3. Verify terminal display
4. Send/receive data (loopback or connected device)
5. Verify logging
6. Test file transfer (if supported)

**Packet Capture**:
1. Start capture on eth0 or loopback
2. Generate traffic
3. Stop capture
4. Verify file created
5. Download and open in Wireshark
6. Test live view

**Remote Access**:
1. Verify AnyDesk/TeamViewer starts
2. Retrieve connection ID from web interface
3. Connect from remote machine
4. Verify full desktop access

**Update**:
1. Create test update (new version)
2. Run update check
3. Apply update
4. Verify new version
5. Test rollback (simulate failure)

### Manual Test Checklist

**Pre-Release**:
- [ ] Fresh install on RPi 3B+
- [ ] Fresh install on RPi 4
- [ ] Fresh install on RPi 5
- [ ] Upgrade from previous version
- [ ] All features in Simple mode
- [ ] All features in Advanced mode
- [ ] Mobile browser (phone)
- [ ] Desktop browser (Chrome, Firefox, Safari)

---

## Performance Testing Benchmarks

### Key Metrics

**Web Interface**:
- Initial load: <3 seconds on RPi 4
- Page navigation: <1 second
- API response: <200ms for typical endpoints

**Serial Console**:
- Keystroke to echo latency: <50ms
- Throughput: Full baud rate (e.g., 115200) without loss

**Packet Capture**:
- Capture rate: 100k+ pps on RPi 4 (Gigabit)
- Live view latency: <500ms
- No packet loss at line rate (or documented limit)

**System**:
- Boot to web-accessible: <2 minutes
- Service start: <10 seconds each
- Memory: <512MB for application services

### Performance Test Approach

**Tools**:
- Browser DevTools (load time, network)
- Custom scripts for latency measurement
- iperf3 for network throughput
- stress-ng for CPU load testing

**Scenarios**:
- Baseline: Idle system metrics
- Load: 4 serial sessions + 1 capture + web active
- Stress: Maximum sessions, verify no crash

### Benchmark Documentation

**Location**: `docs/performance/` or in test results

**Format**: Document baseline for each release, track trends

---

## User Acceptance Testing Criteria

### UAT Scope

**Primary Use Cases** (from PROJECT-OVERVIEW):
1. Remote network troubleshooting
2. On-site packet capture
3. Serial console access
4. Pre-deployment configuration

### Acceptance Criteria

**Use Case 1 - Remote Troubleshooting**:
- [ ] Technician can deploy device in <15 minutes
- [ ] Engineer can connect remotely within 5 minutes of deployment
- [ ] Serial console accessible for all connected devices
- [ ] Packet capture works for troubleshooting
- [ ] No data loss during session

**Use Case 2 - On-Site Packet Capture**:
- [ ] User connects to WiFi with phone
- [ ] Opens web interface, starts capture with 3 clicks
- [ ] Downloads capture file successfully
- [ ] File opens in Wireshark

**Use Case 3 - Serial Console**:
- [ ] Multiple USB serial devices detected
- [ ] Console opens for each device
- [ ] Commands sent and received correctly
- [ ] Logs saved and downloadable
- [ ] File transfer works (XMODEM)

**Use Case 4 - Pre-Deployment**:
- [ ] Save network profile
- [ ] Export configuration
- [ ] Import on second device
- [ ] Both devices work with imported config

### UAT Process

1. Define test scenarios from use cases
2. Execute with target user role (engineer, technician)
3. Document issues and feedback
4. Sign-off when criteria met
5. Track deferred items

---

## Regression Testing Approach

### Trigger

**Regression Run When**:
- Before each release
- After major refactoring
- Weekly (if active development)
- On critical path changes

### Scope

**Full Regression**:
- All unit tests
- All integration tests
- Core system tests
- Smoke test of each feature

**Targeted Regression**:
- Tests for changed module
- Tests for dependent modules
- Related integration tests

### Test Selection

**Impact Analysis**:
- Identify changed files
- Map to affected tests
- Run minimal set for quick feedback
- Full suite for release

### Baseline

**Establish Baseline**:
- Known-good version
- All tests pass
- Document environment
- Use as comparison for regression

---

## Test Automation Strategy

### CI Pipeline

**On Commit/PR**:
1. Lint (flake8, black check)
2. Unit tests (fast, no hardware)
3. Report coverage
4. Fail if coverage drops

**On Merge to Main**:
1. Full unit tests
2. Integration tests (if environment available)
3. Build/package if applicable
4. Deploy to test environment (optional)

### CI Tools

**Options**:
- GitHub Actions
- GitLab CI
- Jenkins
- Local: pre-commit hooks

**Example (GitHub Actions)**:
```yaml
- run: pip install -r requirements-dev.txt
- run: pytest tests/unit/ -v --cov --cov-fail-under=70
```

### Test Markers

```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.hardware  # Requires real hardware
```

**Run Subset**:
```bash
pytest -m unit          # Unit only
pytest -m "not slow"    # Exclude slow
pytest -m "not hardware"  # Exclude hardware-dependent
```

### Flaky Tests

**Policy**: Fix or quarantine flaky tests promptly

**Identification**: Track failures in CI, rerun to confirm

**Quarantine**: Mark with @pytest.mark.skip(reason="Flaky - issue #123") temporarily

---

## Test Data and Environments

### Test Data

**Network**:
- Sample network profiles (JSON)
- Valid/invalid IP configurations
- VLAN configurations

**Serial**:
- Sample session logs
- Test scripts for loopback

**Capture**:
- Small PCAP files for validation
- BPF filter test cases

**Storage**: `tests/fixtures/` or `tests/data/`

### Environment Variables

**Test Config**:
```
RPI_ENGINEER_TEST_MODE=1
RPI_ENGINEER_TEST_DB=:memory:  # or test.db
RPI_ENGINEER_MOCK_HARDWARE=1
```

### Cleanup

**After Tests**:
- Restore original configuration
- Clean temporary files
- Reset database if used
- No side effects on host system

---

## Quality Gates

### Pre-Commit

- [ ] Code passes lint
- [ ] No new critical issues
- [ ] Unit tests pass

### Pre-Merge

- [ ] All unit tests pass
- [ ] Coverage maintained or improved
- [ ] No known high-severity bugs in changed area
- [ ] Code review approved

### Pre-Release

- [ ] Full test suite passes
- [ ] System tests on target hardware pass
- [ ] UAT criteria met
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Changelog updated

### Release Blockers

- Any critical bug
- Security vulnerability
- Data loss scenario
- Install failure on supported hardware

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | chibashr | Initial testing and validation specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- INSTALLATION-SPECIFICATION.md
- All feature specifications (for test scenarios)
- LOGGING-MONITORING-SPECIFICATION.md

# Installation Specification

## Document Information
- **Project**: RPi Engineer-in-a-Box
- **Version**: 1.0.0
- **Date**: February 2026
- **Status**: Draft Specification

---

## Table of Contents
1. [Installation Overview](#installation-overview)
2. [Prerequisites](#prerequisites)
3. [Installation Methods](#installation-methods)
4. [Installation Script](#installation-script)
5. [Setup Wizard](#setup-wizard)
6. [Post-Installation](#post-installation)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

---

## Installation Overview

### Installation Philosophy

The installation process follows these principles:
1. **One-Command Install**: Single command to run installation
2. **Minimal User Input**: Only essential questions during setup
3. **Idempotent**: Can be run multiple times safely
4. **Self-Documenting**: Clear progress indicators and error messages
5. **Fail-Safe**: Validates prerequisites before making changes

### Installation Flow

```
┌─────────────────────────┐
│ Fresh Debian-based OS   │
│ (Ubuntu or RPi OS)      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Download Install Script │
│ curl -fsSL ...          │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Run Installation Script │
│ sudo ./install.sh       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Pre-Flight Checks       │
│ - OS compatibility      │
│ - Hardware detection    │
│ - Network access        │
│ - Disk space            │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Interactive Setup       │
│ - Remote access tool    │
│ - WiFi hotspot password │
│ - Hostname              │
│ - Module selection      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ System Dependencies     │
│ - Update packages       │
│ - Install required      │
│   packages              │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Application Install     │
│ - Copy files            │
│ - Create directories    │
│ - Set permissions       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Service Configuration   │
│ - Create systemd units  │
│ - Configure network     │
│ - Set up hotspot        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Module Installation     │
│ - Install selected      │
│   modules               │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Remote Access Setup     │
│ - Install selected tool │
│ - Configure unattended  │
│   access                │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Final Configuration     │
│ - Generate configs      │
│ - Enable services       │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Installation Complete   │
│ - Display summary       │
│ - Prompt for reboot     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ System Reboot           │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Services Start          │
│ - All services enabled  │
│ - Web interface active  │
└─────────────────────────┘
```

### Installation Time
- **Estimated Duration**: 10-15 minutes
- **Network dependent**: Package downloads
- **User interaction**: 2-3 minutes for questions

---

## Prerequisites

### Hardware Requirements

#### Minimum
- **Device**: Raspberry Pi 3B+, 4, or 5
- **RAM**: 1GB (2GB+ recommended)
- **Storage**: 16GB microSD card (32GB+ recommended)
- **Power**: USB power supply or battery pack (2.5A minimum)

#### Recommended
- **Device**: Raspberry Pi 4 (4GB+) or Raspberry Pi 5
- **RAM**: 4GB or more
- **Storage**: 32GB+ microSD card (Class 10, UHS-I)
- **Power**: Official Raspberry Pi power supply or quality USB-C PD

#### Peripheral
- **USB Cellular Modem**: Verizon Jetpack or compatible
- **USB-to-Serial Adapters**: FTDI or Prolific chipset recommended
- **Ethernet Cable**: For local network connection
- **Optional**: USB keyboard and HDMI cable for initial setup

### Software Requirements

#### Operating System
- **Supported**: Ubuntu Server 22.04 LTS or 24.04 LTS, or Raspberry Pi OS (Debian Bookworm or later)
- **Architecture**: 64-bit ARM (aarch64)
- **Installation**: Minimal/Standard installation (not full)

#### Network Access During Installation
- **Internet Connection**: Required for package downloads
- **Bandwidth**: ~500MB download for all packages
- **Can use**: Ethernet or WiFi (will be reconfigured after installation)

#### User Permissions
- **Root Access**: Required (via sudo)
- **User Account**: Standard user account with sudo privileges

### Pre-Installation Checklist

```
□ Raspberry Pi 3B+, 4, or 5
□ Ubuntu Server 22.04+ or Raspberry Pi OS (Bookworm+) installed
□ microSD card with at least 8GB free space
□ Internet connection active (Ethernet or WiFi)
□ Power supply connected
□ sudo access available
□ Know desired WiFi hotspot password
□ Decided on remote access tool (AnyDesk/TeamViewer/VNC/Raspberry Pi Connect)
□ Optional: list of modules to install
```

---

## Installation Methods

### Method 1: One-Line Install (Recommended)

**Command**:
```bash
curl -fsSL https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install.sh | sudo bash
```

**Advantages**:
- Simplest method
- Always gets latest version
- No manual download

**Disadvantages**:
- Requires trust in remote script
- Needs internet connection

### Method 2: Download and Run

**Commands**:
```bash
wget https://raw.githubusercontent.com/chibashr/RPi-EngineerIAB/main/bin/install.sh
chmod +x install.sh
sudo ./install.sh
```

**Advantages**:
- Can inspect script before running
- Can save for offline installation
- More control

**Disadvantages**:
- Extra steps

### Method 3: Git Clone (Development)

**Commands**:
```bash
git clone https://github.com/[organization]/rpi-engineer.git
cd rpi-engineer
sudo ./install.sh
```

**Advantages**:
- Full source access
- Can modify before installation
- Useful for development

**Disadvantages**:
- Largest download
- More steps

---

## Installation Script

### Script Structure

```bash
#!/bin/bash
#
# RPi Engineer-in-a-Box Installation Script
# Version: 1.0.0
#
# This script installs and configures RPi Engineer-in-a-Box
# on a fresh Ubuntu Server or Raspberry Pi OS installation.
#

# Script Sections:
# 1. Constants and Configuration
# 2. Utility Functions
# 3. Pre-Flight Checks
# 4. Interactive Setup
# 5. Dependency Installation
# 6. Application Installation
# 7. Service Configuration
# 8. Module Installation
# 9. Remote Access Setup
# 10. Final Configuration
# 11. Post-Installation

set -e  # Exit on error
set -u  # Exit on undefined variable
```

### Phase 1 (Foundation) Scope

During Phase 1, the installation script is a **framework only**:

- Includes constants, logging helpers, and pre-flight checks
- Prompts for remote access tool, hotspot password, and hostname
- Executes placeholder stages for dependencies, app install, services, modules, and remote access
- **Does not** perform system changes yet (no packages, files, or services are modified)

The Phase 1 script lives at `bin/install.sh` in the development repo.

### Constants and Configuration

```bash
# Installation directories
INSTALL_DIR="/opt/rpi-engineer"
CONFIG_DIR="/etc/rpi-engineer"
DATA_DIR="/var/lib/rpi-engineer"
LOG_DIR="/var/log/rpi-engineer"

# Service user
SERVICE_USER="rpi-engineer"
SERVICE_GROUP="rpi-engineer"

# Versions
VERSION="1.0.0"
MIN_UBUNTU_VERSION="22.04"
MIN_DEBIAN_VERSION="12"  # Bookworm (Raspberry Pi OS)

# Network defaults
DEFAULT_HOTSPOT_SSID_PREFIX="RPi-Engineer"
DEFAULT_HOTSPOT_IP="192.168.50.1"
DEFAULT_HOTSPOT_DHCP_START="192.168.50.10"
DEFAULT_HOTSPOT_DHCP_END="192.168.50.100"

# Repository
REPO_URL="https://github.com/[organization]/rpi-engineer.git"
BRANCH="main"

# Log file
INSTALL_LOG="/tmp/rpi-engineer-install-$(date +%Y%m%d-%H%M%S).log"
```

### Utility Functions

```bash
# Logging functions
log_info() {
    echo -e "\e[32m[INFO]\e[0m $1" | tee -a "$INSTALL_LOG"
}

log_warn() {
    echo -e "\e[33m[WARN]\e[0m $1" | tee -a "$INSTALL_LOG"
}

log_error() {
    echo -e "\e[31m[ERROR]\e[0m $1" | tee -a "$INSTALL_LOG"
}

log_step() {
    echo -e "\e[36m[STEP]\e[0m $1" | tee -a "$INSTALL_LOG"
}

# Progress indicator
show_progress() {
    local message="$1"
    echo -n "$message... " | tee -a "$INSTALL_LOG"
}

progress_done() {
    echo -e "\e[32m✓\e[0m" | tee -a "$INSTALL_LOG"
}

progress_fail() {
    echo -e "\e[31m✗\e[0m" | tee -a "$INSTALL_LOG"
}

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Detect OS and version
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "Cannot detect OS version"
        exit 1
    fi
}

# Check OS compatibility (Ubuntu or Raspberry Pi OS / Debian)
check_os_compatibility() {
    case "$OS" in
        ubuntu)
            if ! dpkg --compare-versions "$VER" ge "$MIN_UBUNTU_VERSION"; then
                log_error "Ubuntu version $VER is not supported (min $MIN_UBUNTU_VERSION)"
                exit 1
            fi
            ;;
        debian|raspbian)
            if [ -n "${VERSION_CODENAME:-}" ]; then
                case "$VERSION_CODENAME" in
                    bookworm|trixie) : ;;
                    *) log_error "Debian $VERSION_CODENAME not supported (Bookworm+ required)"; exit 1 ;;
                esac
            elif ! dpkg --compare-versions "$VER" ge "12"; then
                log_error "Debian $VER not supported (Bookworm/12+ required)"
                exit 1
            fi
            ;;
        *)
            log_error "Unsupported OS: $OS. Supported: Ubuntu 22.04+ or Raspberry Pi OS (Bookworm+)."
            exit 1
            ;;
    esac
}

# Detect Raspberry Pi model
detect_rpi() {
    local model=""
    if [ -f /proc/device-tree/model ]; then
        model=$(cat /proc/device-tree/model)
        log_info "Detected: $model"
        
        # Check if supported model
        if echo "$model" | grep -qE "Raspberry Pi (3 Model B Plus|4|5)"; then
            return 0
        else
            log_warn "Unsupported Raspberry Pi model: $model"
            log_warn "Supported models: 3B+, 4, 5"
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        log_warn "Cannot detect Raspberry Pi model"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Check disk space
check_disk_space() {
    local required_mb=8192  # 8GB
    local available_mb=$(df / | tail -1 | awk '{print $4}')
    local available_mb=$((available_mb / 1024))
    
    if [ "$available_mb" -lt "$required_mb" ]; then
        log_error "Insufficient disk space"
        log_error "Required: ${required_mb}MB, Available: ${available_mb}MB"
        exit 1
    fi
}

# Check internet connectivity
check_internet() {
    if ! ping -c 1 -W 5 8.8.8.8 > /dev/null 2>&1; then
        log_error "No internet connectivity"
        log_error "Internet is required for package downloads"
        exit 1
    fi
}
```

### Pre-Flight Checks

```bash
run_preflight_checks() {
    log_step "Running pre-flight checks"
    
    show_progress "Checking root privileges"
    check_root
    progress_done
    
    show_progress "Detecting OS"
    detect_os
    progress_done
    
    show_progress "Checking OS compatibility"
    check_os_compatibility
    progress_done
    
    show_progress "Detecting Raspberry Pi model"
    detect_rpi
    progress_done
    
    show_progress "Checking disk space"
    check_disk_space
    progress_done
    
    show_progress "Checking internet connectivity"
    check_internet
    progress_done
    
    log_info "All pre-flight checks passed"
}
```

---

## Setup Wizard

### Interactive Questions

#### 1. Welcome and Confirmation

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║           RPi Engineer-in-a-Box Installation                   ║
║                    Version 1.0.0                               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

This script will install RPi Engineer-in-a-Box on your system.

System Information:
  OS: Ubuntu 22.04 LTS / Raspberry Pi OS Bookworm
  Model: Raspberry Pi 4 Model B
  RAM: 4GB
  Storage: 32GB available

This installation will:
  • Install system dependencies
  • Configure network interfaces
  • Set up WiFi hotspot
  • Install selected remote access tool
  • Install selected modules
  • Configure systemd services

Estimated time: 10-15 minutes

Do you want to continue? (y/n):
```

#### 2. Remote Access Tool Selection

```
╔════════════════════════════════════════════════════════════════╗
║                  Remote Access Configuration                   ║
╚════════════════════════════════════════════════════════════════╝

Select the remote access tool you want to install:

  1) AnyDesk (Recommended)
  2) TeamViewer
  3) TigerVNC
  4) Raspberry Pi Connect (Raspberry Pi OS only)
  5) Install multiple (select after)
  6) Skip (install manually later)

Enter your choice (1-6):
```

If option 5 selected:
```
Select tools to install (comma-separated, e.g., 1,2):
  1) AnyDesk
  2) TeamViewer
  3) TigerVNC
  4) Raspberry Pi Connect (Raspberry Pi OS only)

Enter your choices:
```

#### 3. WiFi Hotspot Configuration

```
╔════════════════════════════════════════════════════════════════╗
║                  WiFi Hotspot Configuration                    ║
╚════════════════════════════════════════════════════════════════╝

Configure the WiFi hotspot for local access.

MAC Address Last 4 Digits: A1B2
Default SSID: RPi-Engineer-A1B2

Press Enter to use default, or type custom SSID:
```

```
Enter WiFi hotspot password (8-63 characters):
Confirm password:
```

#### 4. Hostname Configuration

```
╔════════════════════════════════════════════════════════════════╗
║                    Hostname Configuration                      ║
╚════════════════════════════════════════════════════════════════╝

Current hostname: ubuntu

Enter new hostname (or press Enter to keep current):
```

#### 5. Module Selection

```
╔════════════════════════════════════════════════════════════════╗
║                     Module Selection                           ║
╚════════════════════════════════════════════════════════════════╝

Select optional modules to install:

  [ ] 1. LCD/OLED Display Driver
  [ ] 2. Bandwidth Testing (iperf3)
  [ ] 3. SNMP Monitoring
  [ ] 4. VPN Client Support
  [ ] 5. DNS/DHCP Server

Enter module numbers to install (comma-separated, e.g., 1,2,5)
Or press Enter to skip:
```

#### 6. Configuration Summary

```
╔════════════════════════════════════════════════════════════════╗
║                   Configuration Summary                        ║
╚════════════════════════════════════════════════════════════════╝

Installation Configuration:
  
  Remote Access: AnyDesk
  WiFi SSID: RPi-Engineer-A1B2
  WiFi Password: ********
  Hostname: rpi-field-01
  Modules: LCD Display Driver
  
Is this correct? (y/n):
```

### Configuration Storage

All setup choices are stored in:
```
/etc/rpi-engineer/install.conf
```

Format:
```ini
[general]
version=1.0.0
install_date=2026-02-01T10:30:00Z
hostname=rpi-field-01

[remote_access]
tools=anydesk

[network]
hotspot_ssid=RPi-Engineer-A1B2
hotspot_password_hash=<bcrypt_hash>

[modules]
enabled=display_driver
```

---

## Dependency Installation

### System Package Updates

```bash
install_system_dependencies() {
    log_step "Installing system dependencies"
    
    show_progress "Updating package lists"
    apt-get update >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Upgrading existing packages"
    apt-get upgrade -y >> "$INSTALL_LOG" 2>&1
    progress_done
}
```

### Required Packages

```bash
install_required_packages() {
    log_step "Installing required packages"
    
    local packages=(
        # Python
        "python3"
        "python3-pip"
        "python3-venv"
        
        # Web server
        "nginx"
        
        # Network tools
        "network-manager"
        "dnsmasq"
        "hostapd"
        "iptables"
        "bridge-utils"
        "vlan"
        
        # Serial tools
        "cu"
        "minicom"
        "screen"
        
        # Packet capture
        "tcpdump"
        "tshark"
        "wireshark-common"
        
        # System tools
        "git"
        "curl"
        "wget"
        "jq"
        "bc"
        "lsof"
        
        # USB tools
        "usbutils"
        "usb-modeswitch"
        "usb-modeswitch-data"
        
        # Build tools (for Python packages)
        "build-essential"
        "python3-dev"
        
        # SSL/TLS
        "openssl"
        "ca-certificates"
    )
    
    for package in "${packages[@]}"; do
        show_progress "Installing $package"
        apt-get install -y "$package" >> "$INSTALL_LOG" 2>&1
        progress_done
    done
}
```

### Python Dependencies

```bash
install_python_dependencies() {
    log_step "Installing Python dependencies"
    
    show_progress "Creating virtual environment"
    python3 -m venv "$INSTALL_DIR/venv" >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Installing Python packages"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip >> "$INSTALL_LOG" 2>&1
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" >> "$INSTALL_LOG" 2>&1
    progress_done
}
```

**requirements.txt**:
```
Flask==3.0.0
Flask-SocketIO==5.3.5
pyserial==3.5
scapy==2.5.0
psutil==5.9.6
pyudev==0.24.1
python-iptables==1.0.1
netifaces==0.11.0
requests==2.31.0
pyyaml==6.0.1
python-dotenv==1.0.0
werkzeug==3.0.1
eventlet==0.34.0
```

---

## Application Installation

### Directory Creation

```bash
create_directories() {
    log_step "Creating directory structure"
    
    local directories=(
        "$INSTALL_DIR"
        "$INSTALL_DIR/bin"
        "$INSTALL_DIR/services"
        "$INSTALL_DIR/web"
        "$INSTALL_DIR/modules"
        "$INSTALL_DIR/lib"
        "$CONFIG_DIR"
        "$CONFIG_DIR/network_profiles"
        "$CONFIG_DIR/module_config"
        "$DATA_DIR"
        "$DATA_DIR/captures"
        "$DATA_DIR/serial_logs"
        "$DATA_DIR/backups"
        "$DATA_DIR/database"
        "$LOG_DIR"
    )
    
    for dir in "${directories[@]}"; do
        show_progress "Creating $dir"
        mkdir -p "$dir"
        progress_done
    done
}
```

### File Deployment

```bash
deploy_files() {
    log_step "Deploying application files"
    
    show_progress "Copying service files"
    cp -r services/* "$INSTALL_DIR/services/"
    progress_done
    
    show_progress "Copying web files"
    cp -r web/* "$INSTALL_DIR/web/"
    progress_done
    
    show_progress "Copying library files"
    cp -r lib/* "$INSTALL_DIR/lib/"
    progress_done
    
    show_progress "Copying binary scripts"
    cp -r bin/* "$INSTALL_DIR/bin/"
    chmod +x "$INSTALL_DIR/bin/"*
    progress_done
}
```

### User and Permissions

```bash
setup_user_permissions() {
    log_step "Setting up user and permissions"
    
    show_progress "Creating service user"
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d "$INSTALL_DIR" "$SERVICE_USER"
    fi
    progress_done
    
    show_progress "Setting file ownership"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
    chown -R "$SERVICE_USER:$SERVICE_GROUP" "$LOG_DIR"
    progress_done
    
    show_progress "Setting file permissions"
    chmod 755 "$INSTALL_DIR"
    chmod 640 "$CONFIG_DIR/"*
    chmod 750 "$INSTALL_DIR/bin/"*
    progress_done
    
    show_progress "Adding service user to groups"
    usermod -a -G dialout "$SERVICE_USER"  # Serial port access
    usermod -a -G netdev "$SERVICE_USER"   # Network access
    progress_done
}
```

---

## Service Configuration

### systemd Service Units

#### Master Service

```bash
create_master_service() {
    cat > /etc/systemd/system/rpi-engineer.service <<EOF
[Unit]
Description=RPi Engineer-in-a-Box Master Service
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_DIR/bin/start.sh
ExecStop=$INSTALL_DIR/bin/stop.sh
RemainAfterExit=yes
User=root

[Install]
WantedBy=multi-user.target
EOF
}
```

#### Individual Services

Services created for each component:
- rpi-engineer-api.service
- rpi-engineer-network.service
- rpi-engineer-serial.service
- rpi-engineer-capture.service
- rpi-engineer-system.service
- rpi-engineer-monitor.service
- rpi-engineer-update.service
- rpi-engineer-logging.service

### Network Configuration

#### WiFi Hotspot Setup

```bash
configure_hotspot() {
    log_step "Configuring WiFi hotspot"
    
    # Get MAC address
    local mac=$(cat /sys/class/net/wlan0/address | sed 's/://g' | tail -c 5)
    local ssid="${HOTSPOT_SSID:-$DEFAULT_HOTSPOT_SSID_PREFIX-$mac}"
    
    # hostapd configuration
    cat > /etc/hostapd/hostapd.conf <<EOF
interface=wlan0
driver=nl80211
ssid=$ssid
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$HOTSPOT_PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF

    # dnsmasq configuration
    cat > /etc/dnsmasq.d/rpi-engineer.conf <<EOF
interface=wlan0
dhcp-range=$DEFAULT_HOTSPOT_DHCP_START,$DEFAULT_HOTSPOT_DHCP_END,255.255.255.0,24h
domain=local
address=/rpi-engineer.local/$DEFAULT_HOTSPOT_IP
EOF

    # Network interface configuration
    cat > /etc/network/interfaces.d/wlan0 <<EOF
auto wlan0
iface wlan0 inet static
    address $DEFAULT_HOTSPOT_IP
    netmask 255.255.255.0
EOF

    progress_done
}
```

#### Network Priority Script

```bash
create_network_priority_script() {
    cat > "$INSTALL_DIR/bin/network-priority.sh" <<'EOF'
#!/bin/bash
# Network Priority and Failover Script

test_connectivity() {
    local interface=$1
    ping -c 3 -W 5 -I "$interface" 8.8.8.8 > /dev/null 2>&1 && \
    nslookup google.com | grep -q "Address" > /dev/null 2>&1
}

# Test USB interfaces first
for iface in /sys/class/net/usb*; do
    if [ -e "$iface" ]; then
        iface_name=$(basename "$iface")
        if test_connectivity "$iface_name"; then
            ip route replace default dev "$iface_name" metric 100
            exit 0
        fi
    fi
done

# Test ethernet
if test_connectivity eth0; then
    ip route replace default dev eth0 metric 200
    exit 0
fi

# No WAN connectivity
logger -t rpi-engineer "No WAN connectivity available"
exit 1
EOF

    chmod +x "$INSTALL_DIR/bin/network-priority.sh"
}
```

### nginx Configuration

```bash
configure_nginx() {
    log_step "Configuring nginx"
    
    cat > /etc/nginx/sites-available/rpi-engineer <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    root /opt/rpi-engineer/web;
    index index.html;
    
    # Static files
    location / {
        try_files $uri $uri/ =404;
    }
    
    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    # WebSocket
    location /ws/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/rpi-engineer /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    
    nginx -t && systemctl restart nginx
    progress_done
}
```

---

## Module Installation

### Module Installation Function

```bash
install_module() {
    local module_name=$1
    log_info "Installing module: $module_name"
    
    # Check if module exists
    if [ ! -d "$INSTALL_DIR/modules/$module_name" ]; then
        log_error "Module not found: $module_name"
        return 1
    fi
    
    # Check dependencies
    if [ -f "$INSTALL_DIR/modules/$module_name/module.json" ]; then
        # Parse and install dependencies
        # (Implement JSON parsing and dependency installation)
        :
    fi
    
    # Run module install script if exists
    if [ -f "$INSTALL_DIR/modules/$module_name/install.sh" ]; then
        bash "$INSTALL_DIR/modules/$module_name/install.sh"
    fi
    
    # Register module
    echo "$module_name" >> "$CONFIG_DIR/modules_enabled.txt"
    
    log_info "Module installed: $module_name"
}
```

---

## Remote Access Setup

### AnyDesk Installation

```bash
install_anydesk() {
    log_step "Installing AnyDesk"
    
    show_progress "Adding AnyDesk repository"
    wget -qO - https://keys.anydesk.com/repos/DEB-GPG-KEY | apt-key add -
    echo "deb http://deb.anydesk.com/ all main" > /etc/apt/sources.list.d/anydesk-stable.list
    apt-get update >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Installing AnyDesk"
    apt-get install -y anydesk >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Configuring unattended access"
    echo "password" | anydesk --set-password
    anydesk --get-id > "$CONFIG_DIR/anydesk_id.txt"
    progress_done
    
    show_progress "Enabling AnyDesk service"
    systemctl enable anydesk
    systemctl start anydesk
    progress_done
}
```

### TeamViewer Installation

```bash
install_teamviewer() {
    log_step "Installing TeamViewer"
    
    show_progress "Downloading TeamViewer"
    wget -O /tmp/teamviewer.deb https://download.teamviewer.com/download/linux/teamviewer-host_arm64.deb >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Installing TeamViewer"
    apt-get install -y /tmp/teamviewer.deb >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Configuring TeamViewer"
    teamviewer setup
    teamviewer passwd [password]
    teamviewer info > "$CONFIG_DIR/teamviewer_id.txt"
    progress_done
    
    show_progress "Enabling TeamViewer service"
    systemctl enable teamviewerd
    systemctl start teamviewerd
    progress_done
}
```

### VNC Installation

```bash
install_vnc() {
    log_step "Installing TigerVNC"
    
    show_progress "Installing VNC server"
    apt-get install -y tigervnc-standalone-server tigervnc-common >> "$INSTALL_LOG" 2>&1
    progress_done
    
    show_progress "Configuring VNC"
    mkdir -p /home/"$SERVICE_USER"/.vnc
    echo "password" | vncpasswd -f > /home/"$SERVICE_USER"/.vnc/passwd
    chmod 600 /home/"$SERVICE_USER"/.vnc/passwd
    progress_done
    
    show_progress "Creating VNC service"
    # Create systemd service for VNC
    progress_done
}
```

---

## Final Configuration

### Generate Configuration Files

```bash
generate_configs() {
    log_step "Generating configuration files"
    
    # Main configuration
    cat > "$CONFIG_DIR/system.conf" <<EOF
[general]
version=$VERSION
install_date=$(date -Iseconds)
hostname=$(hostname)

[network]
hotspot_enabled=true
hotspot_ssid=$HOTSPOT_SSID
hotspot_ip=$DEFAULT_HOTSPOT_IP
priority_1=usb
priority_2=ethernet

[remote_access]
tools=$REMOTE_TOOLS

[web]
port=80
mode=simple

[logging]
level=INFO
retention_days=7
EOF

    progress_done
}
```

### Enable Services

```bash
enable_services() {
    log_step "Enabling services"
    
    local services=(
        "rpi-engineer"
        "rpi-engineer-api"
        "rpi-engineer-network"
        "nginx"
        "hostapd"
        "dnsmasq"
    )
    
    for service in "${services[@]}"; do
        show_progress "Enabling $service"
        systemctl enable "$service" >> "$INSTALL_LOG" 2>&1
        progress_done
    done
}
```

---

## Post-Installation

### Installation Summary

```
╔════════════════════════════════════════════════════════════════╗
║                  Installation Complete!                        ║
╚════════════════════════════════════════════════════════════════╝

Installation Summary:
  ✓ System dependencies installed
  ✓ Application files deployed
  ✓ Services configured
  ✓ WiFi hotspot configured
  ✓ Remote access configured
  ✓ Modules installed

System Information:
  WiFi SSID: RPi-Engineer-A1B2
  WiFi Password: ********
  Web Interface: http://192.168.50.1 (after connecting to WiFi)
  
Remote Access:
  AnyDesk ID: 123456789
  
Next Steps:
  1. Reboot the system: sudo reboot
  2. After reboot, connect to WiFi: RPi-Engineer-A1B2
  3. Open web browser to: http://192.168.50.1
  4. Complete initial setup

Installation log saved to: /tmp/rpi-engineer-install-20260201-103000.log

Press Enter to reboot now, or Ctrl+C to reboot manually later...
```

### Reboot

```bash
reboot_system() {
    read -p "Press Enter to reboot now..."
    reboot
}
```

---

## Verification

### Post-Reboot Verification

After system reboots, verify:

```bash
# Check all services are running
systemctl status rpi-engineer
systemctl status rpi-engineer-api
systemctl status nginx

# Check network interfaces
ip addr show wlan0
ip addr show eth0

# Check WiFi hotspot
iw dev wlan0 info

# Check remote access
# AnyDesk
anydesk --get-status

# Check web interface
curl http://localhost/api/v1/system/status

# Check logs
tail -f /var/log/rpi-engineer/api_gateway.log
```

### Health Check Script

```bash
#!/bin/bash
# Post-installation health check

echo "RPi Engineer-in-a-Box Health Check"
echo "===================================="

# Services
echo "Services:"
systemctl is-active rpi-engineer && echo "  ✓ Main service" || echo "  ✗ Main service"
systemctl is-active rpi-engineer-api && echo "  ✓ API service" || echo "  ✗ API service"
systemctl is-active nginx && echo "  ✓ Web server" || echo "  ✗ Web server"

# Network
echo "Network:"
ip addr show wlan0 | grep -q "192.168.50.1" && echo "  ✓ WiFi hotspot" || echo "  ✗ WiFi hotspot"

# Web interface
echo "Web Interface:"
curl -s http://localhost/api/v1/system/status > /dev/null && echo "  ✓ API responding" || echo "  ✗ API not responding"

echo "===================================="
```

---

## Troubleshooting

### Common Issues

#### Issue: Installation fails during package installation

**Symptoms**: apt-get errors during dependency installation

**Solutions**:
1. Check internet connection
2. Update package lists: `sudo apt-get update`
3. Check disk space: `df -h`
4. Review installation log

#### Issue: WiFi hotspot not starting

**Symptoms**: Cannot see WiFi network after reboot

**Solutions**:
1. Check hostapd status: `sudo systemctl status hostapd`
2. Check dnsmasq status: `sudo systemctl status dnsmasq`
3. Verify wlan0 interface: `ip addr show wlan0`
4. Check hostapd config: `sudo hostapd -dd /etc/hostapd/hostapd.conf`

#### Issue: Web interface not accessible

**Symptoms**: Cannot connect to http://192.168.50.1

**Solutions**:
1. Check nginx status: `sudo systemctl status nginx`
2. Check API service: `sudo systemctl status rpi-engineer-api`
3. Verify firewall rules: `sudo iptables -L`
4. Check nginx logs: `sudo tail -f /var/log/nginx/error.log`

#### Issue: Remote access not working

**Symptoms**: Cannot connect via AnyDesk/TeamViewer

**Solutions**:
1. Check service status: `sudo systemctl status anydesk`
2. Verify internet connection
3. Check connection ID: `anydesk --get-id`
4. Review remote access logs

### Debug Mode

Run installation in debug mode:
```bash
DEBUG=1 sudo ./install.sh
```

This enables:
- Verbose output
- Detailed logging
- No cleanup on failure
- Step-by-step confirmation

### Log Locations

- Installation log: `/tmp/rpi-engineer-install-*.log`
- Service logs: `/var/log/rpi-engineer/`
- System logs: `journalctl -u rpi-engineer*`
- nginx logs: `/var/log/nginx/`

### Getting Help

1. Review installation log
2. Run health check script
3. Check service status
4. Review documentation at http://192.168.50.1/docs
5. Submit issue with logs

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | February 2026 | System Architect | Initial installation specification |

## Related Documents
- PROJECT-OVERVIEW.md
- SYSTEM-ARCHITECTURE.md
- WEB-INTERFACE-SPECIFICATION.md
- NETWORK-MANAGEMENT-SPECIFICATION.md
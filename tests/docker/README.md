# Installer Docker Test

Tests the RPi Engineer-in-a-Box installer in an Ubuntu 22.04 container.

## Prerequisites

- Docker Desktop running
- Project checked out

## Run

```bash
# From project root
docker build -f tests/docker/Dockerfile.install-test -t rpi-engineer-install-test .
docker run --rm -it \
  -v "$(pwd):/workspace:ro" \
  -e NONINTERACTIVE=1 \
  -e DEBIAN_FRONTEND=noninteractive \
  rpi-engineer-install-test \
  /bin/bash -c "cd /workspace && NONINTERACTIVE=1 bash bin/install.sh"
```

On Windows PowerShell (omit `-it` when running from script/CI):
```powershell
docker run --rm -v "${PWD}:/workspace:ro" -e NONINTERACTIVE=1 -e DEBIAN_FRONTEND=noninteractive rpi-engineer-install-test /bin/bash -c "cd /workspace && NONINTERACTIVE=1 bash bin/install.sh"
```

## What NONINTERACTIVE=1 does

- Skips all wizard prompts; uses defaults
- Uses DEBIAN_FRONTEND=noninteractive for apt (no debconf prompts)
- Skips reboot at end
- Firewall is skipped when running in a container

## Debugging

To get a shell and run the installer manually:
```bash
docker run --rm -it -v "$(pwd):/workspace:ro" rpi-engineer-install-test /bin/bash
# Inside container:
cd /workspace
NONINTERACTIVE=1 bash bin/install.sh
```

Check the install log: `/tmp/rpi-engineer-install-*.log`

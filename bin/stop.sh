#!/usr/bin/env bash

set -euo pipefail

services=(
  rpi-engineer-logging
  rpi-engineer-update
  rpi-engineer-monitor
  rpi-engineer-system
  rpi-engineer-capture
  rpi-engineer-serial
  rpi-engineer-network
  rpi-engineer-api
)

for service in "${services[@]}"; do
  systemctl stop "$service"
done

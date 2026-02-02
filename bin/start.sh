#!/usr/bin/env bash

set -euo pipefail

services=(
  rpi-engineer-api
  rpi-engineer-network
  rpi-engineer-serial
  rpi-engineer-capture
  rpi-engineer-system
  rpi-engineer-monitor
  rpi-engineer-update
  rpi-engineer-logging
)

for service in "${services[@]}"; do
  systemctl start "$service"
done

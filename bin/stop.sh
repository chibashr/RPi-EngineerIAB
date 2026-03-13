#!/usr/bin/env bash

set -euo pipefail

# Only stop actual daemon services (services with main loops).
# system_manager, serial_manager, capture_manager, update_manager, and
# monitor_service are libraries used by the API gateway, not standalone daemons.
services=(
  rpi-engineer-logging
  rpi-engineer-network
  rpi-engineer-api
)

for service in "${services[@]}"; do
  systemctl stop "$service"
done

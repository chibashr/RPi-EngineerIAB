#!/usr/bin/env bash

set -euo pipefail

# Only start actual daemon services (services with main loops).
# system_manager, serial_manager, capture_manager, update_manager, and
# monitor_service are libraries used by the API gateway, not standalone daemons.
services=(
  rpi-engineer-api
  rpi-engineer-network
  rpi-engineer-logging
)

for service in "${services[@]}"; do
  systemctl start "$service"
done

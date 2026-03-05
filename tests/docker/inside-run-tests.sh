#!/usr/bin/env bash

cd /workspace

export RPI_ENGINEER_DRY_RUN=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

if [ -f "requirements.txt" ]; then
  python3 -m pip install --upgrade pip
  python3 -m pip install -r requirements.txt
fi

if [ -f "requirements-dev.txt" ]; then
  python3 -m pip install -r requirements-dev.txt
fi

if [ -f "package.json" ]; then
  if [ -f "package-lock.json" ]; then
    npm ci
  else
    npm install
  fi
  # Ensure Jest's jsdom environment is available even if devDependencies are skipped.
  npm install --no-save jest-environment-jsdom@^30.2.0 >/dev/null 2>&1 || true
fi

pytest "$@"

NODE_OPTIONS="--experimental-vm-modules" npx jest


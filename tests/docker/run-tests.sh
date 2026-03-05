#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

IMAGE_NAME="rpi-engineer-test:latest"

docker build -f tests/docker/Dockerfile.test -t "$IMAGE_NAME" .

docker run --rm \
  -v "$PWD":/workspace \
  -w /workspace \
  "$IMAGE_NAME" \
  bash -lc $'sed -i "s/\\r$//" tests/docker/inside-run-tests.sh && bash tests/docker/inside-run-tests.sh'


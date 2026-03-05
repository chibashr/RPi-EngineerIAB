#!/usr/bin/env bash
set -euo pipefail

# Run fast JS-level tests for the serial web console inside Docker.
# Uses the existing installer test image as the base environment.
#
# Usage:
#   bin/test-serial-js.sh
#
# The script will:
#   - Build tests/docker/Dockerfile.install-test (if the image is missing)
#   - Start a container with the repo mounted at /workspace
#   - Install Node.js + Jest inside the container (if not already present)
#   - Create a minimal Jest config for web/js/tests
#   - Run: jest web/js/tests/serial.test.mjs

IMAGE_NAME="${RPI_EIAB_TEST_IMAGE:-rpi-eiab-install-test}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Using Docker image: ${IMAGE_NAME}"

if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Docker image ${IMAGE_NAME} not found. Building from tests/docker/Dockerfile.install-test..."
  docker build -f "${REPO_ROOT}/tests/docker/Dockerfile.install-test" -t "${IMAGE_NAME}" "${REPO_ROOT}"
fi

docker run --rm -it \
  -v "${REPO_ROOT}:/workspace" \
  -w /workspace \
  "${IMAGE_NAME}" \
  bash -lc '
set -eu

echo "Running serial JS tests inside container..."

if ! command -v node >/dev/null 2>&1; then
  echo "Installing Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get update
  apt-get install -y nodejs
fi

if [ ! -f package.json ]; then
  echo "Initializing npm package.json..."
  npm init -y >/dev/null 2>&1
fi

echo "Installing Jest + jsdom test environment (if needed)..."
npm install --save-dev jest @jest/globals jest-environment-jsdom

if [ ! -f jest.config.mjs ]; then
  cat > jest.config.mjs <<EOF
export default {
  testEnvironment: "jsdom",
  roots: ["<rootDir>/web/js/tests"],
  transform: {},
  extensionsToTreatAsEsm: [".mjs"],
};
EOF
fi

echo "Running Jest serial tests (ESM mode)..."
NODE_OPTIONS=--experimental-vm-modules npx jest web/js/tests/serial.test.mjs
'


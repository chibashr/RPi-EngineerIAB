#!/bin/bash
# Run installer test in Docker. Usage: ./run-install-test.sh [--build]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE="rpi-engineer-install-test"
CONTAINER="rpi-engineer-install-test-$$"

cd "$REPO_ROOT"

if [[ "$1" == "--build" ]]; then
    docker build -f tests/docker/Dockerfile.install-test -t "$IMAGE" .
fi

# Run with -it for interactive (remove -it when no TTY, e.g. CI)
# NONINTERACTIVE=1 skips prompts; DEBIAN_FRONTEND=noninteractive for apt
docker run --rm \
    -v "$REPO_ROOT:/workspace:ro" \
    -e NONINTERACTIVE=1 \
    -e DEBIAN_FRONTEND=noninteractive \
    "$IMAGE" \
    /bin/bash -c "cd /workspace && NONINTERACTIVE=1 bash bin/install.sh"

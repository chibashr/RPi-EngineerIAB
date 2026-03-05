Param(
    [string]$ImageName = "rpi-eiab-install-test"
)

$ErrorActionPreference = "Stop"

# Resolve repo root based on this script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

Write-Host "Using Docker image: $ImageName"

try {
    docker image inspect $ImageName *>$null
} catch {
    Write-Host "Docker image $ImageName not found. Building from tests/docker/Dockerfile.install-test..."
    docker build -f (Join-Path $RepoRoot "tests/docker/Dockerfile.install-test") -t $ImageName $RepoRoot
}

$innerScript = @'
cd /workspace
echo "Running Jest serial tests (ESM mode)..."
NODE_OPTIONS=--experimental-vm-modules npx jest web/js/tests/serial.test.mjs
'@

docker run --rm -it `
  -v "${RepoRoot}:/workspace" `
  -w /workspace `
  $ImageName `
  bash -lc "$innerScript"


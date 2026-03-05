Param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Args
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
Set-Location $repoRoot

$imageName = "rpi-engineer-test:latest"

docker build -f tests/docker/Dockerfile.test -t $imageName .

docker run --rm `
  -v "${PWD}:/workspace" `
  -w /workspace `
  $imageName `
  bash `
  -lc `
  "sed -i 's/\r$//' tests/docker/inside-run-tests.sh && bash tests/docker/inside-run-tests.sh"


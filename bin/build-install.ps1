# Concatenate bin/install-src/*.sh into bin/install.sh. Run before commit.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $scriptDir "install.sh"
$srcDir = Join-Path $scriptDir "install-src"

$header = @"
#!/usr/bin/env bash
# Auto-generated from bin/install-src/*.sh. Do not edit directly.

"@

$content = $header
$files = Get-ChildItem (Join-Path $srcDir "*.sh") | Sort-Object Name
foreach ($f in $files) {
    $lines = Get-Content $f.FullName
    # Skip first line (shebang)
    if ($lines.Count -gt 1) {
        $content += ($lines[1..($lines.Count-1)] -join "`n") + "`n"
    }
}

[System.IO.File]::WriteAllText($out, $content)
Write-Host "Built $out"

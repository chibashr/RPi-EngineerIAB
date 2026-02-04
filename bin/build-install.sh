#!/usr/bin/env bash
# Concatenate bin/install-src/*.sh into bin/install.sh. Run before commit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${SCRIPT_DIR}/install.sh"

{
    echo "#!/usr/bin/env bash"
    echo "# Auto-generated from bin/install-src/*.sh. Do not edit directly."
    echo ""
    for f in "${SCRIPT_DIR}/install-src/"*.sh; do
        tail -n +2 "$f"
    done
} > "$OUT"

chmod +x "$OUT"
echo "Built ${OUT}"

"""
Audit logging: append JSON-lines to data/audit.log.
Adds timestamp (ISO 8601 UTC). Never raises.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_AUDIT_LOG = "data/audit.log"
_AUDIT_LOG_ENV = "RPI_ENGINEER_AUDIT_LOG"


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "config").is_dir() and (p / "AGENTS.md").exists():
            return p
        p = p.parent
    return Path.cwd()


def audit_log(event: dict) -> None:
    """Append one JSON line to data/audit.log. Adds timestamp. Never raises."""
    try:
        event = dict(event)
        event["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        path = Path(os.environ[_AUDIT_LOG_ENV]) if _AUDIT_LOG_ENV in os.environ else _repo_root() / _AUDIT_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, default=str) + "\n"
        with open(path, "a") as f:
            f.write(line)
    except Exception as e:
        print(e, file=sys.stderr)

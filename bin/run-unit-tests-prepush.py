#!/usr/bin/env python3
"""Run unit tests with a temp auth config so pre-push does not modify config/auth.conf."""

import os
import subprocess
import sys
import tempfile


def main() -> int:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as auth_path:
        auth_path.close()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".audit.log", delete=False) as audit_path:
        audit_path.close()
    try:
        os.environ["RPI_ENGINEER_AUTH_CONF"] = auth_path.name
        os.environ["RPI_ENGINEER_AUDIT_LOG"] = audit_path.name
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/unit/",
                "-x",
                "-q",
                "--tb=line",
                "-m",
                "not slow",
                "-p",
                "no:cacheprovider",
            ],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))) or ".",
        )
    finally:
        for p in (auth_path.name, audit_path.name):
            try:
                os.unlink(p)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())

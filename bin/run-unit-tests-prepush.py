#!/usr/bin/env python3
"""Run unit tests with a temp auth config so pre-push does not modify config/auth.conf."""

import os
import subprocess
import sys
import tempfile


def main() -> int:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
        path = f.name
    try:
        os.environ["RPI_ENGINEER_AUTH_CONF"] = path
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
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())

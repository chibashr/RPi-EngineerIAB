# Known Issues (MEDIUM — Do Not Block)

<!-- Generated: 2026-03-06 | Review: Final verification -->

## Static Analysis

| Issue | Severity | Notes |
|-------|----------|-------|
| ruff not installed | MEDIUM | Add `ruff` to requirements-dev.txt for lint; CI may use alternative (flake8/pylint). |
| mypy not configured | MEDIUM | Optional; add pyproject.toml [tool.mypy] if type checking desired. |

## Code

| Issue | Severity | Notes |
|-------|----------|-------|
| print() in tests/scripts/test_serial_connection.py | MEDIUM | CLI helper script; print is acceptable for user-facing output. |
| Flask references in conftest.py comments | MEDIUM | Historical; TestClient is FastAPI/Starlette compatible. |

## Tests

| Issue | Severity | Notes |
|-------|----------|-------|
| 10 skipped tests (serial_websocket, api_gateway) | MEDIUM | Require live serial hardware or live server; acceptable for CI. |

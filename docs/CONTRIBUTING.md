# Contributing to RPi Engineer-in-a-Box

## Development environment setup

- **Prerequisites**: Git, Python 3.10+, optional Docker for isolated testing. See [Development Guide](.planning/DEVELOPMENT-GUIDE.md) for full setup.
- **Install**: Clone repo, create venv, install deps:
  ```bash
  python3 -m venv venv
  source venv/bin/activate   # or venv\Scripts\activate on Windows
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```
- **System packages** (Ubuntu / Raspberry Pi OS): iproute2, net-tools, tcpdump, tshark, python3-serial, libudev-dev; `pip install pyudev` if needed.

## Available scripts

<!-- AUTO-GENERATED from package.json - do not edit this table manually -->

| Command | Description |
|---------|-------------|
| `npm test` | Placeholder (no test specified; use pytest for Python tests) |

**Python / tests**: Run from repo root:
- `pytest tests/unit/ -v` — unit tests
- `pytest tests/unit/ -v --cov=services` — unit tests with coverage
- `pytest tests/integration/ -v -m integration` — integration tests
- `python -m uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 5000` — run API gateway (default http://0.0.0.0:5000)

<!-- END AUTO-GENERATED -->

## Testing

- **Unit**: `pytest tests/unit/ -v`
- **Coverage**: `pytest tests/unit/ -v --cov=services`
- **Integration**: `pytest tests/integration/ -v -m integration`
- **Manual API**: e.g. `curl http://localhost:5000/api/v1/system/status` or `curl http://localhost:5000/health`
- Use fixtures in `tests/fixtures/`; mock hardware for CI.

## Code style

- **Formatter**: Black (line length 100)
- **Linter**: flake8, pylint, or ruff
- **Type hints** for public APIs. Naming: snake_case files/functions, PascalCase classes, UPPER_SNAKE constants.

## PR workflow

1. Branch from `main` (e.g. `feature/xxx`, `fix/xxx`).
2. Implement with tests; run full test suite.
3. Update documentation if needed.
4. Submit PR; address review; merge after approval.
5. Commit messages: `feat:`, `fix:`, `docs:` prefix.

## Related

- [Development Guide](.planning/DEVELOPMENT-GUIDE.md) — detailed setup, running locally, debugging
- [Specification suite](.planning/README.md) — specs and roadmap

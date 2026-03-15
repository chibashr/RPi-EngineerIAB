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
| `npm test` | Run Jest test suite (NODE_OPTIONS experimental-vm-modules) |
| `npm run test:watch` | Jest in watch mode |
| `npm run test:coverage` | Jest with coverage |
| `npm run test:ci` | Jest CI mode (ci, coverage, default reporters) |
| `npm run test:all` | Python pytest + Jest |
| `npm run test:py` | pytest tests/ -v |
| `npm run test:py:unit` | pytest tests/unit/ -v -m 'not slow' |
| `npm run test:py:integration` | pytest tests/integration/ -v |
| `npm run test:py:coverage` | pytest with --cov=services,lib and term-missing report |
| `npm run lint` | Echo: run ruff check (pip install ruff) |
| `npm run lint:fix` | Echo: run ruff check --fix |

**API (repo root):** `python -m uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 5000`

**Bin scripts (install/deploy):** `bin/install.sh`, `bin/start.sh`, `bin/stop.sh`, `bin/apply-update.sh`, `bin/install-src/*.sh`. See [Installation Specification](.planning/INSTALLATION-SPECIFICATION.md).

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

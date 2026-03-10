# Dependencies

<!-- Generated: 2026-03-10 | Docs: ENV.md, RUNBOOK.md synced | Token estimate: ~400 -->

## External Services

- **Git (remote)**: Update manager uses `git ls-remote` and `git clone` for update check and apply. Requires git clone deploy.
- **Optional**: AnyDesk, TeamViewer, VNC, or Raspberry Pi Connect (remote_access_manager); not in Python deps.

## Third-Party Python (requirements.txt)

| Package | Purpose |
|---------|---------|
| fastapi | API gateway |
| uvicorn[standard] | ASGI server |
| python-multipart | Form/file uploads |
| websockets | WebSocket support |
| psutil | System info |
| pyserial | Serial devices |
| pyudev | USB device detection |

## Dev (requirements-dev.txt)

- pytest — unit/integration tests
- pytest-timeout — test timeouts
- httpx — async HTTP client for tests
- beautifulsoup4 — HTML parsing (e.g. tests)

## Shared Libraries (lib/)

- `lib/common.py` — shared helpers
- `lib/module_logger.py` — get_service_logger
- `lib/api_client.py` — API client utilities
- `lib/utils.py` — utilities

## System Dependencies (install / dev)

- iproute2, net-tools (network)
- tcpdump, tshark (capture)
- python3-serial, libudev-dev (serial/USB)
- Git (for updates and install from repo)

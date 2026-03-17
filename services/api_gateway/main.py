"""RPi Engineer-in-a-Box API Gateway (FastAPI)."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, Response

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from lib.module_logger import get_service_logger  # noqa: E402
from services.api_gateway.limiter import limiter  # noqa: E402
from services.api_gateway.middleware.request_logger import RequestLoggerMiddleware  # noqa: E402
from services.api_gateway.response import success_response  # noqa: E402
from services.api_gateway.routes import register_routes  # noqa: E402
from services.api_gateway.websockets import register_websockets  # noqa: E402
from services.module_manager import module_manager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cleanup modules on shutdown. Route registration happens in create_app before mount."""
    # Re-apply hotspot share rules on startup (persists across reboot; iptables rules are lost on reboot)
    try:
        from services.network_manager import NetworkManager

        nm = NetworkManager()
        if nm._get_share_interfaces():
            nm._apply_hotspot_share()
    except Exception:
        pass
    yield
    module_manager.cleanup()


def create_app() -> FastAPI:
    web_root = REPO_ROOT / "web"
    app = FastAPI(title="RPi Engineer API Gateway", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS: localhost, LAN (192.168.x, 10.x, 172.16-31.x). Scope /api/*, /ws/* preserved via same origins.
    _cors_regex = (
        r"^http://(127\.0\.0\.1|localhost|192\.168\.\d+\.\d+|"
        r"10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_cors_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggerMiddleware)

    # Security headers middleware
    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next) -> Response:
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            # default-src: fallback for unspecified resource types; script-src: JS sources;
            # style-src: CSS (unsafe-inline for inline styles); img-src: images + data URIs;
            # connect-src: fetch/XHR/WS (wss: for WebSockets); frame-ancestors: no embedding;
            # form-action: forms may only submit to same origin
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; connect-src 'self' wss:; frame-ancestors 'none'; form-action 'self';"
            )
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    # Shared status queue for system, network, and modules
    import asyncio

    status_queue: asyncio.Queue[dict] = asyncio.Queue()
    app.state.status_queue = status_queue

    # 1. Register core routes
    register_routes(app)

    # 2. Discover and initialize modules (includes module API + module websockets)
    module_manager.discover_and_initialize(app, status_queue)

    # 3. Register core websockets (/ws/status, /ws/updates/apply)
    register_websockets(app, status_queue=status_queue)

    # Module asset route (before static mount)
    @app.get("/modules/{module_id}/{asset_path:path}")
    def module_asset(module_id: str, asset_path: str):
        from fastapi import HTTPException

        asset = module_manager.resolve_web_asset(module_id, asset_path)
        if not asset:
            raise HTTPException(status_code=404)
        return FileResponse(asset)

    @app.get("/health")
    def health_check():
        return success_response({"status": "healthy"})

    # Static files: / and /advanced/ served via StaticFiles with html=True
    # Mount after explicit routes so /health, /api/*, /ws/*, /modules/* take precedence
    app.mount("/", StaticFiles(directory=str(web_root), html=True), name="web")

    return app


app = create_app()


if __name__ == "__main__":
    import configparser
    import socket
    import struct
    import threading

    try:
        import fcntl
    except ImportError:
        fcntl = None

    import uvicorn

    def _get_interface_ip(ifname: str) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if fcntl is None:
            raise RuntimeError("fcntl not available (Unix only)")
        return socket.inet_ntoa(
            fcntl.ioctl(
                s.fileno(),
                0x8915,
                struct.pack("256s", ifname[:15].encode()),
            )[20:24]
        )

    cfg = configparser.ConfigParser()
    cfg.read(REPO_ROOT / "config" / "network.conf")
    hotspot_if = cfg.get("DEFAULT", "hotspot_interface", fallback="wlan0")
    bind_lan = cfg.getboolean("DEFAULT", "bind_lan_interface", fallback=False)

    cert_file = REPO_ROOT / "config" / "tls" / "cert.pem"
    key_file = REPO_ROOT / "config" / "tls" / "key.pem"
    if not cert_file.exists() or not key_file.exists():
        print(
            "ERROR: TLS certificates missing. Run bin/install.sh first.",
            file=sys.stderr,
        )
        sys.exit(1)

    ssl_kwargs = {
        "ssl_keyfile": str(key_file),
        "ssl_certfile": str(cert_file),
    }

    try:
        hotspot_ip = _get_interface_ip(hotspot_if)
    except Exception as e:
        print(
            f"ERROR: Cannot resolve IP for {hotspot_if}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    bind_ips = [hotspot_ip]
    if bind_lan:
        try:
            bind_ips.append(_get_interface_ip("eth0"))
        except Exception as e:
            print(f"WARNING: Cannot bind to eth0: {e}", file=sys.stderr)

    logger = get_service_logger("services.api_gateway.main")
    port = 5000
    if len(bind_ips) == 1:
        logger.info("API Gateway starting on %s:%s (uvicorn TLS)", bind_ips[0], port)
        uvicorn.run(app, host=bind_ips[0], port=port, **ssl_kwargs)
    else:
        logger.info(
            "API Gateway starting on %s (uvicorn TLS, %d interfaces)",
            bind_ips,
            len(bind_ips),
        )
        threads = [
            threading.Thread(
                target=uvicorn.run,
                kwargs={"app": app, "host": ip, "port": port, **ssl_kwargs},
                daemon=True,
            )
            for ip in bind_ips
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

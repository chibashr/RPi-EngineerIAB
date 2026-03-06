"""RPi Engineer-in-a-Box API Gateway (FastAPI)."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse
from starlette.responses import Response

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from lib.module_logger import get_service_logger  # noqa: E402
from services.api_gateway.middleware.request_logger import RequestLoggerMiddleware  # noqa: E402
from services.api_gateway.response import success_response  # noqa: E402
from services.api_gateway.routes import register_routes  # noqa: E402
from services.api_gateway.websockets import register_websockets  # noqa: E402
from services.module_manager import module_manager  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cleanup modules on shutdown. Route registration happens in create_app before mount."""
    yield
    module_manager.cleanup()


def create_app() -> FastAPI:
    web_root = REPO_ROOT / "web"
    app = FastAPI(title="RPi Engineer API Gateway", lifespan=lifespan)

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
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'"
            )
            return response

    app.add_middleware(SecurityHeadersMiddleware)

    register_routes(app)
    register_websockets(app)

    # Module routes must be registered before StaticFiles mount (catch-all)
    module_manager.discover_and_register(app)

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
    import uvicorn

    logger = get_service_logger("services.api_gateway.main")
    host = os.getenv("RPI_ENGINEER_API_HOST", "0.0.0.0")
    port = int(os.getenv("RPI_ENGINEER_API_PORT", "5000"))
    logger.info("API Gateway starting on %s:%s (uvicorn)", host, port)
    uvicorn.run(app, host=host, port=port)

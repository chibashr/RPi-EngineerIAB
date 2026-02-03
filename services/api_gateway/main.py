"""RPi Engineer-in-a-Box API Gateway (Phase 1 skeleton)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask
from flask_sock import Sock
from flask_cors import CORS

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from services.api_gateway.response import success_response  # noqa: E402
from services.api_gateway.routes import register_routes  # noqa: E402
from services.api_gateway.websockets import register_websockets  # noqa: E402
from services.module_manager import module_manager  # noqa: E402


def create_app() -> Flask:
    web_root = REPO_ROOT / "web"
    # Disable default static route so /modules/<id>/<path> is handled by our route,
    # not by a catch-all that would 404 for module assets. We serve web/ explicitly below.
    app = Flask(__name__, static_folder=None)
    sock = Sock(app)

    # Register module asset route first so it is never shadowed by the web catch-all.
    @app.get("/modules/<module_id>/<path:asset_path>")
    def module_asset(module_id: str, asset_path: str):
        from flask import abort, send_file

        asset = module_manager.resolve_web_asset(module_id, asset_path)
        if not asset:
            abort(404)
        return send_file(asset)

    # Allow local and LAN access: hotspot (192.168.50.x), other LAN subnets, localhost.
    # Supports non-internet LANs and access from the Pi itself.
    _cors_origins = [
        r"http://127\.0\.0\.1(:\d+)?$",
        r"http://localhost(:\d+)?$",
        r"http://192\.168\.\d+\.\d+(:\d+)?$",
        r"http://10\.\d+\.\d+\.\d+(:\d+)?$",
        r"http://172\.(1[6-9]|2\d|3[01])\.\d+\.\d+(:\d+)?$",
    ]
    CORS(
        app,
        resources={
            r"/api/*": {"origins": _cors_origins},
            r"/ws/*": {"origins": _cors_origins},
        },
    )

    register_routes(app)
    register_websockets(sock)

    @app.after_request
    def add_security_headers(response):
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

    @app.get("/health")
    def health_check():
        return success_response({"status": "healthy"})

    @app.get("/")
    def serve_simple_index():
        """Serve simple mode index at root."""
        from flask import send_file

        return send_file(web_root / "index.html")

    @app.get("/advanced/")
    @app.get("/advanced")
    def serve_advanced_index():
        """Serve advanced mode index at /advanced/."""
        from flask import send_file

        return send_file(web_root / "advanced" / "index.html")

    @app.get("/<path:path>")
    def serve_web_asset(path: str):
        """Serve files from web/ (CSS, JS, HTML). Registered after /modules/ so module assets use that route."""
        from flask import send_file

        if path.startswith("modules/"):
            from flask import abort

            abort(404)
        target = (web_root / path).resolve()
        if not str(target).startswith(str(web_root.resolve())):
            from flask import abort

            abort(404)
        if not target.is_file():
            from flask import abort

            abort(404)
        return send_file(target)

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("RPI_ENGINEER_API_HOST", "0.0.0.0")
    port = int(os.getenv("RPI_ENGINEER_API_PORT", "5000"))
    debug = os.getenv("RPI_ENGINEER_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)

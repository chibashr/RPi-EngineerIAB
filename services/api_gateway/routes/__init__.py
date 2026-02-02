"""API route registrations for the gateway."""

from flask import abort, send_file

from services.module_manager import module_manager

from .backup import backup_bp
from .capture import capture_bp
from .logs import logs_bp
from .modules import modules_bp
from .network import network_bp
from .remote import remote_bp
from .serial import serial_bp
from .system import system_bp
from .updates import updates_bp


def register_routes(app) -> None:
    """Register all API group blueprints on the Flask app."""
    app.register_blueprint(system_bp)
    app.register_blueprint(network_bp)
    app.register_blueprint(serial_bp)
    app.register_blueprint(capture_bp)
    app.register_blueprint(updates_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(remote_bp)
    module_manager.register_module_routes(app)

    @app.get("/modules/<module_id>/<path:asset_path>")
    def module_asset(module_id: str, asset_path: str):
        asset = module_manager.resolve_web_asset(module_id, asset_path)
        if not asset:
            abort(404)
        return send_file(asset)

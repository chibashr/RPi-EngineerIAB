"""Shared logging helper for modules and services to ensure consistent log format.

Modules and services should use these helpers instead of Python's standard logging
module to ensure logs follow the RPi Engineer-in-a-Box format:
    YYYY-MM-DD HH:MM:SS,mmm LEVEL [name] message

Example (module):
    from lib.module_logger import get_module_logger
    logger = get_module_logger(__name__)

Example (service):
    from lib.module_logger import get_service_logger
    logger = get_service_logger(__name__)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _get_log_dir() -> Path:
    """Get the log directory, creating fallback if needed."""
    repo_root = Path(__file__).resolve().parents[1]
    log_dir_env = os.getenv("RPI_ENGINEER_LOG_DIR", "/var/log/rpi-engineer")
    log_dir = Path(log_dir_env)
    if not log_dir.exists():
        log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_module_name(module_path: str) -> str:
    """Extract module name from module path (e.g., 'modules.syslog_receiver.receiver' -> 'syslog_receiver')."""
    parts = module_path.split(".")
    try:
        modules_idx = parts.index("modules")
        if modules_idx + 1 < len(parts):
            return parts[modules_idx + 1]
    except ValueError:
        pass
    return parts[-1] if parts else "unknown_module"


def _get_service_name(module_path: str) -> str:
    """Extract service name from path (e.g., 'services.network_manager.manager' -> 'network_manager').
    API gateway submodules (routes, websockets) map to 'api_gateway'.
    remote_access_manager maps to 'remote_access' per spec.
    """
    parts = module_path.split(".")
    try:
        services_idx = parts.index("services")
        if services_idx + 1 < len(parts):
            name = parts[services_idx + 1]
            if name == "remote_access_manager":
                return "remote_access"
            return name
    except ValueError:
        pass
    return parts[-1] if parts else "unknown_service"


class ModuleFormatter(logging.Formatter):
    """Custom formatter for module logs following RPi Engineer-in-a-Box format."""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as: YYYY-MM-DD HH:MM:SS,mmm LEVEL [module_name] message"""
        # Format timestamp: 2026-02-02 14:30:00,123
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S") + f",{dt.microsecond // 1000:03d}"
        
        # Get level name
        level = record.levelname
        
        # Format message
        message = record.getMessage()
        
        # Format: timestamp LEVEL [module_name] message
        formatted = f"{timestamp} {level} [{self.module_name}] {message}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted


def get_module_logger(module_path: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Get a logger configured for module logging with consistent format.

    Args:
        module_path: Typically __name__ (e.g., 'modules.syslog_receiver.receiver')
        log_file: Optional log file name (defaults to '{module_name}.log')

    Returns:
        Configured logger instance
    """
    module_name = _get_module_name(module_path)
    return _get_app_logger(
        module_path, module_name, log_file or f"{module_name}.log"
    )


def get_service_logger(module_path: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Get a logger configured for service logging with consistent format.
    Writes to /var/log/rpi-engineer/{service_name}.log (or RPI_ENGINEER_LOG_DIR).

    Args:
        module_path: Typically __name__ (e.g., 'services.network_manager.manager')
        log_file: Optional log file name (defaults to '{service_name}.log')

    Returns:
        Configured logger instance
    """
    service_name = _get_service_name(module_path)
    return _get_app_logger(
        module_path, service_name, log_file or f"{service_name}.log"
    )


def _get_app_logger(
    logger_name: str, display_name: str, log_file: str
) -> logging.Logger:
    """Shared implementation for module and service loggers."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    if not log_file.endswith(".log"):
        log_file = f"{log_file}.log"
    log_dir = _get_log_dir()
    log_path = log_dir / log_file
    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = ModuleFormatter(display_name)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = ModuleFormatter(display_name)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger

"""Shared logging helper for modules to ensure consistent log format.

Modules should use this helper instead of Python's standard logging module
to ensure logs follow the RPi Engineer-in-a-Box format:
    YYYY-MM-DD HH:MM:SS,mmm LEVEL [module_name] message

Example:
    from lib.module_logger import get_module_logger
    
    logger = get_module_logger(__name__)
    logger.info("Module initialized")
    logger.error("Failed to connect", exc_info=True)
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
    # Look for 'modules' in the path, or use the first part after 'modules'
    try:
        modules_idx = parts.index("modules")
        if modules_idx + 1 < len(parts):
            return parts[modules_idx + 1]
    except ValueError:
        pass
    # Fallback: use the last part or a reasonable default
    return parts[-1] if parts else "unknown_module"


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
        module_path: Typically __name__ from the module (e.g., 'modules.syslog_receiver.receiver')
        log_file: Optional log file name (defaults to '{module_name}.log')
    
    Returns:
        Configured logger instance
    
    Example:
        logger = get_module_logger(__name__)
        logger.info("Starting receiver")
    """
    module_name = _get_module_name(module_path)
    
    # Create logger
    logger = logging.getLogger(module_path)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Determine log file name
    if not log_file:
        log_file = f"{module_name}.log"
    
    # Ensure log file ends with .log
    if not log_file.endswith(".log"):
        log_file = f"{log_file}.log"
    
    # Create file handler
    log_dir = _get_log_dir()
    log_path = log_dir / log_file
    
    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = ModuleFormatter(module_name)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # Fallback to console if file logging fails
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = ModuleFormatter(module_name)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

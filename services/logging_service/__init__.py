"""Logging service package."""

from .manager import LoggingService

logging_service = LoggingService()

__all__ = ["LoggingService", "logging_service"]

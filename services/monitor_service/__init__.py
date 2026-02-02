"""Monitor service package."""

from .manager import MonitorService

monitor_service = MonitorService()

__all__ = ["MonitorService", "monitor_service"]

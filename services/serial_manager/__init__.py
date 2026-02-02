"""Serial manager service package."""

from .manager import SerialManager

serial_manager = SerialManager()

__all__ = ["SerialManager", "serial_manager"]

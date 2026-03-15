"""Remote console (SSH/Telnet) manager service package."""

from .manager import RemoteConsoleManager

remote_console_manager = RemoteConsoleManager()

__all__ = ["RemoteConsoleManager", "remote_console_manager"]

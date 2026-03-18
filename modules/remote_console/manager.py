"""Re-exports remote console manager from services (single implementation, test-patchable paths)."""

from __future__ import annotations

from services.remote_console_manager.manager import (
    MAX_SESSIONS,
    TARGETS_FILENAME,
    RemoteConsoleManager,
    RemoteConsoleSession,
    RemoteConsoleTarget,
    get_remote_console_manager,
)

__all__ = [
    "MAX_SESSIONS",
    "RemoteConsoleManager",
    "RemoteConsoleSession",
    "RemoteConsoleTarget",
    "TARGETS_FILENAME",
    "get_remote_console_manager",
]

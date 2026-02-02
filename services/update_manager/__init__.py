"""Update manager service package."""

from .manager import UpdateManager

update_manager = UpdateManager()

__all__ = ["UpdateManager", "update_manager"]

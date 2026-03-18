"""Syslog module package; exposes receiver for API delegation and test patching."""

from __future__ import annotations

from modules.syslog_receiver import receiver as receiver

__all__ = ["receiver"]

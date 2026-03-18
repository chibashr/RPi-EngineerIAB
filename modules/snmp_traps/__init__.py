"""SNMP traps module package; exposes receiver for API delegation and test patching."""

from __future__ import annotations

from modules.snmp_trap_receiver import receiver as receiver

__all__ = ["receiver"]

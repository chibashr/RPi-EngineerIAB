"""Compatibility shim for legacy `modules.capture.manager` imports."""

import sys

from services.capture_manager import manager as _manager

# Expose the real manager module so monkeypatching works as expected in tests.
sys.modules[__name__] = _manager

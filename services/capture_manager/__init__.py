"""Capture manager service package."""

from .manager import CaptureManager

capture_manager = CaptureManager()

__all__ = ["CaptureManager", "capture_manager"]

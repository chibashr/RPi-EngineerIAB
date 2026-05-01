"""Compatibility shim for legacy `modules.capture.manager` imports."""

from services.capture_manager import manager as _manager

CaptureManager = _manager.CaptureManager
split_bpf_filter = _manager.split_bpf_filter
_capture_dir = _manager._capture_dir
_which = _manager._which

__all__ = ["CaptureManager", "split_bpf_filter", "_capture_dir", "_which"]

"""Syslog receiver lifecycle hooks."""

from . import receiver


def initialize() -> None:
    receiver.start_receiver()


def shutdown() -> None:
    receiver.stop_receiver()

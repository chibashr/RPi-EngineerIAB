"""Example module lifecycle hooks."""

from lib.module_logger import get_module_logger

logger = get_module_logger(__name__)


def initialize() -> None:
    logger.info("Example module initialized")
    return


def shutdown() -> None:
    logger.info("Example module shutdown")
    return

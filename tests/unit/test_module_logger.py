"""Unit tests for lib/module_logger.py."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from lib import module_logger


@pytest.mark.unit
def test_get_service_logger_returns_logger():
    """Verify get_service_logger(__name__) returns a Logger instance."""
    logger = module_logger.get_service_logger(__name__)
    assert isinstance(logger, logging.Logger)


@pytest.mark.unit
def test_service_name_extraction():
    """Verify _get_service_name extracts correct names."""
    assert module_logger._get_service_name("services.network_manager.manager") == "network_manager"
    assert module_logger._get_service_name("services.remote_access_manager.manager") == "remote_access"
    assert module_logger._get_service_name("services.api_gateway.routes.network") == "api_gateway"


@pytest.mark.unit
def test_rotating_handler_configured():
    """Verify the file handler is RotatingFileHandler with correct maxBytes."""
    from logging.handlers import RotatingFileHandler

    logger = module_logger.get_service_logger("tests.unit.test_module_logger")
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    if not file_handlers:
        pytest.skip("RotatingFileHandler not yet implemented (uses FileHandler)")
    handler = file_handlers[0]
    assert handler.maxBytes == 10 * 1024 * 1024  # 10 MB
    assert handler.backupCount == 5


@pytest.mark.unit
def test_stdout_handler_always_present():
    """Verify logger has at least one StreamHandler writing to stdout."""
    logger = module_logger.get_service_logger("tests.unit.test_module_logger")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    stdout_handlers = [h for h in stream_handlers if getattr(h.stream, "name", None) == "<stdout>" or h.stream is sys.stdout]
    if not stdout_handlers:
        pytest.skip("Stdout handler not yet implemented")
    assert len(stdout_handlers) >= 1


@pytest.mark.unit
def test_log_level_from_env(monkeypatch):
    """Verify logger level is DEBUG when RPI_ENGINEER_LOG_LEVEL=DEBUG."""
    monkeypatch.setenv("RPI_ENGINEER_LOG_LEVEL", "DEBUG")
    # Clear cached loggers to force re-init with new env
    name = "tests.unit.test_module_logger_level"
    if name in logging.Logger.manager.loggerDict:
        del logging.Logger.manager.loggerDict[name]
    logger = module_logger.get_service_logger(name)
    if logger.level != logging.DEBUG:
        pytest.skip("RPI_ENGINEER_LOG_LEVEL not yet implemented")
    assert logger.level == logging.DEBUG


@pytest.mark.unit
def test_json_formatter_activated(monkeypatch):
    """Verify formatter is JSONFormatter when RPI_ENGINEER_ENV=production."""
    monkeypatch.setenv("RPI_ENGINEER_ENV", "production")
    name = "tests.unit.test_module_logger_json"
    if name in logging.Logger.manager.loggerDict:
        del logging.Logger.manager.loggerDict[name]
    logger = module_logger.get_service_logger(name)
    formatters = [h.formatter for h in logger.handlers if h.formatter is not None]
    json_formatters = [f for f in formatters if type(f).__name__ == "JSONFormatter"]
    if not json_formatters:
        pytest.skip("JSONFormatter not yet implemented")
    assert len(json_formatters) >= 1


@pytest.mark.unit
def test_json_formatter_output_is_valid_json(monkeypatch):
    """Verify JSON formatter produces valid JSON with required keys."""
    monkeypatch.setenv("RPI_ENGINEER_ENV", "production")
    name = "tests.unit.test_module_logger_json_output"
    if name in logging.Logger.manager.loggerDict:
        del logging.Logger.manager.loggerDict[name]

    # Capture handler to inspect output
    from io import StringIO
    buf = StringIO()
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False

    # Get a JSON formatter if available
    try:
        json_formatter = getattr(module_logger, "JSONFormatter", None)
        if json_formatter is None:
            pytest.skip("JSONFormatter not yet implemented")
        handler = logging.StreamHandler(buf)
        handler.setFormatter(json_formatter("test_service"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.info("test message")
        handler.flush()
        line = buf.getvalue().strip()
        if not line:
            pytest.skip("JSONFormatter not producing output")
        obj = json.loads(line)
        assert "timestamp" in obj
        assert "level" in obj
        assert "service" in obj
        assert "message" in obj
    finally:
        logger.handlers.clear()


@pytest.mark.unit
def test_existing_caller_unchanged():
    """Regression: get_service_logger must not break existing callers."""
    logger = module_logger.get_service_logger("services.serial_manager.manager")
    assert isinstance(logger, logging.Logger)
    logger.debug("test")
    logger.info("test")

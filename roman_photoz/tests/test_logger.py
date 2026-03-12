import io
import logging

import pytest

from roman_photoz.logger import setup_logging


def _close_and_clear_handlers(logger_name="roman_photoz"):
    """Close all handlers before clearing to avoid ResourceWarning."""
    logger = logging.getLogger(logger_name)
    for handler in logger.handlers[:]:
        handler.close()
    logger.handlers.clear()


@pytest.fixture
def temp_log_file(tmp_path):
    """Create a temporary log file path for testing."""
    return tmp_path / "test_roman_photoz.log"


def test_setup_logging_creates_logger_with_correct_name():
    """Test that setup_logging creates a logger with the correct name."""
    logger = setup_logging()
    assert logger.name == "roman_photoz"


def test_setup_logging_creates_handlers_and_filters(tmp_path):
    """Test that setup_logging creates the correct handlers and filters."""
    _close_and_clear_handlers()

    log_file = tmp_path / "test_roman_photoz.log"
    logger = setup_logging(log_file=str(log_file))

    # Should have 2 handlers (console and file)
    assert len(logger.handlers) == 2

    # Check handler types
    handler_types = [type(h) for h in logger.handlers]
    assert logging.StreamHandler in handler_types
    assert logging.FileHandler in handler_types

    # Console handler only allows INFO messages
    console_handler = [
        h for h in logger.handlers if isinstance(h, logging.StreamHandler)
    ][0]
    assert console_handler.level == logging.INFO
    assert (
        any(
            hasattr(f, "__call__") and getattr(f, "__name__", "") == "<lambda>"
            for f in console_handler.filters
        )
        or console_handler.filters
    )  # lambda filter present

    # File handler is attached to the same logger
    file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert file_handlers
    assert file_handlers[0].baseFilename.endswith("test_roman_photoz.log")


def test_setup_logging_uses_correct_formatter(tmp_path):
    """Test that setup_logging uses the correct formatter."""
    _close_and_clear_handlers()

    log_file = tmp_path / "test_roman_photoz.log"
    logger = setup_logging(log_file=str(log_file))

    for handler in logger.handlers:
        formatter = handler.formatter
        assert formatter._fmt == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Also check file handler formatter
    file_handler = [h for h in logger.handlers if isinstance(h, logging.FileHandler)][0]
    assert (
        file_handler.formatter._fmt
        == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def test_setup_logging_only_configures_once(tmp_path):
    """Test that setup_logging doesn't add handlers if already configured."""
    _close_and_clear_handlers()
    _close_and_clear_handlers("root")

    log_file = tmp_path / "test_roman_photoz.log"
    logger1 = setup_logging(log_file=str(log_file))
    initial_handler_count = len(logger1.handlers)

    logger2 = setup_logging(log_file=str(log_file))
    assert len(logger2.handlers) == initial_handler_count


@pytest.mark.parametrize(
    "message_level,should_appear_on_console",
    [
        (logging.DEBUG, False),
        (logging.INFO, True),
        (logging.WARNING, False),
        (logging.ERROR, False),
        (logging.CRITICAL, False),
    ],
    ids=[
        "debug_not_on_console",
        "info_on_console",
        "warning_not_on_console",
        "error_not_on_console",
        "critical_not_on_console",
    ],
)
def test_console_only_shows_info_messages(
    tmp_path, message_level, should_appear_on_console
):
    """Test that only INFO messages appear on the console."""
    _close_and_clear_handlers()
    _close_and_clear_handlers("root")

    log_file = tmp_path / "test_roman_photoz.log"
    logger = setup_logging(log_file=str(log_file))

    # Patch sys.stderr to capture console output
    stream = io.StringIO()
    logger.handlers[0].stream = stream

    test_message = "Test message"
    log_func = {
        logging.DEBUG: logger.debug,
        logging.INFO: logger.info,
        logging.WARNING: logger.warning,
        logging.ERROR: logger.error,
        logging.CRITICAL: logger.critical,
    }[message_level]
    log_func(test_message)

    output = stream.getvalue()
    if should_appear_on_console:
        assert test_message in output
    else:
        assert test_message not in output


@pytest.mark.parametrize(
    "message_level",
    [
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ],
)
def test_all_messages_go_to_file(tmp_path, message_level):
    """Test that all log levels are written to the log file."""
    _close_and_clear_handlers()
    _close_and_clear_handlers("root")

    log_file = tmp_path / "test_roman_photoz.log"
    logger = setup_logging(log_file=str(log_file))

    test_message = f"File log message {message_level}"
    log_func = {
        logging.DEBUG: logger.debug,
        logging.INFO: logger.info,
        logging.WARNING: logger.warning,
        logging.ERROR: logger.error,
        logging.CRITICAL: logger.critical,
    }[message_level]
    log_func(test_message)

    # Flush and close file handlers to ensure logs are written and file is closed
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.flush()
            handler.close()

    with open(log_file) as f:
        contents = f.read()
    assert test_message in contents

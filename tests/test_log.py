"""Tests for sift.log."""

import logging

import pytest

from sift.log import setup_logging


@pytest.fixture(autouse=True)
def clean_sift_logger():
    """Restore the sift logger after every test."""
    logger = logging.getLogger("sift")
    handlers, level = logger.handlers[:], logger.level
    yield logger
    logger.handlers[:] = handlers
    logger.setLevel(level)


def test_level_is_set_by_name(clean_sift_logger: logging.Logger) -> None:
    setup_logging("debug")
    assert clean_sift_logger.level == logging.DEBUG
    setup_logging()
    assert clean_sift_logger.level == logging.WARNING


def test_calling_twice_keeps_one_handler(
    clean_sift_logger: logging.Logger,
) -> None:
    setup_logging()
    setup_logging("INFO", rich=True)
    assert len(clean_sift_logger.handlers) == 1


def test_records_go_to_stderr_in_the_documented_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging("INFO")
    logging.getLogger("sift.demo").info("hello %s", "world")
    logging.getLogger("sift.demo").debug("hidden")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INFO sift.demo: hello world\n"


def test_rich_uses_the_rich_handler(
    clean_sift_logger: logging.Logger,
) -> None:
    from rich.logging import RichHandler

    setup_logging("INFO", rich=True)
    (handler,) = clean_sift_logger.handlers
    assert isinstance(handler, RichHandler)
    setup_logging("INFO")
    (handler,) = clean_sift_logger.handlers
    assert not isinstance(handler, RichHandler)


def test_rich_records_go_to_stderr_without_time_or_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    setup_logging("INFO", rich=True)
    logging.getLogger("sift.demo").info("hello [bold]%s[/bold]", "world")
    logging.getLogger("sift.demo").debug("hidden")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "INFO" in captured.err
    assert "sift.demo: hello [bold]world[/bold]" in captured.err
    assert "hidden" not in captured.err
    assert "\x1b" not in captured.err
    assert ".py" not in captured.err


def test_unknown_level_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown log level: 'LOUD'"):
        setup_logging("LOUD")

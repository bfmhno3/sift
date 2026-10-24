"""Logging setup: one function that configures the ``sift`` logger.

Every module logs through ``logging.getLogger("sift.<module>")``, so
one handler on the ``sift`` logger sees them all.
"""

import logging
import sys

_FORMAT = "%(levelname)s %(name)s: %(message)s"


def setup_logging(level: str = "WARNING", *, rich: bool = False) -> None:
    """Send ``sift.*`` log records to stderr at the given level.

    level is a level name such as ``"DEBUG"`` or ``"WARNING"``; an
    unknown name raises ValueError. Calling it again replaces the
    handler, it never adds a second one. rich is accepted and
    ignored: the rich handler arrives in chapter 19.
    """
    number = logging.getLevelNamesMapping().get(level.upper())
    if number is None:
        raise ValueError(f"unknown log level: {level!r}")
    logger = logging.getLogger("sift")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(number)

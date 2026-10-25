"""Logging setup: one function that configures the ``sift`` logger.

Every module logs through ``logging.getLogger("sift.<module>")``, so
one handler on the ``sift`` logger sees them all.
"""

import logging
import sys

_FORMAT = "%(levelname)s %(name)s: %(message)s"
_RICH_FORMAT = "%(name)s: %(message)s"


def setup_logging(level: str = "WARNING", *, rich: bool = False) -> None:
    """Send ``sift.*`` log records to stderr at the given level.

    level is a level name such as ``"DEBUG"`` or ``"WARNING"``; an
    unknown name raises ValueError. Calling it again replaces the
    handler, it never adds a second one. With rich the handler is
    rich.logging.RichHandler (coloured level, aligned columns, no
    time or path); without it, a plain StreamHandler with the format
    ``LEVEL name: message``. The command line passes rich only when
    stderr is a terminal.
    """
    number = logging.getLevelNamesMapping().get(level.upper())
    if number is None:
        raise ValueError(f"unknown log level: {level!r}")
    logger = logging.getLogger("sift")
    for old in logger.handlers[:]:
        logger.removeHandler(old)
    handler: logging.Handler
    if rich:
        from rich.console import Console
        from rich.logging import RichHandler

        handler = RichHandler(
            console=Console(stderr=True),
            show_time=False,
            show_path=False,
            markup=False,
        )
        handler.setFormatter(logging.Formatter(_RICH_FORMAT))
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(number)

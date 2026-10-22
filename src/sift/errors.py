"""The exception hierarchy of Sift: every error it raises on purpose.

::

    Exception
    └── SiftError
        ├── QuerySyntaxError
        ├── FrontMatterError
        ├── ConfigError
        ├── IndexMissingError
        └── IndexCorruptError

``except SiftError`` catches every failure that Sift reports on
purpose and nothing else: a bug stays a plain TypeError or KeyError.
"""

import unicodedata
from pathlib import Path


class SiftError(Exception):
    """Base class of every error that Sift raises on purpose."""


def _display_width(text: str) -> int:
    """Return how many terminal columns text takes.

    Wide and fullwidth characters (CJK) take two columns, combining
    marks none, everything else one.
    """
    width = 0
    for ch in text:
        if unicodedata.east_asian_width(ch) in "WF":
            width += 2
        elif not unicodedata.combining(ch):
            width += 1
    return width


class QuerySyntaxError(SiftError):
    """A query that does not follow the grammar.

    str(error) is the message alone. query is the text that failed
    and position an offset into it.
    """

    def __init__(self, message: str, query: str, position: int) -> None:
        """Keep the message, the query and the offset."""
        super().__init__(message, query, position)
        self.message = message
        self.query = query
        self.position = position

    def __str__(self) -> str:
        """Return the message alone."""
        return self.message

    def render(self) -> str:
        """Return the message, the query line and a caret line.

        The caret sits under the character at position, also when
        the query has wide (CJK) characters before it.
        """
        pad = " " * _display_width(self.query[: self.position])
        return f"{self.message}\n  {self.query}\n  {pad}^"


class FrontMatterError(SiftError):
    """A front matter block that the parser cannot read.

    path is the file (None while only a string is parsed) and line
    the 1-based line in that file, or in the parsed text.
    """

    def __init__(self, path: Path | None, line: int, message: str) -> None:
        """Keep the file, the line and the message."""
        super().__init__(path, line, message)
        self.path = path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        """Return ``path:line: message``, or ``line N: message``."""
        if self.path is None:
            return f"line {self.line}: {self.message}"
        return f"{self.path}:{self.line}: {self.message}"


class ConfigError(SiftError):
    """A setting that names something that does not exist."""


class IndexMissingError(SiftError):
    """No index has been built where one is expected (from ch12)."""


class IndexCorruptError(SiftError):
    """An index file that fails its checks (from ch12)."""

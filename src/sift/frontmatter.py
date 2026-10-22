"""A hand-written parser for the YAML subset used by the posts."""

import re
from pathlib import Path

from sift.errors import FrontMatterError

type Value = str | list[str] | bool | int

_KEY = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+(.*))?")
_ITEM = re.compile(r"[ \t]*-[ \t]+(.*)")
_INT = re.compile(r"[+-]?[0-9]+")
_DOUBLE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_SINGLE = re.compile(r"'((?:[^']|'')*)'")
_ESCAPE = re.compile(r"\\(.)")
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t"}
_INLINE_ITEM = re.compile(
    r"""[ \t]*("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[^,"'\s][^,]*?)[ \t]*(,|$)"""
)
_FLOW_START = "[{|>&*!%@`"
_BLOCK_HEADERS = (">", ">-", "|", "|-")


def _no_value(path: Path | None, line: int, key: str) -> FrontMatterError:
    """Return the error for a ``key:`` with neither value nor items."""
    return FrontMatterError(path, line, f"key {key!r} has no value")


def _unescape(match: re.Match[str]) -> str:
    """Return the character a double-quoted escape stands for."""
    try:
        return _ESCAPES[match[1]]
    except KeyError:
        raise ValueError(f"unsupported escape \\{match[1]}") from None


def _parse_string(raw: str) -> str:
    """Return the string a quoted or plain scalar stands for."""
    if raw.startswith('"'):
        if (m := _DOUBLE.fullmatch(raw)) is None:
            raise ValueError(f"bad double-quoted string: {raw}")
        return _ESCAPE.sub(_unescape, m[1])
    if raw.startswith("'"):
        if (m := _SINGLE.fullmatch(raw)) is None:
            raise ValueError(f"bad single-quoted string: {raw}")
        return m[1].replace("''", "'")
    if raw[0] in _FLOW_START:
        raise ValueError(f"unsupported syntax: {raw}")
    if ": " in raw or raw.endswith(":") or " #" in raw:
        raise ValueError(f"ambiguous plain string: {raw}")
    return raw


def _parse_inline_list(raw: str) -> list[str]:
    """Parse ``[a, "b", 'c']`` into a list of strings."""
    if not raw.endswith("]"):
        raise ValueError(f"unterminated inline list: {raw}")
    inner = raw[1:-1]
    items: list[str] = []
    pos = 0
    while inner[pos:].strip():
        if (m := _INLINE_ITEM.match(inner, pos)) is None:
            raise ValueError(f"bad inline list: {raw}")
        items.append(_parse_string(m[1]))
        pos = m.end()
    return items


def _parse_scalar(raw: str) -> Value:
    """Parse the value after ``key:`` on the same line."""
    if raw == "true":
        return True
    if raw == "false":
        return False
    if _INT.fullmatch(raw):
        return int(raw)
    if raw.startswith("["):
        return _parse_inline_list(raw)
    return _parse_string(raw)


def _block_scalar(lines: list[str], i: int, header: str) -> tuple[str, int]:
    """Read the indented lines from lines[i] as a ``>`` or ``|`` scalar.

    header is the indicator (``>``, ``>-``, ``|`` or ``|-``). Return
    the string and the index of the first line that is not part of it.
    """
    if header not in _BLOCK_HEADERS:
        raise ValueError(f"unsupported block scalar header {header!r}")
    start = i
    while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
        i += 1
    body = [line.strip() for line in lines[start:i]]
    while body and not body[-1]:
        body.pop()
    text = (" " if header[0] == ">" else "\n").join(body)
    return (text if header.endswith("-") or not text else text + "\n"), i


def parse_front_matter(
    text: str, path: Path | None = None, first_line: int = 1
) -> dict[str, Value]:
    """Parse the front matter text of a post into a dict.

    The input is the text between the two ``---`` lines. Supported:
    ``key: value`` with double-quoted, single-quoted or plain strings,
    ``true``/``false``, integers, inline lists ``[a, b]``, block lists
    of ``  - item`` lines and the block scalars ``>``, ``>-``, ``|``
    and ``|-`` with indented text lines. Anything else, such as
    nesting, anchors or a repeated key, raises FrontMatterError.

    path names the file in the error and first_line is the number
    that the first line of text has in that file (2 when text comes
    from between two ``---`` lines), so error.line is a line of the
    file.
    """
    result: dict[str, Value] = {}
    lines = text.splitlines()
    open_list: list[str] | None = None
    open_key = ""
    open_line = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip():
            continue
        try:
            if m := _ITEM.fullmatch(line.rstrip()):
                if open_list is None:
                    raise ValueError("list item without a key")
                open_list.append(_parse_string(m[1].strip()))
                continue
            if open_list is not None and not open_list:
                raise _no_value(path, first_line + open_line - 1, open_key)
            open_list = None
            if (m := _KEY.fullmatch(line.rstrip())) is None:
                raise ValueError(f"cannot parse line: {line!r}")
            key, raw = m[1], m[2]
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            if raw is None:
                open_list = result[key] = []
                open_key, open_line = key, i
            elif raw[0] in ">|":
                result[key], i = _block_scalar(lines, i, raw.strip())
            else:
                result[key] = _parse_scalar(raw.strip())
        except ValueError as exc:
            raise FrontMatterError(
                path, first_line + i - 1, str(exc)
            ) from None
    if open_list is not None and not open_list:
        raise _no_value(path, first_line + open_line - 1, open_key)
    return result

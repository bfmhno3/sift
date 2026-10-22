"""Snippets: a window of text around the matches, and its rendering."""

import re
from bisect import bisect_left, bisect_right
from collections.abc import Collection
from functools import cache
from html import escape
from itertools import accumulate
from string.templatelib import Interpolation, Template, convert

from sift.analysis import iter_tokens
from sift.analysis.tokenize import fold

type Parts = list[tuple[str, bool]]

_SPACES = re.compile(r"\s+")


@cache
def _folded_len(ch: str) -> int:
    """Return the length of fold(ch)."""
    return len(fold(ch))


def _origin(text: str) -> tuple[str, list[int] | None]:
    """Return the text to show and the offset table of its folding.

    iter_tokens reports offsets into fold(text), which is longer or
    shorter than text when NFKC rewrites a character (``…`` becomes
    three dots). The table lists, for every index i of text, the
    offset in fold(text) where character i starts, plus the final
    length, so a folded offset maps back with bisect. None means the
    two texts have the same length and offsets are the same. If the
    per-character folds do not add up to fold(text) (combining
    marks), the folded text itself is shown, with offsets as they are.
    """
    folded = fold(text)
    if len(folded) == len(text):
        return text, None
    lengths = [_folded_len(ch) for ch in text]
    table = list(accumulate(lengths, initial=0))
    if table[-1] != len(folded):
        return folded, None
    return text, table


def _hit_spans(
    shown: str, table: list[int] | None, terms: Collection[str]
) -> list[tuple[int, int]]:
    """Return disjoint (start, end) offsets in shown of the hits."""
    spans: list[tuple[int, int]] = []
    for token in iter_tokens(shown):
        if token.text not in terms:
            continue
        start, end = token.start, token.end
        if table is not None:
            start = bisect_right(table, start) - 1
            end = bisect_left(table, end)
        if spans and start <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(end, spans[-1][1]))
        else:
            spans.append((start, end))
    return spans


def _squeeze(text: str) -> str:
    """Collapse every run of whitespace in text to one space."""
    return _SPACES.sub(" ", text)


def make_snippet(text: str, terms: Collection[str], width: int = 160) -> Parts:
    """Return parts of text around the densest cluster of hits.

    terms are index terms (analyzed). The result is a list of
    ``(text, is_hit)`` pairs covering a window of about width
    characters; ``…`` marks a cut edge. With no hit, the window is
    the start of the text. Whitespace runs are collapsed to a space.
    """
    shown, table = _origin(text)
    spans = _hit_spans(shown, table, terms)
    if not spans:
        lo, hi = 0, width
    else:
        starts = [s for s, _ in spans]
        ends = [e for _, e in spans]
        best = -1
        lo = 0
        for s in starts:
            cand = max(0, s - width // 4)
            count = bisect_right(ends, cand + width) - bisect_left(
                starts, cand
            )
            if count > best:
                best, lo = count, cand
        hi = lo + width
    hi = min(hi, len(shown))
    parts: Parts = []
    if lo > 0:
        parts.append(("…", False))
    cursor = lo
    for start, end in spans:
        if end <= lo or start >= hi:
            continue
        start, end = max(start, lo), min(end, hi)
        if start > cursor:
            parts.append((_squeeze(shown[cursor:start]), False))
        parts.append((_squeeze(shown[start:end]), True))
        cursor = end
    if cursor < hi:
        parts.append((_squeeze(shown[cursor:hi]), False))
    if hi < len(shown):
        parts.append(("…", False))
    return parts


def html(template: Template) -> str:
    """Render a t-string, escaping every interpolated value.

    Static text is the author's HTML and passes through. A value that
    is itself a Template is rendered recursively; any other value is
    converted, formatted, then escaped with ``html.escape``.
    """
    out: list[str] = []
    for item in template:
        match item:
            case str() as static:
                out.append(static)
            case Interpolation(Template() as inner, _, _, _):
                out.append(html(inner))
            case Interpolation(value, _, conversion, format_spec):
                if conversion is not None:
                    value = convert(value, conversion)
                out.append(escape(format(value, format_spec)))
    return "".join(out)


def render_html(parts: Parts) -> str:
    """Return parts as HTML: text escaped, hits wrapped in <mark>."""
    return "".join(
        html(t"<mark>{text}</mark>") if hit else html(t"{text}")
        for text, hit in parts
    )


def render_plain(parts: Parts) -> str:
    """Return parts as text with ``[`` and ``]`` around the hits."""
    return "".join(f"[{text}]" if hit else text for text, hit in parts)

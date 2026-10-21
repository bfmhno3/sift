"""The tokenizer: Latin words and CJK bigrams, as a token stream."""

import re
import unicodedata
from collections.abc import Iterator
from typing import NamedTuple

CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"

# Latin/digit run with an optional c++ / c# style suffix, or a CJK run.
_TOKEN = re.compile(
    rf"""
    (?P<latin> [0-9a-z_]+ (?: \+{{1,2}} | \# )? )
    | (?P<cjk> [{CJK}]+ )
    """,
    re.VERBOSE,
)


def fold(text: str) -> str:
    """NFKC-normalize and casefold text."""
    return unicodedata.normalize("NFKC", text).casefold()


class Token(NamedTuple):
    """One index term and where it came from.

    position counts tokens from 0. start and end are str offsets into
    the folded text (see iter_tokens), with end exclusive.
    """

    text: str
    position: int
    start: int
    end: int


def iter_tokens(text: str) -> Iterator[Token]:
    """Yield the tokens of text one at a time.

    The text is NFKC-normalized and casefolded first. Latin and digit
    runs become one token each (``c++`` and ``c#`` keep their suffix).
    A CJK run becomes overlapping bigrams, or one unigram when the run
    has a single character.

    start and end are offsets into the normalized, casefolded text,
    not into the argument: NFKC can change the length of the text
    (``"ﬁ"`` becomes ``"fi"``, ``"㎏"`` becomes ``"kg"``), and the
    two coincide only when the folding keeps every length.
    """
    folded = fold(text)
    position = 0
    for match in _TOKEN.finditer(folded):
        if match["latin"] is not None:
            yield Token(match["latin"], position, match.start(), match.end())
            position += 1
            continue
        run = match["cjk"]
        if len(run) == 1:
            yield Token(run, position, match.start(), match.end())
            position += 1
            continue
        for i in range(len(run) - 1):
            start = match.start() + i
            yield Token(run[i : i + 2], position, start, start + 2)
            position += 1


def tokenize(text: str) -> list[str]:
    """Return the terms of text: the token texts of iter_tokens."""
    return [token.text for token in iter_tokens(text)]

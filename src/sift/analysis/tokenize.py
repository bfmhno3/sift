"""The tokenizer: Latin words and CJK bigrams, as a token stream."""

import re
import unicodedata
from collections.abc import Callable, Collection, Iterator
from typing import NamedTuple, cast

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


# Token(...) runs a generated Python __new__; this skips that frame.
_new_token = cast(
    "Callable[[type[Token], tuple[str, int, int, int]], Token]",
    tuple[object, ...].__new__,
)


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
    new = _new_token
    for match in _TOKEN.finditer(folded):
        run = match[0]
        start, end = match.span()
        if match.lastgroup == "latin" or end - start == 1:
            yield new(Token, (run, position, start, end))
            position += 1
            continue
        for i in range(end - start - 1):
            at = start + i
            yield new(Token, (run[i : i + 2], position, at, at + 2))
            position += 1


def iter_hit_spans(
    text: str, terms: Collection[str]
) -> Iterator[tuple[int, int]]:
    """Yield (start, end) of the tokens of text whose text is in terms.

    The same tokens and offsets as the ones of iter_tokens that pass
    ``token.text in terms``, in the same order, but the other tokens
    are never built: a snippet keeps a handful out of thousands.

    >>> list(iter_hit_spans("The Fox ran. 搜索引擎", {"fox", "索引"}))
    [(4, 7), (14, 16)]
    """
    folded = fold(text)
    for match in _TOKEN.finditer(folded):
        run = match[0]
        start, end = match.span()
        if match.lastgroup == "latin" or end - start == 1:
            if run in terms:
                yield start, end
            continue
        for i in range(end - start - 1):
            if run[i : i + 2] in terms:
                at = start + i
                yield at, at + 2


def tokenize(text: str) -> list[str]:
    """Return the terms of text: the token texts of iter_tokens."""
    return [token.text for token in iter_tokens(text)]

"""The Rust tokenizer through PyO3: ``sift._rs`` from rust/sift-rs.

``make ext-rs`` builds it with maturin into the virtual environment.
Like the C twins it takes text that ``sift.analysis.tokenize.fold``
has already normalized: no Rust crate does ``str.casefold`` for the
Unicode version of this interpreter.

The Rust side returns plain tuples; this module turns them into Token.
A lone surrogate cannot become a Rust ``&str``, so PyO3 raises
UnicodeEncodeError; each surrogate is then replaced by U+FFFD, which
is no token and keeps every offset, and the call is repeated.
"""

import re
from collections.abc import Sequence

import sift._rs as _rs
from sift.analysis.tokenize import Token
from sift.ext import new_token

_SURROGATE = re.compile("[\ud800-\udfff]")


def _clean(text: str) -> str:
    """Return text with each lone surrogate replaced by U+FFFD."""
    return _SURROGATE.sub("\ufffd", text)


def tokens(folded: str) -> list[Token]:
    """Return the tokens of folded, which is NFKC and casefolded."""
    try:
        raw = _rs.tokenize(folded)
    except UnicodeEncodeError:
        raw = _rs.tokenize(_clean(folded))
    new = new_token
    return [new(Token, item) for item in raw]


def tokens_many(folded: Sequence[str], threads: int = 0) -> list[list[Token]]:
    """Return tokens(text) for each text, tokenized in parallel.

    The GIL is released while the Rust threads work. threads is the
    number of Rust threads; 0 means one per CPU. ValueError if it is
    more than 256.
    """
    texts = list(folded)
    try:
        raw = _rs.tokenize_many(texts, threads)
    except UnicodeEncodeError:
        raw = _rs.tokenize_many([_clean(text) for text in texts], threads)
    new = new_token
    return [[new(Token, item) for item in found] for found in raw]

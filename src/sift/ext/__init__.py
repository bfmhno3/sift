"""Native tokenizers: the same tokens as MixedTokenizer, from C.

Four ways to call native code, one task. ``ctok`` binds
``c/build/libsifttok.so`` with ctypes, ``cffitok`` binds the same
library with cffi, ``_cytok`` is a Cython module that loops over the
str, and ``_capi`` is a hand-written C API module. ``make ext`` builds
the three native artifacts; nothing here is imported until a tokenizer
of this package is used.

Each tokenizer module has ``tokens(folded)``, which takes text that
``sift.analysis.tokenize.fold`` has already normalized and returns the
list of Token that ``iter_tokens`` would yield for the original text.
NFKC and casefold stay in Python: they need the Unicode database.

The C library reports byte offsets into the UTF-8 encoding of the
text. ``tokens_from_spans`` turns them into str offsets.
"""

from collections.abc import Callable, Sequence
from typing import cast

from sift.analysis.tokenize import Token

# Token(...) runs a generated Python __new__; this skips that frame.
_new_token = cast(
    "Callable[[type[Token], tuple[str, int, int, int]], Token]",
    tuple[object, ...].__new__,
)

ENCODING = "utf-8"
# A str may hold lone surrogates; encoding them with the default
# handler raises. surrogatepass writes them as three bytes, which the
# C code treats as invalid UTF-8 and skips, like Python skips them.
ERRORS = "surrogatepass"


def encode(folded: str) -> bytes:
    """Return the UTF-8 bytes of folded, lone surrogates included."""
    return folded.encode(ENCODING, ERRORS)


def tokens_from_spans(
    folded: str, data: bytes, flat: Sequence[int]
) -> list[Token]:
    """Build the Token list from byte spans.

    data is encode(folded) and flat holds the spans as start0, end0,
    start1, end1, ... byte offsets, ordered by start as the C code
    emits them. Positions count the spans from 0.

    When data is as long as folded every character took one byte, so
    byte and str offsets are the same. Otherwise the str offset of a
    span is the str offset of the one before plus the characters in
    the bytes between the two starts; a gap of one three-byte
    character, as between two bigrams of a run, is not decoded. A
    token is either ASCII or CJK, and a CJK character takes three
    bytes, which gives its length in characters without decoding it.
    """
    new = _new_token
    out: list[Token] = []
    it = iter(flat)
    if len(data) == len(folded):
        for position, (start, end) in enumerate(zip(it, it, strict=True)):
            out.append(new(Token, (folded[start:end], position, start, end)))
        return out
    byte_at = 0
    char_at = 0
    for position, (start, end) in enumerate(zip(it, it, strict=True)):
        gap = start - byte_at
        if gap:
            if gap == 3 and 0xE0 <= data[byte_at] < 0xF0:
                char_at += 1
            else:
                skipped = data[byte_at:start].decode(ENCODING, ERRORS)
                char_at += len(skipped)
            byte_at = start
        size = end - start
        if data[start] >= 0x80:
            size //= 3
        stop = char_at + size
        out.append(new(Token, (folded[char_at:stop], position, char_at, stop)))
    return out

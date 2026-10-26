"""The C tokenizer through ctypes.

ctypes loads ``c/build/libsifttok.so`` with ``CDLL`` and calls it
with no compiler and no glue code, but it checks nothing: the
``argtypes`` and ``restype`` set below are the only protection against
a wrong call, and a wrong one is a crash, not an exception.

SIFT_LIBTOK names another library file. Importing this module raises
OSError if the library is not there: run ``make ext``.
"""

import ctypes
import errno
import os
from pathlib import Path

from sift.analysis.tokenize import Token
from sift.ext import encode, tokens_from_spans

LIBRARY = Path(__file__).resolve().parents[3] / "c/build/libsifttok.so"
# Spans for the first call: a guess that holds for most text. The C
# code reports the exact count, so a miss costs one more call.
FIRST_GUESS = 4


class Span(ctypes.Structure):
    """struct sift_span: the byte range of one token."""

    _fields_ = [("start", ctypes.c_size_t), ("end", ctypes.c_size_t)]


def load(path: Path) -> ctypes.CDLL:
    """Load the library at path and declare its functions."""
    lib = ctypes.CDLL(str(path))
    lib.sift_tokenize.argtypes = [
        ctypes.c_char_p,
        ctypes.c_size_t,
        ctypes.POINTER(Span),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    lib.sift_tokenize.restype = ctypes.c_int
    lib.sift_count_cjk.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    lib.sift_count_cjk.restype = ctypes.c_size_t
    return lib


_lib = load(Path(os.environ.get("SIFT_LIBTOK", LIBRARY)))
_tokenize = _lib.sift_tokenize
_count_cjk = _lib.sift_count_cjk


def spans(data: bytes) -> list[int]:
    """Return the token spans of UTF-8 data: start, end, start, ...

    Raise OSError if the C code reports an error.
    """
    cap = len(data) // FIRST_GUESS + 1
    n = ctypes.c_size_t()
    while True:
        buf = (Span * cap)()
        rc = _tokenize(data, len(data), buf, cap, ctypes.byref(n))
        if rc == 0:
            break
        if rc != -errno.ENOSPC:
            raise OSError(-rc, os.strerror(-rc))
        cap = n.value
    # The array is a buffer of size_t pairs; view it as plain numbers.
    numbers = ctypes.cast(buf, ctypes.POINTER(ctypes.c_size_t))
    return numbers[: 2 * n.value]


def tokens(folded: str) -> list[Token]:
    """Return the tokens of folded, which is NFKC and casefolded."""
    data = encode(folded)
    return tokens_from_spans(folded, data, spans(data))


def count_cjk(text: str) -> int:
    """Return the number of CJK characters in text."""
    data = encode(text)
    return int(_count_cjk(data, len(data)))

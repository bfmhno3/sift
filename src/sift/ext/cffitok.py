"""The C tokenizer through cffi, in ABI mode.

``ffi.cdef`` declares the C functions and ``ffi.dlopen`` loads the
library: nothing is compiled, like ctypes, but the declarations are
written as C instead of as Python objects, and cffi converts the
arguments for you. API mode (``ffi.set_source`` and a compile step)
checks the declarations against the header; ABI mode trusts them.

SIFT_LIBTOK names another library file. Importing this module raises
OSError if the library is not there: run ``make ext``.
"""

import errno
import os
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from cffi import FFI

from sift.analysis.tokenize import Token
from sift.ext import encode, tokens_from_spans

if TYPE_CHECKING:
    from cffi import CData

LIBRARY = Path(__file__).resolve().parents[3] / "c/build/libsifttok.so"
# See sift.ext.ctok.FIRST_GUESS.
FIRST_GUESS = 4

ffi = FFI()
ffi.cdef(
    """
    struct sift_span {
        size_t start;
        size_t end;
    };
    int sift_tokenize(const char *utf8, size_t len,
                      struct sift_span *out, size_t cap, size_t *n_out);
    size_t sift_count_cjk(const char *utf8, size_t len);
    """
)


class _Library(Protocol):
    """The functions that ffi.cdef declared, as dlopen hands them out."""

    def sift_tokenize(
        self,
        utf8: bytes,
        len: int,
        out: CData,
        cap: int,
        n_out: CData,
    ) -> int: ...

    def sift_count_cjk(self, utf8: bytes, len: int) -> int: ...


_lib = cast(
    "_Library",
    ffi.dlopen(str(Path(os.environ.get("SIFT_LIBTOK", LIBRARY)))),
)


def spans(data: bytes) -> list[int]:
    """Return the token spans of UTF-8 data: start, end, start, ...

    Raise OSError if the C code reports an error.
    """
    cap = len(data) // FIRST_GUESS + 1
    n = ffi.new("size_t *")
    while True:
        buf = ffi.new("struct sift_span[]", cap)
        rc = _lib.sift_tokenize(data, len(data), buf, cap, n)
        if rc == 0:
            break
        if rc != -errno.ENOSPC:
            raise OSError(-rc, os.strerror(-rc))
        cap = n[0]
    numbers = ffi.cast("size_t *", buf)
    return ffi.unpack(numbers, 2 * n[0])


def tokens(folded: str) -> list[Token]:
    """Return the tokens of folded, which is NFKC and casefolded."""
    data = encode(folded)
    return tokens_from_spans(folded, data, spans(data))


def count_cjk(text: str) -> int:
    """Return the number of CJK characters in text."""
    data = encode(text)
    return int(_lib.sift_count_cjk(data, len(data)))

# cython: language_level=3, boundscheck=False, wraparound=False
"""The tokenizer of Sift in Cython: a typed loop over a str.

tokens() takes text that is already NFKC-normalized and casefolded
(sift.analysis.tokenize.fold) and returns what iter_tokens would yield
for it, as a list. The offsets are str offsets; no byte is encoded.
"""

from sift.analysis.tokenize import Token

cdef object _new = tuple.__new__


cdef inline bint is_latin(Py_UCS4 c) noexcept:
    return (u"0" <= c <= u"9") or (u"a" <= c <= u"z") or c == u"_"


cdef inline bint is_cjk(Py_UCS4 c) noexcept:
    return (
        0x3400 <= c <= 0x4DBF
        or 0x4E00 <= c <= 0x9FFF
        or 0xF900 <= c <= 0xFAFF
    )


def tokens(str folded):
    """Return the tokens of folded, a list of Token."""
    cdef Py_ssize_t n = len(folded)
    cdef Py_ssize_t i = 0
    cdef Py_ssize_t start, k, size
    cdef Py_ssize_t position = 0
    cdef Py_UCS4 c
    cdef list out = []

    while i < n:
        c = folded[i]
        start = i
        if is_latin(c):
            while i < n and is_latin(folded[i]):
                i += 1
            if i < n and folded[i] == u"+":
                i += 1
                if i < n and folded[i] == u"+":
                    i += 1
            elif i < n and folded[i] == u"#":
                i += 1
            out.append(
                _new(Token, (folded[start:i], position, start, i))
            )
            position += 1
        elif is_cjk(c):
            while i < n and is_cjk(folded[i]):
                i += 1
            size = i - start
            if size == 1:
                out.append(
                    _new(Token, (folded[start:i], position, start, i))
                )
                position += 1
            else:
                for k in range(start, i - 1):
                    out.append(
                        _new(
                            Token,
                            (folded[k:k + 2], position, k, k + 2),
                        )
                    )
                    position += 1
        else:
            i += 1
    return out


def count_cjk(str text):
    """Return the number of CJK characters in text."""
    cdef Py_ssize_t i
    cdef Py_ssize_t count = 0
    for i in range(len(text)):
        if is_cjk(text[i]):
            count += 1
    return count


def count_cjk_utf8(const unsigned char[::1] data):
    """Return the number of CJK characters in UTF-8 bytes.

    data is any contiguous buffer (bytes, bytearray, memoryview,
    array); it is read in place through a typed memoryview. Bytes
    that do not form a CJK character are skipped.
    """
    cdef Py_ssize_t i = 0
    cdef Py_ssize_t n = data.shape[0]
    cdef Py_ssize_t count = 0
    cdef unsigned int cp
    while i < n:
        if (
            0xE0 <= data[i] <= 0xEF
            and i + 2 < n
            and (data[i + 1] & 0xC0) == 0x80
            and (data[i + 2] & 0xC0) == 0x80
        ):
            cp = (
                ((data[i] & 0x0F) << 12)
                | ((data[i + 1] & 0x3F) << 6)
                | (data[i + 2] & 0x3F)
            )
            if is_cjk(cp):
                count += 1
            i += 3
        else:
            i += 1
    return count

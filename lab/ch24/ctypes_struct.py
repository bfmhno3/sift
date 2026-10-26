"""ctypes_struct.py: Structure, arrays and the C tokenizer by hand.

The same declarations as sift.ext.ctok, written out one by one, then a
struct with padding to show what ``sizeof`` and the field offsets say.
"""

import ctypes

from sift.ext import ctok


class Padded(ctypes.Structure):
    """A struct with padding: a char, then a double."""

    _fields_ = [("tag", ctypes.c_char), ("value", ctypes.c_double)]


class Packed(ctypes.Structure):
    """The same fields without padding."""

    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("tag", ctypes.c_char), ("value", ctypes.c_double)]


def main() -> None:
    print("sizeof(Span):", ctypes.sizeof(ctok.Span))
    print("sizeof(Padded):", ctypes.sizeof(Padded))
    print("sizeof(Packed):", ctypes.sizeof(Packed))
    print("Padded.value offset:", Padded.value.offset)
    print("Packed.value offset:", Packed.value.offset)

    lib = ctok.load(ctok.LIBRARY)
    data = "c++ 搜索引擎".encode()
    cap = 2
    spans = (ctok.Span * cap)()
    n = ctypes.c_size_t()
    rc = lib.sift_tokenize(data, len(data), spans, cap, ctypes.byref(n))
    print(f"cap {cap}: rc {rc} (-ENOSPC), n_out {n.value}")
    print("written:", [(s.start, s.end) for s in spans])

    cap = n.value
    spans = (ctok.Span * cap)()
    rc = lib.sift_tokenize(data, len(data), spans, cap, ctypes.byref(n))
    print(f"cap {cap}: rc {rc}, n_out {n.value}")
    for span in spans:
        print(span.start, span.end, data[span.start : span.end].decode())

    # An array of Structures is a buffer: the numbers are right there.
    view = memoryview(spans).cast("B").cast("N")
    print("as size_t:", view.tolist())


if __name__ == "__main__":
    main()

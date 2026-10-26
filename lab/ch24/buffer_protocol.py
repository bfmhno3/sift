"""buffer_protocol.py: pass memory to C without a copy.

A bytearray, a memoryview over it and a ctypes array all expose the
same memory through the buffer protocol. ``from_buffer`` makes a ctypes
view of it (writable, no copy); the typed memoryview of Cython reads it
in place. Writing through one shows in the others.
"""

import ctypes

from sift.ext import _cytok, ctok


def main() -> None:
    lib = ctok.load(ctok.LIBRARY)
    text = "ab 搜索引擎 cd"
    data = bytearray(text.encode())
    view = memoryview(data)
    print("bytearray, memoryview share memory:", view.obj is data)

    # c_char * n .from_buffer: a ctypes array over the bytearray.
    array = (ctypes.c_char * len(data)).from_buffer(data)
    print("array sees the same bytes:", bytes(array) == bytes(data))
    print(
        "count_cjk via C, no copy:",
        lib.sift_count_cjk(array, len(data)),
    )
    print("count_cjk via Cython memoryview:", _cytok.count_cjk_utf8(view))

    # A slice of a memoryview is a view too: pass the CJK part only.
    start = data.index("搜".encode())
    part = view[start : start + 6]
    print("view of 2 characters:", part.nbytes, "bytes,", bytes(part).decode())
    print("count_cjk of the view:", _cytok.count_cjk_utf8(part))

    # Write through the ctypes array: the bytearray changes.
    array[0] = b"A"
    print("after array[0] = b'A':", data[:2].decode())

    # While a view exists, the bytearray cannot be resized.
    try:
        data.extend(b"x")
    except BufferError as error:
        print("resize with live exports:", error)
    del array, part
    view.release()
    data.extend(b"x")
    print("resize after release works:", len(data))


if __name__ == "__main__":
    main()

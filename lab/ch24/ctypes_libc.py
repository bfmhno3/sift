"""ctypes_libc.py: call libc from Python with ctypes.

Three things to see: a function whose declared types are wrong returns
a wrong answer without any error, a variadic function wants its
arguments as C types, and C's stdout is not Python's.
"""

import ctypes


def main() -> None:
    libc = ctypes.CDLL(None)

    # Without argtypes ctypes passes a Python bytes as char * and a
    # Python int as int; without restype it reads the result as int.
    text = "搜索 sift".encode()
    print("bytes:", len(text))
    print("strlen, defaults :", libc.strlen(text))
    libc.strlen.argtypes = [ctypes.c_char_p]
    libc.strlen.restype = ctypes.c_size_t
    print("strlen, declared :", libc.strlen(text))

    # A pointer comes back as a C int unless restype says otherwise:
    # the default cuts the address to 32 bits on a 64-bit build.
    libc.getenv.argtypes = [ctypes.c_char_p]
    cut = libc.getenv(b"PYTHONHASHSEED")
    libc.getenv.restype = ctypes.c_void_p
    address = libc.getenv(b"PYTHONHASHSEED")
    print("default restype cut the address:", cut != address)
    print("address fits 32 bits:", address < 2**32)
    libc.getenv.restype = ctypes.c_char_p
    print("getenv as c_char_p:", libc.getenv(b"PYTHONHASHSEED"))

    # printf is variadic: ctypes cannot know the types of the extra
    # arguments, so a float must be wrapped as a C double.
    libc.printf.argtypes = [ctypes.c_char_p]
    libc.printf.restype = ctypes.c_int
    libc.fflush.argtypes = [ctypes.c_void_p]
    try:
        libc.printf(b"%f\n", 1.5)
    except ctypes.ArgumentError as error:
        print("printf with a float:", error)
    libc.printf(b"printf with c_double: %.2f\n", ctypes.c_double(1.5))
    libc.printf(b"printf with ints: %d %s\n", 42, b"ok")
    # C stdio has its own buffer. Without the flush, a pipe shows this
    # output after everything Python printed.
    libc.fflush(None)
    print("after fflush")


if __name__ == "__main__":
    main()

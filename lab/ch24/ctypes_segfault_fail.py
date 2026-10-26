"""ctypes_segfault_fail.py: ctypes does not check pointers.

``string_at(0)`` reads the C string at address 0: the process gets
SIGSEGV and dies, with no exception to catch. The lab runner sees a
negative exit code (minus the signal number). faulthandler is the only
thing that speaks before the end: it prints the Python stack.
"""

import ctypes
import faulthandler


def read_address(address: int) -> bytes:
    """Return the C string at address."""
    return ctypes.string_at(address)


def main() -> None:
    faulthandler.enable()
    print("reading address 0 ...", flush=True)
    print(read_address(0))
    print("not reached")


if __name__ == "__main__":
    main()

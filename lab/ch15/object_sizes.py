"""sys.getsizeof of empty objects, and a look at the PyObject header."""

import ctypes
import sys
from dataclasses import dataclass


class Plain:
    pass


class WithSlots:
    __slots__ = ()


class TwoSlots:
    __slots__ = ("a", "b")


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


def header(obj: object) -> tuple[int, int]:
    """Return (refcount, type pointer) read from the object's memory.

    CPython puts ob_refcnt first and ob_type second; id(obj) is the
    address of that header (a CPython detail).
    """
    refcnt = ctypes.c_ssize_t.from_address(id(obj)).value
    ob_type = ctypes.c_size_t.from_address(id(obj) + 8).value
    return refcnt, ob_type


def main() -> None:
    """Print sizes in bytes, then read a header."""
    plain = Plain()
    samples: list[tuple[str, object]] = [
        ("object()", object()),
        ("None", None),
        ("True", True),
        ("0", 0),
        ("1", 1),
        ("2**30", 2**30),
        ("2**60", 2**60),
        ("2**100", 2**100),
        ("1.5", 1.5),
        ("''", ""),
        ("'a'", "a"),
        ("'ab' * 10", "ab" * 10),
        ("'中'", "中"),
        ("b''", b""),
        ("()", ()),
        ("(1,)", (1,)),
        ("[]", []),
        ("[1]", [1]),
        ("{}", {}),
        ("{1: 1}", {1: 1}),
        ("set()", set()),
        ("frozenset()", frozenset()),
        ("lambda: 0", lambda: 0),
        ("Plain()", plain),
        ("WithSlots()", WithSlots()),
        ("TwoSlots()", TwoSlots()),
        ("Point(1, 2)", Point(1, 2)),
        ("Plain (class)", Plain),
    ]
    print("-- sys.getsizeof")
    for label, value in samples:
        print(f"  {label:14} {sys.getsizeof(value):5}")
    plain.a = 1  # type: ignore[attr-defined]
    print("-- an instance dict is extra")
    print("  Plain() with one attribute:", sys.getsizeof(plain))
    print("  its __dict__              :", sys.getsizeof(plain.__dict__))
    print("-- the header: refcount, then the type pointer")
    item: list[int] = []
    count, ob_type = header(item)
    print("  refcount via ctypes   :", count)
    print("  sys.getrefcount       :", sys.getrefcount(item))
    print("  type pointer is id(list):", ob_type == id(list))
    keep = item
    print("  after another name    :", header(keep)[0])
    print("  pointer size          :", ctypes.sizeof(ctypes.c_void_p))


if __name__ == "__main__":
    main()

"""Names bind to objects: rebinding versus mutation."""

import sys


def main() -> None:
    """Show aliasing, mutation, rebinding and reference counts."""
    a = [1, 2, 3]
    b = a
    print("a is b:", a is b)
    b.append(4)
    print("after b.append(4), a =", a)
    b = b + [5]
    print("after b = b + [5], a =", a, "| b =", b)
    print("a is b:", a is b)

    x = 10
    y = x
    y += 1
    print("ints are immutable: x =", x, "| y =", y)

    obj = object()
    print("refcount of a fresh object:", sys.getrefcount(obj))
    alias = obj
    print("after one alias:", sys.getrefcount(obj))
    holder = [obj, obj]
    print("after a list holding it twice:", sys.getrefcount(obj))
    del alias
    del holder
    print("after del alias, del holder:", sys.getrefcount(obj))

    name = "temp"
    del name
    try:
        print(name)  # noqa: F821
    except NameError as exc:
        print("NameError:", exc)


if __name__ == "__main__":
    main()

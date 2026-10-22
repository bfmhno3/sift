"""Bases in an order that no linearization can respect."""


class A:
    """The parent."""


class B(A):
    """The child."""


def main() -> None:
    """List the parent before its child: C3 cannot satisfy both."""
    print("A.__mro__:", [c.__name__ for c in A.__mro__])
    print("B.__mro__:", [c.__name__ for c in B.__mro__])
    # error: TypeError: Cannot create a consistent method resolution
    # order (MRO) for bases A, B
    type("C", (A, B), {})


if __name__ == "__main__":
    main()

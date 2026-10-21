"""Operator overloading: __and__, __or__, __sub__, __radd__."""

from sift.index import Posting, PostingList


def plist(spec: dict[int, tuple[int, ...]]) -> PostingList:
    """Build a PostingList from {doc_id: positions}."""
    return PostingList(Posting(d, pos) for d, pos in spec.items())


class Money:
    """An amount that adds to ints, so that sum() works."""

    def __init__(self, cents: int) -> None:
        """Store the amount in cents."""
        self.cents = cents

    def __repr__(self) -> str:
        """Return the constructor-style form."""
        return f"Money({self.cents})"

    def __add__(self, other: object) -> Money:
        """Add a Money or an int number of cents."""
        if isinstance(other, Money):
            return Money(self.cents + other.cents)
        if isinstance(other, int):
            return Money(self.cents + other)
        return NotImplemented

    def __radd__(self, other: object) -> Money:
        """Handle ``int + Money``, tried after int.__add__ gives up."""
        return self.__add__(other)


def main() -> None:
    """Combine posting lists with &, | and -, then reflected ops."""
    rust = plist({1: (0, 4), 3: (2,), 5: (1,), 8: (9,)})
    safe = plist({3: (3,), 4: (0,), 5: (7,), 9: (1,)})
    print("rust:", rust.doc_ids())
    print("safe:", safe.doc_ids())
    print("rust & safe:", (rust & safe).doc_ids())
    print("rust | safe:", (rust | safe).doc_ids())
    print("rust - safe:", (rust - safe).doc_ids())
    print("safe - rust:", (safe - rust).doc_ids())
    print("positions in doc 5 of rust & safe:", (rust & safe)[1].positions)
    print("(rust & safe) == (safe & rust):", (rust & safe) == (safe & rust))
    # The operator is sugar for a method call on the left operand.
    print(
        "rust.__and__(safe) == rust & safe:", rust.__and__(safe) == rust & safe
    )

    # NotImplemented tells Python to try the other operand's reflected
    # method; if nobody handles it, the result is a TypeError.
    print("rust.__and__(3):", rust.__and__(3))
    try:
        rust & 3
    except TypeError as exc:
        print("rust & 3 ->", exc)

    print("Money(5) + Money(7):", Money(5) + Money(7))
    print("Money(5) + 1:", Money(5) + 1)
    print("1 + Money(5):", 1 + Money(5))
    print("sum of 3 Money:", sum([Money(1), Money(2), Money(3)]))
    print("Money(1).__add__('x'):", Money(1).__add__("x"))


if __name__ == "__main__":
    main()

"""Classes are objects; instance vs class attributes; bound methods."""


class Counter:
    """Count how often a term was seen."""

    kind = "counter"  # class attribute, shared by every instance

    def __init__(self, term: str) -> None:
        """Start a counter at zero for term."""
        self.term = term  # instance attribute
        self.count = 0

    def hit(self) -> int:
        """Count one more occurrence and return the new count."""
        self.count += 1
        return self.count


def main() -> None:
    """Walk through attribute lookup and bound methods."""
    a, b = Counter("rust"), Counter("python")
    a.hit()
    a.hit()
    print("a.__dict__:", a.__dict__)
    print("b.__dict__:", b.__dict__)
    print("Counter.__dict__ has 'kind':", "kind" in Counter.__dict__)
    print("a.kind, b.kind:", a.kind, b.kind)

    # Assigning through the instance shadows; it never edits the class.
    a.kind = "mine"
    print("after a.kind = 'mine':", a.kind, b.kind, Counter.kind)
    print("a.__dict__:", a.__dict__)
    del a.kind
    print("after del a.kind:", a.kind)

    # A class is an object: it has a type, a name, and can be passed on.
    print("type(Counter):", type(Counter))
    alias = Counter
    print("alias is Counter:", alias is Counter)
    print("alias('c').term:", alias("c").term)
    Dynamic = type("Dynamic", (), {"x": 1})
    print("type(...) made:", Dynamic, Dynamic().x)

    # A method is a function stored on the class. Looking it up on an
    # instance wraps it in a bound method that carries self.
    bound = a.hit
    print("bound:", type(bound).__name__, bound.__qualname__)
    print("bound.__self__ is a:", bound.__self__ is a)
    print("bound.__func__ is Counter.hit:", bound.__func__ is Counter.hit)
    print("bound():", bound())
    print("Counter.hit(a):", Counter.hit(a))
    print("type(Counter.hit):", type(Counter.hit).__name__)
    print("type(a.hit):", type(a.hit).__name__)


if __name__ == "__main__":
    main()

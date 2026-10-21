"""Defining __eq__ sets __hash__ to None; proof and the fix."""


class Plain:
    """Default identity-based equality and hash."""

    def __init__(self, doc_id: int) -> None:
        """Store the id."""
        self.doc_id = doc_id


class ByValue:
    """__eq__ without __hash__: instances become unhashable."""

    def __init__(self, doc_id: int) -> None:
        """Store the id."""
        self.doc_id = doc_id

    def __eq__(self, other: object) -> bool:
        """Compare by doc_id."""
        if not isinstance(other, ByValue):
            return NotImplemented
        return self.doc_id == other.doc_id


class Hashable(ByValue):
    """Restore hashing explicitly, consistent with __eq__."""

    def __hash__(self) -> int:
        """Hash the same field __eq__ compares."""
        return hash(self.doc_id)


def main() -> None:
    """Show the effect of __eq__ on __hash__."""
    print("Plain(1) == Plain(1):", Plain(1) == Plain(1))
    print("hash works on Plain:", isinstance(hash(Plain(1)), int))
    print("ByValue(1) == ByValue(1):", ByValue(1) == ByValue(1))
    print("'__hash__' in vars(ByValue):", "__hash__" in vars(ByValue))
    print("ByValue.__hash__:", ByValue.__hash__)
    print("Plain.__hash__:", Plain.__hash__)
    print("ByValue.__hash__ is None:", ByValue.__hash__ is None)
    print("Hashable.__hash__ is None:", Hashable.__hash__ is None)
    seen = {Hashable(1), Hashable(1), Hashable(2)}
    print("set of Hashable(1), (1), (2):", len(seen))
    print("ByValue(1) == 1:", ByValue(1) == 1)
    print("ByValue(1) != ByValue(2):", ByValue(1) != ByValue(2))


if __name__ == "__main__":
    main()
